from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .files import ensure_dir, read_json, write_json
from .media import burn_subtitle_track, concat_video_clips, mix_storybook_audio, mux_subtitle_track
from .shotlist import load_shotlist, resolve_shot_order


def stitch_run(
    *,
    run_dir: Path,
    output_path: Path,
    overwrite: bool = False,
    narration_audio_path: Optional[Path] = None,
    background_music_path: Optional[Path] = None,
    clip_audio_volume: Optional[float] = None,
    narration_volume: Optional[float] = None,
    music_volume: Optional[float] = None,
    duck_music_under_narration: Optional[bool] = None,
    subtitle_path: Optional[Path] = None,
    subtitle_language: str = "eng",
    burn_subtitles: bool = False,
    subtitle_preset: Optional[str] = None,
    subtitle_layout: Optional[str] = None,
    subtitle_style: Optional[str] = None,
) -> Dict[str, Any]:
    run_manifest_path = run_dir / "run-manifest.json"
    shotlist_path = run_dir / "shotlist.json"
    if not run_manifest_path.exists():
        raise FileNotFoundError(run_manifest_path)
    if not shotlist_path.exists():
        raise FileNotFoundError(shotlist_path)

    run_manifest = read_json(run_manifest_path)
    shotlist = load_shotlist(shotlist_path)
    project = dict(shotlist.get("project") or {})
    ordered_ids = [shot["id"] for shot in resolve_shot_order(shotlist["shots"])]
    manifests_by_id = {str(shot.get("id")): shot for shot in run_manifest.get("shots") or []}
    video_paths = _ordered_video_paths(ordered_ids, manifests_by_id)
    if not video_paths:
        raise ValueError("No completed shot videos found in the run directory.")

    ensure_dir(output_path.parent)
    if output_path.exists() and not overwrite:
        raise ValueError(f"Output already exists: {output_path}")

    needs_audio_mix = bool(narration_audio_path or background_music_path)
    needs_subtitle_mux = bool(subtitle_path)
    temp_base_path = _stage_path(output_path, "base") if (needs_audio_mix or needs_subtitle_mux) else output_path
    audio_mode = concat_video_clips(
        video_paths=video_paths,
        output_path=temp_base_path,
        overwrite=True if (needs_audio_mix or needs_subtitle_mux) else overwrite,
    )

    final_audio_mode = audio_mode
    staged_output_path = temp_base_path
    if needs_audio_mix:
        staged_output_path = _stage_path(output_path, "audio") if needs_subtitle_mux else output_path
        final_audio_mode = mix_storybook_audio(
            video_path=temp_base_path,
            output_path=staged_output_path,
            overwrite=True if needs_subtitle_mux else overwrite,
            narration_audio_path=narration_audio_path,
            background_music_path=background_music_path,
            clip_audio_volume=clip_audio_volume if clip_audio_volume is not None else float(os.getenv("STORYBOOK_CLIP_AUDIO_VOLUME", "0.0")),
            narration_volume=narration_volume if narration_volume is not None else float(os.getenv("STORYBOOK_NARRATION_VOLUME", "1.0")),
            music_volume=music_volume if music_volume is not None else float(os.getenv("STORYBOOK_MUSIC_VOLUME", "0.12")),
            duck_music_under_narration=duck_music_under_narration if duck_music_under_narration is not None else os.getenv("STORYBOOK_DUCK_MUSIC_UNDER_NARRATION", "1") != "0",
        )
        if temp_base_path.exists() and temp_base_path != output_path:
            temp_base_path.unlink()

    subtitle_mode = None
    if needs_subtitle_mux and subtitle_path:
        if burn_subtitles:
            subtitle_mode = burn_subtitle_track(
                video_path=staged_output_path,
                subtitle_path=subtitle_path,
                output_path=output_path,
                overwrite=overwrite,
                preset=subtitle_preset or str(project.get("subtitle_preset") or os.getenv("STORYBOOK_SUBTITLE_PRESET", "storybook")),
                layout=subtitle_layout or str(project.get("subtitle_layout") or os.getenv("STORYBOOK_SUBTITLE_LAYOUT", "auto")),
                position=str(project.get("subtitle_position") or os.getenv("STORYBOOK_SUBTITLE_POSITION", "bottom")),
                style=subtitle_style,
            )
        else:
            subtitle_mode = mux_subtitle_track(
                video_path=staged_output_path,
                subtitle_path=subtitle_path,
                output_path=output_path,
                overwrite=overwrite,
                language=subtitle_language,
            )
        if staged_output_path.exists() and staged_output_path != output_path:
            staged_output_path.unlink()
    elif not needs_audio_mix and temp_base_path != output_path and temp_base_path.exists():
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
    if background_music_path:
        stitch_manifest["background_music_path"] = str(background_music_path)
    if subtitle_path:
        stitch_manifest["subtitle_path"] = str(subtitle_path)
        stitch_manifest["subtitle_language"] = subtitle_language
        stitch_manifest["burn_subtitles"] = bool(burn_subtitles)
        if subtitle_preset:
            stitch_manifest["subtitle_preset"] = subtitle_preset
        if subtitle_layout:
            stitch_manifest["subtitle_layout"] = subtitle_layout
        if project.get("subtitle_position"):
            stitch_manifest["subtitle_position"] = str(project.get("subtitle_position"))
        if subtitle_style:
            stitch_manifest["subtitle_style"] = subtitle_style
        if subtitle_mode:
            stitch_manifest["subtitle_mode"] = subtitle_mode
    write_json(run_dir / "stitch-manifest.json", stitch_manifest)
    return stitch_manifest


def _ordered_video_paths(ordered_ids: List[str], manifests_by_id: Dict[str, Dict[str, Any]]) -> List[Path]:
    paths: List[Path] = []
    for shot_id in ordered_ids:
        manifest = manifests_by_id.get(shot_id)
        if not manifest or manifest.get("status") != "completed":
            continue
        selected_downloads = manifest.get("downloads") or []
        if manifest.get("selected_candidate"):
            for candidate in manifest.get("candidates") or []:
                if str(candidate.get("candidate_id")) == str(manifest.get("selected_candidate")):
                    selected_downloads = candidate.get("downloads") or selected_downloads
                    break
        for download in selected_downloads:
            if download.get("variant") == "video" and download.get("path"):
                path = Path(str(download["path"]))
                if path.exists():
                    paths.append(path)
                break
    return paths


def _stage_path(output_path: Path, suffix: str) -> Path:
    return output_path.with_name(f"{output_path.stem}.{suffix}{output_path.suffix}")
