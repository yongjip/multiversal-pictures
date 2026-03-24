from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .files import ensure_dir, read_json, write_json
from .narration import build_narration_plan
from .shotlist import load_shotlist


def build_subtitle_plan(
    *,
    shotlist: Dict[str, Any],
    narration_manifest: Optional[Dict[str, Any]] = None,
    default_offset_ms: int = 500,
    max_words_per_cue: int = 8,
) -> Dict[str, Any]:
    narration_plan = build_narration_plan(shotlist, default_offset_ms=default_offset_ms)
    manifest_segments = {
        str(segment.get("shot_id")): segment for segment in (narration_manifest or {}).get("segments") or []
    }

    cues: List[Dict[str, Any]] = []
    timeline_cursor = 0.0
    cue_index = 1
    for segment in narration_plan.get("segments") or []:
        shot_seconds = _coerce_seconds(segment.get("seconds"))
        shot_start_seconds = timeline_cursor
        timeline_cursor += shot_seconds

        narration_line = str(segment.get("narration_line") or "").strip()
        if not narration_line:
            continue

        manifest_segment = manifest_segments.get(str(segment.get("shot_id"))) or {}
        offset_ms = int(manifest_segment.get("narration_offset_ms") or segment.get("narration_offset_ms") or default_offset_ms)
        offset_seconds = max(0.0, offset_ms / 1000.0)
        available_seconds = max(0.0, shot_seconds - offset_seconds)
        spoken_seconds = _spoken_duration_seconds(manifest_segment, available_seconds)
        cue_start_seconds = shot_start_seconds + offset_seconds
        cue_end_limit = shot_start_seconds + shot_seconds

        text_chunks = _split_subtitle_text(narration_line, max_words_per_cue=max_words_per_cue)
        chunk_durations = _allocate_chunk_durations(text_chunks, spoken_seconds or available_seconds)
        chunk_cursor = cue_start_seconds

        for text, duration in zip(text_chunks, chunk_durations):
            if not text:
                continue
            start_seconds = min(chunk_cursor, cue_end_limit)
            end_seconds = min(cue_end_limit, start_seconds + duration)
            if end_seconds <= start_seconds:
                end_seconds = min(cue_end_limit, start_seconds + 0.8)
            if end_seconds <= start_seconds:
                continue

            cues.append(
                {
                    "index": cue_index,
                    "shot_id": segment["shot_id"],
                    "shot_title": segment["shot_title"],
                    "start_seconds": round(start_seconds, 3),
                    "end_seconds": round(end_seconds, 3),
                    "text": text,
                }
            )
            cue_index += 1
            chunk_cursor = end_seconds

    return {
        "project_title": narration_plan.get("project_title") or "Untitled Storybook",
        "narration_style": narration_plan.get("narration_style") or "gentle storybook narration",
        "source": "narration_manifest" if narration_manifest else "shotlist",
        "cue_count": len(cues),
        "duration_seconds": round(timeline_cursor, 3),
        "cues": cues,
    }


def export_subtitles(
    *,
    shotlist_path: Path,
    output_path: Path,
    output_format: Optional[str] = None,
    narration_manifest_path: Optional[Path] = None,
    default_offset_ms: int = 500,
    max_words_per_cue: int = 8,
) -> Dict[str, Any]:
    shotlist = load_shotlist(shotlist_path)
    narration_manifest = read_json(narration_manifest_path) if narration_manifest_path else None
    subtitle_plan = build_subtitle_plan(
        shotlist=shotlist,
        narration_manifest=narration_manifest,
        default_offset_ms=default_offset_ms,
        max_words_per_cue=max_words_per_cue,
    )
    resolved_format = (output_format or _format_from_path(output_path)).lower()

    ensure_dir(output_path.parent)
    if resolved_format == "json":
        write_json(output_path, subtitle_plan)
    elif resolved_format == "vtt":
        output_path.write_text(render_vtt(subtitle_plan), encoding="utf-8")
    else:
        output_path.write_text(render_srt(subtitle_plan), encoding="utf-8")

    return subtitle_plan


def render_srt(plan: Dict[str, Any]) -> str:
    lines: List[str] = []
    for cue in plan.get("cues") or []:
        lines.append(str(cue["index"]))
        lines.append(f"{_format_srt_timestamp(cue['start_seconds'])} --> {_format_srt_timestamp(cue['end_seconds'])}")
        lines.append(str(cue["text"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_vtt(plan: Dict[str, Any]) -> str:
    lines: List[str] = ["WEBVTT", ""]
    for cue in plan.get("cues") or []:
        lines.append(f"{_format_vtt_timestamp(cue['start_seconds'])} --> {_format_vtt_timestamp(cue['end_seconds'])}")
        lines.append(str(cue["text"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_default_subtitle_assets(
    *,
    shotlist_path: Path,
    narration_manifest_path: Path,
    output_dir: Path,
    default_offset_ms: int = 500,
    max_words_per_cue: int = 8,
) -> Dict[str, str]:
    output_dir = ensure_dir(output_dir)
    paths = {
        "srt": output_dir / "captions.srt",
        "vtt": output_dir / "captions.vtt",
        "json": output_dir / "captions.json",
    }
    for format_name, path in paths.items():
        export_subtitles(
            shotlist_path=shotlist_path,
            output_path=path,
            output_format=format_name,
            narration_manifest_path=narration_manifest_path,
            default_offset_ms=default_offset_ms,
            max_words_per_cue=max_words_per_cue,
        )
    return {name: str(path) for name, path in paths.items()}


def _spoken_duration_seconds(segment: Dict[str, Any], fallback_seconds: float) -> float:
    raw_duration = segment.get("raw_duration_seconds")
    if raw_duration is None:
        return max(0.0, float(fallback_seconds))
    return max(0.0, min(float(raw_duration), float(fallback_seconds)))


def _split_subtitle_text(text: str, *, max_words_per_cue: int) -> List[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []

    clauses = [chunk.strip() for chunk in re.split(r"(?<=[.!?;:])\s+", normalized) if chunk.strip()]
    cues: List[str] = []
    for clause in clauses:
        words = clause.split()
        if len(words) <= max_words_per_cue:
            cues.append(clause)
            continue
        for index in range(0, len(words), max_words_per_cue):
            cues.append(" ".join(words[index : index + max_words_per_cue]))
    return cues or [normalized]


def _allocate_chunk_durations(text_chunks: List[str], total_seconds: float) -> List[float]:
    if not text_chunks:
        return []

    total_seconds = max(float(total_seconds), 0.8)
    weights = [max(1, len(chunk.split())) for chunk in text_chunks]
    weight_total = sum(weights) or len(text_chunks)
    provisional = [total_seconds * (weight / weight_total) for weight in weights]
    minimum = 0.8
    durations = [max(value, minimum) for value in provisional]
    scale = total_seconds / sum(durations)
    return [round(value * scale, 3) for value in durations]


def _format_from_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".vtt":
        return "vtt"
    if suffix == ".json":
        return "json"
    return "srt"


def _coerce_seconds(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def _format_vtt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"
