from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .files import ensure_dir, write_bytes, write_json
from .media import normalize_image_to_size, parse_media_size
from .openai_images import OpenAIImagesClient
from .prompting import build_anchor_prompt
from .shotlist import load_shotlist, resolve_shot_order


def generate_anchor_images(
    *,
    shotlist_path: Path,
    output_dir: Path,
    output_shotlist_path: Path,
    client: OpenAIImagesClient,
    model: str,
    quality: str,
    replace_existing_input_reference: bool = False,
) -> Dict[str, Any]:
    document = load_shotlist(shotlist_path)
    project = dict(document.get("project") or {})
    ordered_shots = resolve_shot_order(document.get("shots") or [])

    run_dir = ensure_dir(output_dir)
    raw_dir = ensure_dir(run_dir / "raw")
    normalized_dir = ensure_dir(run_dir / "normalized")

    manifest: Dict[str, Any] = {
        "shotlist_path": str(shotlist_path),
        "output_shotlist_path": str(output_shotlist_path),
        "model": model,
        "quality": quality,
        "shots": [],
    }

    output_shots: List[Dict[str, Any]] = []
    for shot in ordered_shots:
        exportable_shot = dict(shot)
        exportable_shot.pop("order", None)

        mode = str(shot.get("mode") or "generate").strip().lower()
        if mode != "generate":
            output_shots.append(exportable_shot)
            manifest["shots"].append(
                {
                    "shot_id": shot["id"],
                    "status": "skipped_non_generate",
                }
            )
            continue

        if exportable_shot.get("input_reference") and not replace_existing_input_reference:
            output_shots.append(exportable_shot)
            manifest["shots"].append(
                {
                    "shot_id": shot["id"],
                    "status": "skipped_existing_reference",
                    "input_reference": exportable_shot.get("input_reference"),
                }
            )
            continue

        video_size = str(shot.get("size") or project.get("size") or "1280x720")
        anchor_size = image_generation_size_for_video(video_size)
        prompt = build_anchor_prompt(project, shot)

        stem = f"{shot['order']:02d}-{_slug_anchor_name(shot['id'])}"
        raw_path = raw_dir / f"{stem}.png"
        normalized_path = normalized_dir / f"{stem}.png"

        image_bytes = client.generate_image(
            model=model,
            prompt=prompt,
            size=anchor_size,
            quality=quality,
            output_format="png",
        )
        write_bytes(raw_path, image_bytes)
        normalize_image_to_size(
            input_path=raw_path,
            output_path=normalized_path,
            size=video_size,
            overwrite=True,
            fit="cover",
        )

        relative_anchor_path = os.path.relpath(normalized_path, output_shotlist_path.parent)
        exportable_shot["input_reference"] = {"path": relative_anchor_path}
        output_shots.append(exportable_shot)

        manifest["shots"].append(
            {
                "shot_id": shot["id"],
                "status": "generated",
                "video_size": video_size,
                "anchor_size": anchor_size,
                "prompt": prompt,
                "raw_path": str(raw_path),
                "normalized_path": str(normalized_path),
                "input_reference": exportable_shot["input_reference"],
            }
        )

    output_document = {
        "project": project,
        "shots": output_shots,
    }
    write_json(output_shotlist_path, output_document)
    write_json(run_dir / "anchors-manifest.json", manifest)
    return manifest


def image_generation_size_for_video(video_size: str) -> str:
    width, height = parse_media_size(video_size)
    if width == height:
        return "1024x1024"
    if width > height:
        return "1536x1024"
    return "1024x1536"


def _slug_anchor_name(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-") or "anchor"
