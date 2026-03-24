from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class MediaInfo:
    path: Path
    duration_seconds: Optional[float]
    has_audio: bool
    has_video: bool


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
    return MediaInfo(
        path=path,
        duration_seconds=duration_seconds,
        has_audio=" Audio:" in text,
        has_video=" Video:" in text,
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

    command = [ffmpeg, "-y" if overwrite else "-n", "-i", str(video_path), "-i", str(narration_audio_path)]
    if video_info.has_audio:
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
