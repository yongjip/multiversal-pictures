from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .files import ensure_dir, write_bytes, write_json
from .media import align_audio_to_duration, concat_audio_tracks, probe_media
from .narration import build_narration_plan
from .openai_speech import OpenAISpeechClient
from .shotlist import load_shotlist
from .subtitles import write_default_subtitle_assets


def synthesize_narration(
    *,
    shotlist_path: Path,
    output_dir: Path,
    client: OpenAISpeechClient,
    model: str,
    voice: str,
    response_format: str,
    default_offset_ms: int,
) -> Dict[str, Any]:
    shotlist = load_shotlist(shotlist_path)
    plan = build_narration_plan(shotlist, default_offset_ms=default_offset_ms)

    run_dir = ensure_dir(output_dir)
    raw_dir = ensure_dir(run_dir / "raw")
    aligned_dir = ensure_dir(run_dir / "aligned")
    manifest: Dict[str, Any] = {
        "shotlist_path": str(shotlist_path),
        "model": model,
        "voice": voice,
        "response_format": response_format,
        "segments": [],
    }

    aligned_paths: List[Path] = []
    instructions = _build_tts_instructions(plan)

    for index, segment in enumerate(plan["segments"], start=1):
        stem = f"{index:02d}-{_slug_segment(segment['shot_id'])}"
        raw_path = raw_dir / f"{stem}.{_audio_extension(response_format)}"
        audio_bytes = client.create_speech(
            model=model,
            voice=voice,
            input_text=segment["narration_line"],
            instructions=instructions,
            response_format=response_format,
        )
        write_bytes(raw_path, audio_bytes)

        raw_info = probe_media(raw_path)
        aligned_path = aligned_dir / f"{stem}.wav"
        clip_seconds = float(segment["seconds"])
        offset_ms = int(segment.get("narration_offset_ms") or default_offset_ms)
        align_audio_to_duration(
            input_audio_path=raw_path,
            output_audio_path=aligned_path,
            duration_seconds=clip_seconds,
            offset_ms=offset_ms,
            overwrite=True,
        )
        aligned_info = probe_media(aligned_path)
        aligned_paths.append(aligned_path)

        manifest["segments"].append(
            {
                "shot_id": segment["shot_id"],
                "shot_title": segment["shot_title"],
                "seconds": segment["seconds"],
                "narration_cue": segment["narration_cue"],
                "narration_line": segment["narration_line"],
                "narration_offset_ms": offset_ms,
                "raw_audio_path": str(raw_path),
                "aligned_audio_path": str(aligned_path),
                "raw_duration_seconds": raw_info.duration_seconds,
                "aligned_duration_seconds": aligned_info.duration_seconds,
                "overflow_seconds": _overflow_seconds(raw_info.duration_seconds, clip_seconds, offset_ms),
                "sfx_notes": segment.get("sfx_notes"),
            }
        )

    master_path = run_dir / "narration.wav"
    concat_audio_tracks(audio_paths=aligned_paths, output_path=master_path, overwrite=True)
    master_info = probe_media(master_path)
    manifest["master_audio_path"] = str(master_path)
    manifest["master_duration_seconds"] = master_info.duration_seconds

    write_json(run_dir / "narration-plan.json", plan)
    write_json(run_dir / "narration-manifest.json", manifest)
    manifest["subtitle_paths"] = write_default_subtitle_assets(
        shotlist_path=shotlist_path,
        narration_manifest_path=run_dir / "narration-manifest.json",
        output_dir=run_dir,
        default_offset_ms=default_offset_ms,
    )
    write_json(run_dir / "narration-manifest.json", manifest)
    return manifest


def _build_tts_instructions(plan: Dict[str, Any]) -> str:
    style = str(plan.get("narration_style") or "gentle storybook narration").strip()
    notes = str(plan.get("narration_notes") or "").strip()
    parts = [style]
    if notes:
        parts.append(notes)
    parts.append("Read clearly for a children's storybook. Keep pacing measured and warm.")
    return " ".join(parts)


def _audio_extension(response_format: str) -> str:
    normalized = response_format.strip().lower()
    if normalized in {"mp3", "wav", "opus", "aac", "flac", "pcm"}:
        return "wav" if normalized == "pcm" else normalized
    return normalized or "wav"


def _overflow_seconds(raw_duration_seconds: Optional[float], clip_seconds: float, offset_ms: int) -> float:
    if raw_duration_seconds is None:
        return 0.0
    available = max(0.0, clip_seconds - (offset_ms / 1000.0))
    return max(0.0, raw_duration_seconds - available)


def _slug_segment(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-") or "segment"
