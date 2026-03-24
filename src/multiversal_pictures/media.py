from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


SUBTITLE_STYLE_PRESETS = {
    "storybook": {
        "widescreen": "FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&HAA000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=36",
        "vertical": "FontSize=19,PrimaryColour=&H00FFFFFF,OutlineColour=&HAA000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=88",
    },
    "large": {
        "widescreen": "FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&HAA000000,BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginV=42",
        "vertical": "FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&HAA000000,BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginV=104",
    },
    "minimal": {
        "widescreen": "FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H88000000,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV=28",
        "vertical": "FontSize=17,PrimaryColour=&H00FFFFFF,OutlineColour=&H88000000,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV=78",
    },
    "high-contrast": {
        "widescreen": "FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&HDD000000,BorderStyle=1,Outline=4,Shadow=0,Alignment=2,MarginV=36",
        "vertical": "FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&HDD000000,BorderStyle=1,Outline=4,Shadow=0,Alignment=2,MarginV=92",
    },
}


@dataclass
class MediaInfo:
    path: Path
    duration_seconds: Optional[float]
    has_audio: bool
    has_video: bool
    width: Optional[int]
    height: Optional[int]


def ffmpeg_executable() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except ImportError as error:
        raise ValueError(
            "This workflow requires imageio-ffmpeg. Reinstall the project with `python3 -m pip install -e .`."
        ) from error
    return get_ffmpeg_exe()


def probe_media(path: Path, *, ffmpeg: Optional[str] = None) -> MediaInfo:
    ffmpeg = ffmpeg or ffmpeg_executable()
    completed = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
    )
    text = "\n".join([completed.stdout or "", completed.stderr or ""])
    duration_seconds = _parse_duration_seconds(text)
    width, height = _parse_video_dimensions(text)
    return MediaInfo(
        path=path,
        duration_seconds=duration_seconds,
        has_audio=" Audio:" in text,
        has_video=" Video:" in text,
        width=width,
        height=height,
    )


def concat_video_clips(
    *,
    video_paths: List[Path],
    output_path: Path,
    overwrite: bool = False,
) -> str:
    if not video_paths:
        raise ValueError("No video paths were provided for stitching.")

    if len(video_paths) == 1:
        _copy_file(video_paths[0], output_path, overwrite=overwrite)
        info = probe_media(output_path)
        return "clip_audio" if info.has_audio else "video_only"

    ffmpeg = ffmpeg_executable()
    infos = [probe_media(path, ffmpeg=ffmpeg) for path in video_paths]
    all_have_audio = all(info.has_audio for info in infos)

    command = [ffmpeg, "-y" if overwrite else "-n"]
    for path in video_paths:
        command.extend(["-i", str(path)])

    if all_have_audio:
        inputs = "".join(f"[{index}:v:0][{index}:a:0]" for index in range(len(video_paths)))
        filter_complex = f"{inputs}concat=n={len(video_paths)}:v=1:a=1[v][a]"
        command.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
        _run_ffmpeg(command, error_prefix="Clip stitching failed")
        return "clip_audio"

    video_inputs = "".join(f"[{index}:v:0]" for index in range(len(video_paths)))
    filter_complex = f"{video_inputs}concat=n={len(video_paths)}:v=1:a=0[v]"
    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    _run_ffmpeg(command, error_prefix="Clip stitching failed")
    return "video_only"


def mix_narration_audio(
    *,
    video_path: Path,
    narration_audio_path: Path,
    output_path: Path,
    overwrite: bool = False,
    clip_audio_volume: float = 0.35,
    narration_volume: float = 1.0,
) -> str:
    ffmpeg = ffmpeg_executable()
    video_info = probe_media(video_path, ffmpeg=ffmpeg)
    clip_audio_volume = max(0.0, float(clip_audio_volume))
    narration_volume = max(0.0, float(narration_volume))

    command = [ffmpeg, "-y" if overwrite else "-n", "-i", str(video_path), "-i", str(narration_audio_path)]
    if video_info.has_audio and clip_audio_volume > 0:
        filter_complex = (
            f"[0:a]volume={clip_audio_volume}[clip];"
            f"[1:a]volume={narration_volume}[narration];"
            "[clip][narration]amix=inputs=2:normalize=0:duration=first[aout]"
        )
        command.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                "-shortest",
                str(output_path),
            ]
        )
        _run_ffmpeg(command, error_prefix="Narration mix failed")
        return "clip_plus_narration"

    command.extend(
        [
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]
    )
    _run_ffmpeg(command, error_prefix="Narration mux failed")
    return "narration_only"


def mix_storybook_audio(
    *,
    video_path: Path,
    output_path: Path,
    overwrite: bool = False,
    narration_audio_path: Optional[Path] = None,
    background_music_path: Optional[Path] = None,
    clip_audio_volume: float = 0.0,
    narration_volume: float = 1.0,
    music_volume: float = 0.12,
    duck_music_under_narration: bool = True,
) -> str:
    ffmpeg = ffmpeg_executable()
    video_info = probe_media(video_path, ffmpeg=ffmpeg)
    clip_audio_volume = max(0.0, float(clip_audio_volume))
    narration_volume = max(0.0, float(narration_volume))
    music_volume = max(0.0, float(music_volume))

    command = [ffmpeg, "-y" if overwrite else "-n", "-i", str(video_path)]
    input_index = 1
    narration_index: Optional[int] = None
    music_index: Optional[int] = None

    if narration_audio_path:
        narration_index = input_index
        command.extend(["-i", str(narration_audio_path)])
        input_index += 1

    if background_music_path:
        music_index = input_index
        command.extend(["-stream_loop", "-1", "-i", str(background_music_path)])
        input_index += 1

    source_labels: List[str] = []
    filter_parts: List[str] = []
    mode_parts: List[str] = []

    if video_info.has_audio and clip_audio_volume > 0:
        filter_parts.append(f"[0:a]volume={clip_audio_volume}[clip]")
        source_labels.append("[clip]")
        mode_parts.append("clip")

    narration_label: Optional[str] = None
    if narration_index is not None:
        filter_parts.append(f"[{narration_index}:a]volume={narration_volume}[narration]")
        narration_label = "[narration]"
        mode_parts.append("narration")

    music_label: Optional[str] = None
    if music_index is not None and music_volume > 0:
        filter_parts.append(f"[{music_index}:a]volume={music_volume}[music]")
        music_label = "[music]"
        mode_parts.append("music")

    if music_label and narration_label and duck_music_under_narration:
        filter_parts.append(f"{music_label}{narration_label}sidechaincompress=threshold=0.03:ratio=10:attack=15:release=400[ducked_music]")
        music_label = "[ducked_music]"
        mode_parts.append("ducked")

    if music_label:
        source_labels.append(music_label)
    if narration_label:
        source_labels.append(narration_label)

    if not source_labels:
        if output_path.exists() and not overwrite:
            raise ValueError(f"Output already exists: {output_path}")
        _copy_file(video_path, output_path, overwrite=overwrite)
        return "video_only"

    if len(source_labels) == 1:
        source_label = source_labels[0]
        filter_parts.append(f"{source_label}anull[aout]")
    else:
        joined = "".join(source_labels)
        filter_parts.append(f"{joined}amix=inputs={len(source_labels)}:normalize=0:duration=first[aout]")

    command.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]
    )
    _run_ffmpeg(command, error_prefix="Storybook audio mix failed")
    return "_plus_".join(mode_parts) if mode_parts else "video_only"


def mux_subtitle_track(
    *,
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    overwrite: bool = False,
    language: str = "eng",
) -> str:
    suffix = subtitle_path.suffix.lower()
    if suffix not in {".srt", ".vtt"}:
        raise ValueError(f"Unsupported subtitle format: {subtitle_path}")

    ffmpeg = ffmpeg_executable()
    command = [
        ffmpeg,
        "-y" if overwrite else "-n",
        "-i",
        str(video_path),
        "-i",
        str(subtitle_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-map",
        "1:0",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-c:s",
        "mov_text",
        "-metadata:s:s:0",
        f"language={language}",
        "-metadata:s:s:0",
        "handler_name=Storybook Subtitles",
        "-disposition:s:0",
        "default",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    _run_ffmpeg(command, error_prefix="Subtitle mux failed")
    return "embedded_subtitles"


def burn_subtitle_track(
    *,
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    overwrite: bool = False,
    preset: Optional[str] = None,
    layout: Optional[str] = None,
    style: Optional[str] = None,
) -> str:
    ffmpeg = ffmpeg_executable()
    video_info = probe_media(video_path, ffmpeg=ffmpeg)
    prepared_path, cleanup_paths = _prepare_subtitle_for_burn(subtitle_path)
    filter_path = _escape_subtitle_filter_value(prepared_path)
    subtitle_filter = f"subtitles=filename='{filter_path}'"
    subtitle_style = resolve_subtitle_style(
        preset=preset,
        style_override=style,
        layout=layout or os.getenv("STORYBOOK_SUBTITLE_LAYOUT", "auto"),
        video_width=video_info.width,
        video_height=video_info.height,
        font_scale=float(_safe_env_float("STORYBOOK_SUBTITLE_FONT_SCALE", 1.0)),
        margin_scale=float(_safe_env_float("STORYBOOK_SUBTITLE_MARGIN_SCALE", 1.0)),
    ).strip()
    if subtitle_style:
        subtitle_filter += f":force_style='{_escape_subtitle_style_value(subtitle_style)}'"

    command = [
        ffmpeg,
        "-y" if overwrite else "-n",
        "-i",
        str(video_path),
        "-vf",
        subtitle_filter,
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        _run_ffmpeg(command, error_prefix="Subtitle burn-in failed")
    finally:
        for path in cleanup_paths:
            if path.exists():
                path.unlink()
    return "burned_subtitles"


def align_audio_to_duration(
    *,
    input_audio_path: Path,
    output_audio_path: Path,
    duration_seconds: float,
    offset_ms: int,
    overwrite: bool = True,
) -> None:
    ffmpeg = ffmpeg_executable()
    offset_ms = max(0, int(offset_ms))
    if offset_ms:
        filter_chain = f"adelay={offset_ms}:all=1,apad,atrim=0:{duration_seconds}"
    else:
        filter_chain = f"apad,atrim=0:{duration_seconds}"

    command = [
        ffmpeg,
        "-y" if overwrite else "-n",
        "-i",
        str(input_audio_path),
        "-filter:a",
        filter_chain,
        "-c:a",
        "pcm_s16le",
        str(output_audio_path),
    ]
    _run_ffmpeg(command, error_prefix="Narration alignment failed")


def concat_audio_tracks(
    *,
    audio_paths: List[Path],
    output_path: Path,
    overwrite: bool = True,
) -> None:
    if not audio_paths:
        raise ValueError("No narration audio segments were provided.")
    if len(audio_paths) == 1:
        _copy_file(audio_paths[0], output_path, overwrite=overwrite)
        return

    ffmpeg = ffmpeg_executable()
    command = [ffmpeg, "-y" if overwrite else "-n"]
    for path in audio_paths:
        command.extend(["-i", str(path)])

    audio_inputs = "".join(f"[{index}:a:0]" for index in range(len(audio_paths)))
    filter_complex = f"{audio_inputs}concat=n={len(audio_paths)}:v=0:a=1[a]"
    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[a]",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
    )
    _run_ffmpeg(command, error_prefix="Narration track concat failed")


def _prepare_subtitle_for_burn(subtitle_path: Path) -> Tuple[Path, List[Path]]:
    suffix = subtitle_path.suffix.lower()
    if suffix == ".srt":
        return subtitle_path, []
    if suffix != ".vtt":
        raise ValueError(f"Unsupported subtitle format for burn-in: {subtitle_path}")

    temporary = tempfile.NamedTemporaryFile(prefix="multiversal-pictures-", suffix=".srt", delete=False)
    temp_path = Path(temporary.name)
    temporary.close()
    temp_path.write_text(_convert_vtt_to_srt(subtitle_path.read_text(encoding="utf-8")), encoding="utf-8")
    return temp_path, [temp_path]


def _convert_vtt_to_srt(value: str) -> str:
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue
        if stripped == "WEBVTT":
            continue
        current.append(stripped)
    if current:
        blocks.append(current)

    srt_blocks: List[str] = []
    cue_index = 1
    for block in blocks:
        timestamp_line, text_lines = _split_vtt_block(block)
        if not timestamp_line or not text_lines:
            continue
        srt_blocks.append(str(cue_index))
        srt_blocks.append(timestamp_line.replace(".", ","))
        srt_blocks.extend(text_lines)
        srt_blocks.append("")
        cue_index += 1
    return "\n".join(srt_blocks).rstrip() + "\n"


def _split_vtt_block(block: List[str]) -> Tuple[Optional[str], List[str]]:
    timestamp_index = -1
    for index, line in enumerate(block):
        if "-->" in line:
            timestamp_index = index
            break
    if timestamp_index < 0:
        return None, []
    text_lines = [line for line in block[timestamp_index + 1 :] if line and not line.startswith(("NOTE", "STYLE", "REGION"))]
    return _normalize_vtt_timestamp_line(block[timestamp_index]), text_lines


def _default_subtitle_style() -> str:
    return SUBTITLE_STYLE_PRESETS["storybook"]["widescreen"]


def subtitle_preset_names() -> List[str]:
    return list(SUBTITLE_STYLE_PRESETS.keys())


def subtitle_layout_names() -> List[str]:
    return ["auto", "widescreen", "vertical"]


def resolve_subtitle_style(
    *,
    preset: Optional[str],
    style_override: Optional[str],
    layout: Optional[str] = None,
    video_width: Optional[int] = None,
    video_height: Optional[int] = None,
    font_scale: float = 1.0,
    margin_scale: float = 1.0,
) -> str:
    resolved_preset = (preset or "storybook").strip().lower()
    if resolved_preset not in SUBTITLE_STYLE_PRESETS:
        choices = ", ".join(subtitle_preset_names())
        raise ValueError(f"Unknown subtitle preset '{resolved_preset}'. Expected one of: {choices}")

    base_style = _scaled_subtitle_style(
        base_style=_subtitle_style_for_layout(
            preset=resolved_preset,
            layout=_resolve_subtitle_layout(layout=layout, video_width=video_width, video_height=video_height),
        ),
        video_width=video_width or 1280,
        video_height=video_height or 720,
        font_scale=font_scale,
        margin_scale=margin_scale,
    )
    return _merge_subtitle_style_strings(base_style, (style_override or "").strip())


def _scaled_subtitle_style(
    *,
    base_style: str,
    video_width: int,
    video_height: int,
    font_scale: float,
    margin_scale: float,
) -> str:
    pairs = _parse_style_pairs(base_style)
    resolution_scale = max(0.5, min(float(video_width), float(video_height)) / 720.0)

    if "FontSize" in pairs:
        pairs["FontSize"] = str(_scaled_int(pairs["FontSize"], resolution_scale * max(font_scale, 0.1), minimum=10))
    if "MarginV" in pairs:
        pairs["MarginV"] = str(_scaled_int(pairs["MarginV"], resolution_scale * max(margin_scale, 0.1), minimum=12))
    if "Outline" in pairs:
        pairs["Outline"] = str(_scaled_int(pairs["Outline"], resolution_scale, minimum=1))
    if "Shadow" in pairs:
        pairs["Shadow"] = str(_scaled_int(pairs["Shadow"], resolution_scale, minimum=0))

    return ",".join(f"{key}={value}" for key, value in pairs.items())


def _subtitle_style_for_layout(*, preset: str, layout: str) -> str:
    style_by_layout = SUBTITLE_STYLE_PRESETS[preset]
    return style_by_layout.get(layout) or style_by_layout["widescreen"]


def _resolve_subtitle_layout(*, layout: Optional[str], video_width: Optional[int], video_height: Optional[int]) -> str:
    requested = (layout or "auto").strip().lower()
    if requested not in subtitle_layout_names():
        choices = ", ".join(subtitle_layout_names())
        raise ValueError(f"Unknown subtitle layout '{requested}'. Expected one of: {choices}")
    if requested != "auto":
        return requested
    if video_width and video_height and video_height > video_width:
        return "vertical"
    return "widescreen"


def _merge_subtitle_style_strings(base_style: str, override_style: str) -> str:
    override = override_style.strip()
    if not override:
        return base_style
    if not base_style:
        return override
    return f"{base_style},{override}"


def _parse_style_pairs(value: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for part in value.split(","):
        item = part.strip()
        if not item or "=" not in item:
            continue
        key, raw_value = item.split("=", 1)
        pairs[key.strip()] = raw_value.strip()
    return pairs


def _scaled_int(value: str, scale: float, *, minimum: int) -> int:
    try:
        base = float(value)
    except ValueError:
        return minimum
    return max(minimum, int(round(base * scale)))


def _normalize_vtt_timestamp_line(value: str) -> Optional[str]:
    match = re.search(
        r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})",
        value,
    )
    if not match:
        return None
    return f"{match.group('start')} --> {match.group('end')}"


def _escape_subtitle_filter_value(value: str | Path) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    text = text.replace(",", "\\,")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def _escape_subtitle_style_value(value: str) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    return text


def _copy_file(source: Path, destination: Path, *, overwrite: bool) -> None:
    if destination.exists() and not overwrite:
        raise ValueError(f"Output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _run_ffmpeg(command: List[str], *, error_prefix: str) -> None:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip() or "ffmpeg failed"
        raise ValueError(f"{error_prefix}: {stderr}")


def _parse_duration_seconds(text: str) -> Optional[float]:
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def _parse_video_dimensions(text: str) -> Tuple[Optional[int], Optional[int]]:
    match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _safe_env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
