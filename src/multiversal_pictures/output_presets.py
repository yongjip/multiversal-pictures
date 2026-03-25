from __future__ import annotations

import os
from typing import Any, Dict, Optional


OUTPUT_PRESETS: Dict[str, Dict[str, str]] = {
    "storybook-landscape": {
        "size": "1280x720",
        "seconds": "8",
        "subtitle_preset": "storybook",
        "subtitle_layout": "widescreen",
        "subtitle_position": "bottom",
        "format_guidance": "Compose for 16:9 landscape framing. Stage subjects with clear left-to-right reads and keep the lower center safe for optional subtitles.",
    },
    "storybook-vertical": {
        "size": "720x1280",
        "seconds": "8",
        "subtitle_preset": "large",
        "subtitle_layout": "vertical",
        "subtitle_position": "bottom_raised",
        "format_guidance": "Compose for 9:16 vertical framing. Keep the main subject centered, let the subject fill the middle band, avoid critical details at the extreme top or bottom, and reserve a taller raised lower subtitle-safe band.",
    },
    "storybook-short": {
        "size": "1280x720",
        "seconds": "6",
        "subtitle_preset": "large",
        "subtitle_layout": "widescreen",
        "subtitle_position": "bottom",
        "format_guidance": "Compose for 16:9 landscape framing with faster visual reads. Land one clear action per shot and keep the lower center safe for optional subtitles.",
    },
    "storybook-short-vertical": {
        "size": "720x1280",
        "seconds": "6",
        "subtitle_preset": "large",
        "subtitle_layout": "vertical",
        "subtitle_position": "bottom_raised",
        "format_guidance": "Compose for 9:16 vertical framing with quick, simple subject reads. Center the subject, prioritize one clear action per shot, and reserve a taller raised lower subtitle-safe band.",
    },
    "storybook-pro-landscape": {
        "size": "1792x1024",
        "seconds": "8",
        "subtitle_preset": "storybook",
        "subtitle_layout": "widescreen",
        "subtitle_position": "bottom",
        "format_guidance": "Compose for premium 16:9 landscape framing. Favor hero-shot clarity, controlled negative space, strong subject silhouette, and keep the lower center safe for optional subtitles.",
    },
    "storybook-pro-vertical": {
        "size": "1024x1792",
        "seconds": "8",
        "subtitle_preset": "large",
        "subtitle_layout": "vertical",
        "subtitle_position": "bottom_raised",
        "format_guidance": "Compose for premium 9:16 vertical framing. Keep the hero subject centered, stack action vertically, protect a taller raised lower subtitle-safe band, and avoid important details at the top and bottom extremes.",
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
    resolved["subtitle_position"] = preset["subtitle_position"]
    resolved["format_guidance"] = preset["format_guidance"]
    return resolved
