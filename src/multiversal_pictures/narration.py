from __future__ import annotations

from typing import Any, Dict, List, Optional

from .shotlist import resolve_shot_order


DEFAULT_NARRATION_TIMING_MODE = "locked"
DEFAULT_LOCKED_OFFSET_MS = 500
DEFAULT_COMPACT_OFFSET_MS = 150
DEFAULT_HOLD_AFTER_NARRATION_MS = 250
MINIMUM_STITCH_SECONDS = 1.6
NARRATION_TIMING_MODES = {"locked", "compact"}


def build_narration_plan(document: Dict[str, Any], *, default_offset_ms: Optional[int] = None) -> Dict[str, Any]:
    project = dict(document.get("project") or {})
    shots = resolve_shot_order(document.get("shots") or [])
    timing_mode = resolve_narration_timing_mode(project)
    fallback_offset_ms = _resolve_default_offset_ms(default_offset_ms, timing_mode=timing_mode)

    segments: List[Dict[str, Any]] = []
    for shot in shots:
        segments.append(
            {
                "shot_id": shot["id"],
                "shot_title": shot["title"],
                "seconds": str(shot.get("seconds") or project.get("seconds") or "8"),
                "narration_cue": str(shot.get("narration_cue") or "start"),
                "narration_line": _narration_line(shot),
                "narration_offset_ms": _coerce_int(shot.get("narration_offset_ms"), fallback_offset_ms),
                "hold_after_narration_ms": _coerce_int(
                    shot.get("hold_after_narration_ms"),
                    DEFAULT_HOLD_AFTER_NARRATION_MS,
                ),
                "stitch_seconds": _coerce_optional_seconds(shot.get("stitch_seconds")),
                "sfx_notes": str(shot.get("sfx_notes") or project.get("audio_notes") or "").strip(),
            }
        )

    return {
        "project_title": str(project.get("title") or "Untitled Storybook"),
        "narration_style": str(project.get("narration_style") or "gentle storybook narration"),
        "narration_notes": str(project.get("narration_notes") or "").strip(),
        "narration_timing_mode": timing_mode,
        "segments": segments,
    }


def render_narration_markdown(plan: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {plan['project_title']} Narration Script")
    lines.append("")
    lines.append(f"- Narration style: {plan['narration_style']}")
    lines.append(f"- Timing mode: {plan.get('narration_timing_mode') or DEFAULT_NARRATION_TIMING_MODE}")
    if plan.get("narration_notes"):
        lines.append(f"- Narration notes: {plan['narration_notes']}")
    lines.append("")

    for index, segment in enumerate(plan.get("segments") or [], start=1):
        lines.append(f"## {index}. {segment['shot_title']} ({segment['shot_id']})")
        lines.append(f"- Duration: {segment['seconds']}s")
        lines.append(f"- Cue: {segment['narration_cue']}")
        lines.append(f"- Offset: {segment['narration_offset_ms']}ms")
        if segment.get("stitch_seconds") is not None:
            lines.append(f"- Stitch length override: {segment['stitch_seconds']}s")
        if segment.get("hold_after_narration_ms") is not None:
            lines.append(f"- Post-line hold: {segment['hold_after_narration_ms']}ms")
        lines.append(f"- Narration: {segment['narration_line']}")
        if segment.get("sfx_notes"):
            lines.append(f"- SFX: {segment['sfx_notes']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _narration_line(shot: Dict[str, Any]) -> str:
    explicit = str(shot.get("narration_line") or "").strip()
    if explicit:
        return explicit

    title = str(shot.get("title") or "").strip()
    action = str(shot.get("action") or "").strip()
    if title and action:
        return f"{title}. {action}."
    return title or action or "Narration line not provided."


def resolve_narration_timing_mode(project: Dict[str, Any]) -> str:
    value = str(project.get("narration_timing_mode") or DEFAULT_NARRATION_TIMING_MODE).strip().lower()
    if value in NARRATION_TIMING_MODES:
        return value
    return DEFAULT_NARRATION_TIMING_MODE


def resolve_segment_stitch_seconds(
    segment: Dict[str, Any],
    *,
    raw_duration_seconds: Optional[float] = None,
    timing_mode: Optional[str] = None,
) -> float:
    generation_seconds = _coerce_seconds(segment.get("seconds"), fallback=0.0)
    mode = str(timing_mode or segment.get("narration_timing_mode") or DEFAULT_NARRATION_TIMING_MODE).strip().lower()
    explicit_seconds = _coerce_optional_seconds(segment.get("stitch_seconds"))
    if explicit_seconds is not None:
        return _clamp_stitch_seconds(explicit_seconds, generation_seconds)

    if mode != "compact" or raw_duration_seconds is None:
        return generation_seconds

    offset_ms = _coerce_int(segment.get("narration_offset_ms"), DEFAULT_COMPACT_OFFSET_MS)
    hold_ms = _coerce_int(segment.get("hold_after_narration_ms"), DEFAULT_HOLD_AFTER_NARRATION_MS)
    stitched = (offset_ms / 1000.0) + max(0.0, float(raw_duration_seconds)) + (hold_ms / 1000.0)
    return _clamp_stitch_seconds(stitched, generation_seconds)


def resolve_segment_timeline_seconds(
    segment: Dict[str, Any],
    *,
    manifest_segment: Optional[Dict[str, Any]] = None,
    timing_mode: Optional[str] = None,
) -> float:
    if manifest_segment and manifest_segment.get("stitch_seconds") is not None:
        return _coerce_seconds(manifest_segment.get("stitch_seconds"), fallback=0.0)
    return resolve_segment_stitch_seconds(segment, timing_mode=timing_mode)


def default_offset_ms_for_timing_mode(timing_mode: str) -> int:
    return DEFAULT_COMPACT_OFFSET_MS if str(timing_mode).strip().lower() == "compact" else DEFAULT_LOCKED_OFFSET_MS


def _resolve_default_offset_ms(default_offset_ms: Optional[int], *, timing_mode: str) -> int:
    if default_offset_ms is None:
        return default_offset_ms_for_timing_mode(timing_mode)
    return _coerce_int(default_offset_ms, default_offset_ms_for_timing_mode(timing_mode))


def _clamp_stitch_seconds(value: float, generation_seconds: float) -> float:
    upper_bound = max(float(generation_seconds), MINIMUM_STITCH_SECONDS)
    return round(min(max(float(value), MINIMUM_STITCH_SECONDS), upper_bound), 3)


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return int(fallback)


def _coerce_optional_seconds(value: Any) -> Optional[float]:
    if value in {None, ""}:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def _coerce_seconds(value: Any, *, fallback: float) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return float(fallback)
