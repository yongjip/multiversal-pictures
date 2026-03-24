from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .files import image_path_to_data_url, read_json, slugify
from .prompting import build_shot_prompt


def load_shotlist(path: Path) -> Dict[str, Any]:
    document = read_json(path)
    if not isinstance(document, dict):
        raise ValueError("Shot list must be a JSON object.")
    if not isinstance(document.get("shots"), list) or not document["shots"]:
        raise ValueError("Shot list must include a non-empty shots array.")
    document.setdefault("project", {})
    return document


def resolve_shot_order(shots: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered: List[Dict[str, Any]] = []
    for index, shot in enumerate(shots, start=1):
        resolved = dict(shot)
        resolved.setdefault("id", f"shot-{index:02d}-{slugify(shot.get('title') or index)}")
        resolved.setdefault("title", resolved["id"])
        resolved["order"] = index
        ordered.append(resolved)
    return ordered


def build_shot_request(
    *,
    project: Dict[str, Any],
    shot: Dict[str, Any],
    shotlist_dir: Path,
    known_videos: Dict[str, str],
) -> Dict[str, Any]:
    mode = str(shot.get("mode") or "generate").strip().lower()
    prompt = build_shot_prompt(project, shot)
    payload: Dict[str, Any] = {
        "prompt": prompt,
        "model": str(shot.get("model") or project.get("model") or os.getenv("OPENAI_VIDEO_MODEL", "sora-2-pro")),
        "size": str(shot.get("size") or project.get("size") or os.getenv("OPENAI_VIDEO_SIZE", "1280x720")),
        "seconds": str(shot.get("seconds") or project.get("seconds") or os.getenv("OPENAI_VIDEO_SECONDS", "8")),
    }

    characters = shot.get("characters") or project.get("characters") or []
    normalized_characters = _normalize_characters(characters)
    if normalized_characters:
        payload["characters"] = normalized_characters

    input_reference = shot.get("input_reference")
    if input_reference:
        payload["input_reference"] = _resolve_input_reference(input_reference, shotlist_dir)

    if mode in {"extend", "edit"}:
        source_video_id = _resolve_source_video_id(shot, known_videos)
        if not source_video_id:
            raise ValueError(f"{shot['id']} requires source_video_id or source_shot_id.")
        payload["video"] = {"id": source_video_id}

    return payload


def _normalize_characters(value: Any) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append({"id": item.strip()})
        elif isinstance(item, dict) and item.get("id"):
            result.append({"id": str(item["id"]).strip()})
    return result


def _resolve_source_video_id(shot: Dict[str, Any], known_videos: Dict[str, str]) -> Optional[str]:
    if shot.get("source_video_id"):
        return str(shot["source_video_id"])
    source_shot_id = shot.get("source_shot_id")
    if source_shot_id:
        return known_videos.get(str(source_shot_id))
    return None


def _resolve_input_reference(value: Any, shotlist_dir: Path) -> Dict[str, str]:
    if isinstance(value, str):
        return {"image_url": value}

    if not isinstance(value, dict):
        raise ValueError("input_reference must be a string or object.")

    if value.get("file_id"):
        return {"file_id": str(value["file_id"])}

    if value.get("image_url"):
        return {"image_url": str(value["image_url"])}

    if value.get("path"):
        image_path = (shotlist_dir / str(value["path"])).resolve()
        return {"image_url": image_path_to_data_url(image_path)}

    raise ValueError("input_reference must contain file_id, image_url, or path.")


def preferred_variants(project: Dict[str, Any], shot: Dict[str, Any], override: Optional[str]) -> List[str]:
    if override:
        return [item.strip() for item in override.split(",") if item.strip()]
    configured = shot.get("download_variants") or project.get("download_variants") or ["video"]
    return [str(item).strip() for item in configured if str(item).strip()]
