from __future__ import annotations

import os
from typing import Any, Dict, Optional


OUTPUT_PRESETS: Dict[str, Dict[str, str]] = {
    "storybook-landscape": {
        "size": "1280x720",
        "seconds": "8",
        "subtitle_preset": "storybook",
        "subtitle_layout": "widescreen",
        "format_guidance": "Compose for 16:9 landscape framing. Stage subjects with clear left-to-right reads and keep the lower center safe for optional subtitles.",
    },
    "storybook-vertical": {
        "size": "720x1280",
        "seconds": "8",
        "subtitle_preset": "large",
        "subtitle_layout": "vertical",
        "format_guidance": "Compose for 9:16 vertical framing. Keep the main subject centered, stack action vertically, avoid critical details at the extreme top or bottom, and preserve lower-center subtitle safe area.",
    },
    "storybook-short": {
        "size": "1280x720",
        "seconds": "6",
        "subtitle_preset": "large",
        "subtitle_layout": "widescreen",
        "format_guidance": "Compose for 16:9 landscape framing with faster visual reads. Land one clear action per shot and keep the lower center safe for optional subtitles.",
    },
    "storybook-short-vertical": {
        "size": "720x1280",
        "seconds": "6",
        "subtitle_preset": "large",
        "subtitle_layout": "vertical",
        "format_guidance": "Compose for 9:16 vertical framing with quick, simple subject reads. Center the subject, prioritize one clear action per shot, and reserve lower-center subtitle safe area.",
    },
}


def output_preset_names() -> list[str]:
    return list(OUTPUT_PRESETS.keys())


def resolve_output_preset(name: Optional[str]) -> Optional[Dict[str, str]]:
    if not name:
        return None
    key = str(name).strip().lower()
    if not key:
        return None
    if key not in OUTPUT_PRESETS:
        choices = ", ".join(output_preset_names())
        raise ValueError(f"Unknown output preset '{key}'. Expected one of: {choices}")
    resolved = dict(OUTPUT_PRESETS[key])
    resolved["name"] = key
    return resolved


def default_output_preset_name() -> Optional[str]:
    value = os.getenv("STORYBOOK_OUTPUT_PRESET", "").strip().lower()
    return value or None


def preset_project_overrides(
    *,
    project: Dict[str, Any],
    preset: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    if not preset:
        return dict(project)

    resolved = dict(project)
    resolved["output_preset"] = preset["name"]
    resolved["size"] = preset["size"]
    resolved["seconds"] = preset["seconds"]
    resolved["subtitle_preset"] = preset["subtitle_preset"]
    resolved["subtitle_layout"] = preset["subtitle_layout"]
    resolved["format_guidance"] = preset["format_guidance"]
    return resolved
