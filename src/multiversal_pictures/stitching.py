from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .files import ensure_dir, read_json, write_json
from .media import concat_video_clips, mix_narration_audio
from .shotlist import load_shotlist, resolve_shot_order


def stitch_run(
    *,
    run_dir: Path,
    output_path: Path,
    overwrite: bool = False,
    narration_audio_path: Optional[Path] = None,
    clip_audio_volume: Optional[float] = None,
    narration_volume: Optional[float] = None,
) -> Dict[str, Any]:
    run_manifest_path = run_dir / "run-manifest.json"
    shotlist_path = run_dir / "shotlist.json"
    if not run_manifest_path.exists():
        raise FileNotFoundError(run_manifest_path)
    if not shotlist_path.exists():
        raise FileNotFoundError(shotlist_path)

    run_manifest = read_json(run_manifest_path)
    shotlist = load_shotlist(shotlist_path)
    ordered_ids = [shot["id"] for shot in resolve_shot_order(shotlist["shots"])]
    manifests_by_id = {str(shot.get("id")): shot for shot in run_manifest.get("shots") or []}
    video_paths = _ordered_video_paths(ordered_ids, manifests_by_id)
    if not video_paths:
        raise ValueError("No completed shot videos found in the run directory.")

    ensure_dir(output_path.parent)
    if output_path.exists() and not overwrite:
        raise ValueError(f"Output already exists: {output_path}")

    temp_base_path = output_path.with_suffix(".base.mp4") if narration_audio_path else output_path
    audio_mode = concat_video_clips(video_paths=video_paths, output_path=temp_base_path, overwrite=True if narration_audio_path else overwrite)

    final_audio_mode = audio_mode
    if narration_audio_path:
        final_audio_mode = mix_narration_audio(
            video_path=temp_base_path,
            narration_audio_path=narration_audio_path,
            output_path=output_path,
            overwrite=overwrite,
            clip_audio_volume=clip_audio_volume if clip_audio_volume is not None else float(os.getenv("STORYBOOK_CLIP_AUDIO_VOLUME", "0.0")),
            narration_volume=narration_volume if narration_volume is not None else float(os.getenv("STORYBOOK_NARRATION_VOLUME", "1.0")),
        )
        if temp_base_path.exists() and temp_base_path != output_path:
            temp_base_path.unlink()

    stitch_manifest = {
        "run_dir": str(run_dir),
        "output_path": str(output_path),
        "clip_count": len(video_paths),
        "clips": [str(path) for path in video_paths],
        "audio_mode": final_audio_mode,
    }
    if narration_audio_path:
        stitch_manifest["narration_audio_path"] = str(narration_audio_path)
    write_json(run_dir / "stitch-manifest.json", stitch_manifest)
    return stitch_manifest


def _ordered_video_paths(ordered_ids: List[str], manifests_by_id: Dict[str, Dict[str, Any]]) -> List[Path]:
    paths: List[Path] = []
    for shot_id in ordered_ids:
        manifest = manifests_by_id.get(shot_id)
        if not manifest or manifest.get("status") != "completed":
            continue
        for download in manifest.get("downloads") or []:
            if download.get("variant") == "video" and download.get("path"):
                path = Path(str(download["path"]))
                if path.exists():
                    paths.append(path)
                break
    return paths
