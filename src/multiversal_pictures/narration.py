from __future__ import annotations

from typing import Any, Dict, List

from .shotlist import resolve_shot_order


def build_narration_plan(document: Dict[str, Any], *, default_offset_ms: int = 500) -> Dict[str, Any]:
    project = dict(document.get("project") or {})
    shots = resolve_shot_order(document.get("shots") or [])

    segments: List[Dict[str, Any]] = []
    for shot in shots:
        segments.append(
            {
                "shot_id": shot["id"],
                "shot_title": shot["title"],
                "seconds": str(shot.get("seconds") or project.get("seconds") or "8"),
                "narration_cue": str(shot.get("narration_cue") or "start"),
                "narration_line": _narration_line(shot),
                "narration_offset_ms": int(shot.get("narration_offset_ms") or default_offset_ms),
                "sfx_notes": str(shot.get("sfx_notes") or project.get("audio_notes") or "").strip(),
            }
        )

    return {
        "project_title": str(project.get("title") or "Untitled Storybook"),
        "narration_style": str(project.get("narration_style") or "gentle storybook narration"),
        "narration_notes": str(project.get("narration_notes") or "").strip(),
        "segments": segments,
    }


def render_narration_markdown(plan: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {plan['project_title']} Narration Script")
    lines.append("")
    lines.append(f"- Narration style: {plan['narration_style']}")
    if plan.get("narration_notes"):
        lines.append(f"- Narration notes: {plan['narration_notes']}")
    lines.append("")

    for index, segment in enumerate(plan.get("segments") or [], start=1):
        lines.append(f"## {index}. {segment['shot_title']} ({segment['shot_id']})")
        lines.append(f"- Duration: {segment['seconds']}s")
        lines.append(f"- Cue: {segment['narration_cue']}")
        lines.append(f"- Offset: {segment['narration_offset_ms']}ms")
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
