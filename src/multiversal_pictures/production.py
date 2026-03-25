from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .agents import StoryAgentConfig, StoryToShotlistAgent, default_agent_model, default_agent_reasoning_effort
from .anchors import generate_anchor_images
from .files import ensure_dir, read_json, write_json
from .openai_images import OpenAIImagesClient
from .openai_responses import OpenAIResponsesClient
from .openai_speech import OpenAISpeechClient
from .openai_videos import OpenAIVideosClient
from .output_presets import default_output_preset_name, preset_project_overrides, resolve_output_preset
from .rendering import render_shots
from .review import review_rendered_shots
from .shotlist import load_shotlist, resolve_shot_order
from .stitching import stitch_run
from .tts import synthesize_narration


PRODUCTION_STAGES = {"anchors", "narration", "render", "review", "stitch"}
PRODUCTION_MODES = {"preview", "balanced", "master"}


@dataclass
class StorybookProductionConfig:
    run_dir: Path
    output_path: Path
    prompt: Optional[str] = None
    prompt_file: Optional[Path] = None
    shotlist_path: Optional[Path] = None
    brief_output_path: Optional[Path] = None
    trace_output_path: Optional[Path] = None
    audience: str = "children and families"
    language: str = "en"
    style: str = "polished storybook animation, gentle cinematic motion, soft textures"
    shot_count: int = 4
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    output_preset: Optional[str] = None
    size: Optional[str] = None
    seconds: Optional[str] = None
    jobs: Optional[int] = None
    download_variants: Optional[str] = None
    skip_existing: bool = False
    poll_interval: Optional[int] = None
    timeout_seconds: Optional[int] = None
    narration_model: Optional[str] = None
    narration_voice: Optional[str] = None
    narration_response_format: Optional[str] = None
    default_offset_ms: int = 500
    with_anchors: Optional[bool] = None
    image_model: Optional[str] = None
    image_quality: Optional[str] = None
    with_review: bool = False
    review_mode: Optional[str] = None
    review_model: Optional[str] = None
    review_threshold: Optional[float] = None
    review_best_of: Optional[int] = None
    subtitle_file: Optional[Path] = None
    subtitle_language: str = "eng"
    burn_subtitles: bool = False
    subtitle_preset: Optional[str] = None
    subtitle_layout: Optional[str] = None
    subtitle_style: Optional[str] = None
    clip_audio_volume: Optional[float] = None
    narration_volume: Optional[float] = None
    music_volume: Optional[float] = None
    background_music_path: Optional[Path] = None
    mute_clip_audio: bool = True
    duck_music_under_narration: Optional[bool] = None
    no_music_ducking: bool = False
    overwrite: bool = False
    production_mode: Optional[str] = None
    resume: bool = False
    stop_after: Optional[str] = None


def run_storybook_production(config: StorybookProductionConfig) -> Dict[str, Any]:
    run_dir = ensure_dir(config.run_dir.expanduser().resolve())
    output_path = config.output_path.expanduser().resolve()
    production_mode = _resolve_production_mode(config.production_mode or os.getenv("STORYBOOK_PRODUCTION_MODE", "balanced"))
    stop_after = _resolve_stop_after(config.stop_after)
    resolved_output_preset = resolve_output_preset(config.output_preset or default_output_preset_name())

    source_shotlist_path = run_dir / "source-shotlist.json"
    anchored_shotlist_path = run_dir / "anchored-shotlist.json"
    brief_output_path = config.brief_output_path.expanduser().resolve() if config.brief_output_path else run_dir / "story-brief.json"
    trace_output_path = config.trace_output_path.expanduser().resolve() if config.trace_output_path else run_dir / "agent-trace.json"
    production_manifest_path = run_dir / "production-manifest.json"

    production_manifest: Dict[str, Any] = read_json(production_manifest_path) if config.resume and production_manifest_path.exists() else {}
    production_manifest.update(
        {
            "run_dir": str(run_dir),
            "output_path": str(output_path),
            "production_mode": production_mode,
            "stop_after": stop_after,
            "resume": bool(config.resume),
        }
    )

    shotlist_source = _prepare_or_resume_shotlist(
        config=config,
        staged_shotlist_path=source_shotlist_path,
        brief_output_path=brief_output_path,
        trace_output_path=trace_output_path,
        resolved_output_preset=resolved_output_preset,
    )
    shotlist = load_shotlist(source_shotlist_path)
    shotlist = _apply_production_defaults(
        document=shotlist,
        production_mode=production_mode,
        resolved_output_preset=resolved_output_preset,
    )
    write_json(source_shotlist_path, shotlist)
    production_manifest.update(
        {
            "shotlist_source": shotlist_source,
            "input_shotlist_path": str(source_shotlist_path),
            "current_shotlist_path": str(source_shotlist_path),
            "brief_output_path": str(brief_output_path) if brief_output_path.exists() else None,
            "trace_output_path": str(trace_output_path) if trace_output_path.exists() else None,
            "completed_stage": "shotlist",
        }
    )
    _write_production_manifest(production_manifest_path, production_manifest)

    effective_with_anchors = _effective_with_anchors(config.with_anchors, production_mode)
    anchor_manifest: Optional[Dict[str, Any]] = None
    effective_shotlist_path = source_shotlist_path
    if effective_with_anchors:
        anchor_manifest_path = run_dir / "anchors" / "anchors-manifest.json"
        if config.resume and _anchored_shotlist_ready(anchored_shotlist_path):
            anchor_manifest = read_json(anchor_manifest_path) if anchor_manifest_path.exists() else None
            effective_shotlist_path = anchored_shotlist_path
        else:
            anchor_manifest = generate_anchor_images(
                shotlist_path=source_shotlist_path,
                output_dir=run_dir / "anchors",
                output_shotlist_path=anchored_shotlist_path,
                client=_image_client_from_env(),
                model=config.image_model or os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1.5"),
                quality=config.image_quality or os.getenv("OPENAI_IMAGE_QUALITY", "high"),
            )
            effective_shotlist_path = anchored_shotlist_path
        production_manifest["anchor_manifest"] = anchor_manifest
    else:
        production_manifest["anchor_manifest"] = None

    production_manifest["current_shotlist_path"] = str(effective_shotlist_path)
    production_manifest["shotlist_path"] = str(effective_shotlist_path)
    production_manifest["completed_stage"] = "anchors" if effective_with_anchors else "shotlist"
    _write_production_manifest(production_manifest_path, production_manifest)
    if stop_after == "anchors":
        return production_manifest

    effective_shotlist = load_shotlist(effective_shotlist_path)
    project = dict(effective_shotlist.get("project") or {})
    ordered_shots = resolve_shot_order(effective_shotlist["shots"])
    poll_interval = config.poll_interval or int(project.get("poll_interval_seconds") or os.getenv("OPENAI_POLL_INTERVAL_SECONDS", "10"))
    timeout_seconds = config.timeout_seconds or int(os.getenv("OPENAI_VIDEO_TIMEOUT_SECONDS", "1800"))
    narration_model = config.narration_model or os.getenv("OPENAI_TTS_MODEL", "tts-1-hd")
    narration_voice = config.narration_voice or os.getenv("OPENAI_TTS_VOICE", "alloy")
    narration_response_format = config.narration_response_format or os.getenv("OPENAI_TTS_RESPONSE_FORMAT", "wav")

    narration_manifest = _resume_narration_manifest(run_dir) if config.resume else None
    render_manifest = _resume_render_manifest(run_dir) if config.resume else None
    render_enabled = stop_after != "narration"
    render_skip_existing = bool(config.skip_existing or config.resume)
    effective_jobs = _effective_jobs(config.jobs, production_mode)

    needs_narration = narration_manifest is None
    needs_render = render_enabled and render_manifest is None
    if needs_narration and not needs_render and stop_after == "narration":
        narration_manifest = synthesize_narration(
            shotlist_path=effective_shotlist_path,
            output_dir=run_dir / "narration",
            client=_speech_client_from_env(),
            model=narration_model,
            voice=narration_voice,
            response_format=narration_response_format,
            default_offset_ms=int(config.default_offset_ms),
        )
    elif needs_narration or needs_render:
        futures = {}
        with ThreadPoolExecutor(max_workers=2) as executor:
            if needs_render:
                futures[executor.submit(
                    render_shots,
                    shotlist_path=effective_shotlist_path,
                    project=project,
                    ordered_shots=ordered_shots,
                    output_dir=run_dir,
                    selected_ids=set(),
                    download_variants_override=config.download_variants,
                    dry_run=False,
                    skip_existing=render_skip_existing,
                    poll_interval=poll_interval,
                    timeout_seconds=timeout_seconds,
                    jobs=effective_jobs,
                    client=_video_client_from_env(config.timeout_seconds),
                )] = "render"
            if needs_narration:
                futures[executor.submit(
                    synthesize_narration,
                    shotlist_path=effective_shotlist_path,
                    output_dir=run_dir / "narration",
                    client=_speech_client_from_env(),
                    model=narration_model,
                    voice=narration_voice,
                    response_format=narration_response_format,
                    default_offset_ms=int(config.default_offset_ms),
                )] = "narration"

            for future in as_completed(futures):
                stage = futures[future]
                result = future.result()
                if stage == "render":
                    render_manifest = result
                else:
                    narration_manifest = result

    production_manifest["narration_manifest"] = narration_manifest
    if render_enabled:
        production_manifest["render_manifest"] = render_manifest
    production_manifest["completed_stage"] = "render" if render_enabled else "narration"
    _write_production_manifest(production_manifest_path, production_manifest)
    if stop_after == "narration":
        return production_manifest
    if stop_after == "render":
        return production_manifest

    review_manifest = _resume_review_manifest(run_dir) if config.resume and config.with_review else None
    effective_review_mode = _effective_review_mode(config.review_mode, production_mode)
    if config.with_review and review_manifest is None:
        review_manifest = review_rendered_shots(
            run_dir=run_dir,
            response_client=_responses_client_from_env(),
            video_client=_video_client_from_env(config.timeout_seconds),
            model=config.review_model or os.getenv("STORYBOOK_QA_MODEL", default_agent_model()),
            mode=effective_review_mode,
            threshold=float(config.review_threshold if config.review_threshold is not None else os.getenv("STORYBOOK_QA_THRESHOLD", "0.78")),
            best_of=int(
                config.review_best_of
                if config.review_best_of is not None
                else os.getenv("STORYBOOK_QA_BEST_OF", "2" if effective_review_mode == "repair" else "1")
            ),
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
            reasoning_effort=config.reasoning_effort or default_agent_reasoning_effort(),
        )
    production_manifest["review_manifest"] = review_manifest
    production_manifest["completed_stage"] = "review" if config.with_review else "render"
    _write_production_manifest(production_manifest_path, production_manifest)
    if stop_after == "review":
        return production_manifest

    subtitle_path = config.subtitle_file.expanduser().resolve() if config.subtitle_file else Path((narration_manifest or {})["subtitle_paths"]["srt"])
    stitch_manifest = None
    if config.resume and output_path.exists() and not config.overwrite and (run_dir / "stitch-manifest.json").exists():
        stitch_manifest = read_json(run_dir / "stitch-manifest.json")
    else:
        stitch_manifest = stitch_run(
            run_dir=run_dir,
            output_path=output_path,
            overwrite=bool(config.overwrite),
            narration_audio_path=Path((narration_manifest or {})["master_audio_path"]).resolve() if narration_manifest else None,
            background_music_path=config.background_music_path.expanduser().resolve() if config.background_music_path else None,
            clip_audio_volume=0.0 if config.mute_clip_audio else config.clip_audio_volume,
            narration_volume=config.narration_volume,
            music_volume=config.music_volume,
            duck_music_under_narration=not bool(config.no_music_ducking) if config.duck_music_under_narration is None else bool(config.duck_music_under_narration),
            subtitle_path=subtitle_path,
            subtitle_language=config.subtitle_language,
            burn_subtitles=bool(config.burn_subtitles),
            subtitle_preset=config.subtitle_preset or str(project.get("subtitle_preset") or (resolved_output_preset["subtitle_preset"] if resolved_output_preset else "")) or None,
            subtitle_layout=config.subtitle_layout or str(project.get("subtitle_layout") or (resolved_output_preset["subtitle_layout"] if resolved_output_preset else "")) or None,
            subtitle_style=config.subtitle_style,
        )

    production_manifest["stitch_manifest"] = stitch_manifest
    production_manifest["shotlist_path"] = str(run_dir / "shotlist.json") if (run_dir / "shotlist.json").exists() else str(effective_shotlist_path)
    production_manifest["output_path"] = str(output_path)
    production_manifest["completed_stage"] = "stitch"
    _write_production_manifest(production_manifest_path, production_manifest)
    return production_manifest


def _prepare_or_resume_shotlist(
    *,
    config: StorybookProductionConfig,
    staged_shotlist_path: Path,
    brief_output_path: Path,
    trace_output_path: Path,
    resolved_output_preset: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    if config.resume and staged_shotlist_path.exists():
        return {
            "source": "resume",
            "shotlist_path": str(staged_shotlist_path),
        }

    return _prepare_shotlist(
        config=config,
        staged_shotlist_path=staged_shotlist_path,
        brief_output_path=brief_output_path,
        trace_output_path=trace_output_path,
        resolved_output_preset=resolved_output_preset,
    )


def _prepare_shotlist(
    *,
    config: StorybookProductionConfig,
    staged_shotlist_path: Path,
    brief_output_path: Path,
    trace_output_path: Path,
    resolved_output_preset: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    if config.prompt or config.prompt_file:
        prompt_text = _read_prompt_text(config.prompt, config.prompt_file)
        response_client = _responses_client_from_env()
        output_preset_name = resolved_output_preset["name"] if resolved_output_preset else None
        size = config.size or (resolved_output_preset["size"] if resolved_output_preset else os.getenv("OPENAI_VIDEO_SIZE", "1280x720"))
        seconds = config.seconds or (resolved_output_preset["seconds"] if resolved_output_preset else os.getenv("OPENAI_VIDEO_SECONDS", "8"))
        agent = StoryToShotlistAgent(response_client)
        agent.run(
            StoryAgentConfig(
                prompt=prompt_text,
                output_path=staged_shotlist_path,
                audience=config.audience,
                language=config.language,
                visual_style=config.style,
                shot_count=max(1, int(config.shot_count)),
                model=config.model or default_agent_model(),
                video_model=os.getenv("OPENAI_VIDEO_MODEL", "sora-2-pro"),
                reasoning_effort=config.reasoning_effort or default_agent_reasoning_effort(),
                size=size,
                seconds=seconds,
                output_preset=output_preset_name,
                dry_run=False,
                brief_output_path=brief_output_path,
                trace_output_path=trace_output_path,
            )
        )
        return {
            "source": "prompt",
            "prompt_path": str(config.prompt_file.resolve()) if config.prompt_file else None,
        }

    if not config.shotlist_path:
        raise ValueError("Either a prompt or an existing shotlist is required.")

    shotlist_source_path = config.shotlist_path.expanduser().resolve()
    shotlist = load_shotlist(shotlist_source_path)
    if resolved_output_preset:
        shotlist["project"] = preset_project_overrides(project=dict(shotlist.get("project") or {}), preset=resolved_output_preset)
    write_json(staged_shotlist_path, shotlist)
    return {
        "source": "shotlist",
        "shotlist_path": str(shotlist_source_path),
    }


def _apply_production_defaults(
    *,
    document: Dict[str, Any],
    production_mode: str,
    resolved_output_preset: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    normalized = {
        "project": dict(document.get("project") or {}),
        "shots": [dict(shot) for shot in document.get("shots") or []],
    }
    project = dict(normalized["project"])
    if resolved_output_preset:
        project = preset_project_overrides(project=project, preset=resolved_output_preset)
    project["production_mode"] = production_mode
    if not project.get("subtitle_position") and resolved_output_preset and resolved_output_preset.get("subtitle_position"):
        project["subtitle_position"] = resolved_output_preset["subtitle_position"]
    normalized["project"] = project

    if production_mode != "master" or not _is_vertical_project(project):
        return normalized

    for shot in normalized["shots"]:
        if str(shot.get("mode") or "generate").strip().lower() != "generate":
            continue
        priority = str(shot.get("priority") or "normal").strip().lower()
        shot["size"] = "1080x1920" if priority == "high" else "1024x1792"
    if project.get("size"):
        project["size"] = "1024x1792"
    normalized["project"] = project
    return normalized


def _resume_narration_manifest(run_dir: Path) -> Optional[Dict[str, Any]]:
    path = run_dir / "narration" / "narration-manifest.json"
    if not path.exists():
        return None
    manifest = read_json(path)
    master_audio_path = str(manifest.get("master_audio_path") or "").strip()
    subtitle_paths = manifest.get("subtitle_paths") or {}
    if not master_audio_path or not Path(master_audio_path).expanduser().resolve().exists():
        return None
    required_subtitles = [subtitle_paths.get("srt"), subtitle_paths.get("vtt"), subtitle_paths.get("json")]
    if any(not value or not Path(str(value)).expanduser().resolve().exists() for value in required_subtitles):
        return None
    return manifest


def _resume_render_manifest(run_dir: Path) -> Optional[Dict[str, Any]]:
    path = run_dir / "run-manifest.json"
    if not path.exists():
        return None
    manifest = read_json(path)
    for shot_manifest in manifest.get("shots") or []:
        if str(shot_manifest.get("status") or "").strip().lower() != "completed":
            return None
        downloads = shot_manifest.get("downloads") or []
        if not downloads:
            return None
        missing_download = False
        for download in downloads:
            download_path = str(download.get("path") or "").strip()
            if not download_path or not Path(download_path).expanduser().resolve().exists():
                missing_download = True
                break
        if missing_download:
            return None
    return manifest


def _resume_review_manifest(run_dir: Path) -> Optional[Dict[str, Any]]:
    path = run_dir / "review-manifest.json"
    if not path.exists():
        return None
    return read_json(path)


def _anchored_shotlist_ready(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        shotlist = load_shotlist(path)
    except Exception:
        return False
    for shot in resolve_shot_order(shotlist.get("shots") or []):
        if str(shot.get("mode") or "generate").strip().lower() != "generate":
            continue
        input_reference = shot.get("input_reference") or {}
        reference_path = str(input_reference.get("path") or "").strip()
        if not reference_path:
            return False
        if not (path.parent / reference_path).resolve().exists():
            return False
    return True


def _write_production_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    write_json(path, manifest)


def _resolve_production_mode(value: Optional[str]) -> str:
    normalized = str(value or "balanced").strip().lower()
    if normalized not in PRODUCTION_MODES:
        choices = ", ".join(sorted(PRODUCTION_MODES))
        raise ValueError(f"Unsupported production mode '{value}'. Expected one of: {choices}")
    return normalized


def _resolve_stop_after(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized not in PRODUCTION_STAGES:
        choices = ", ".join(sorted(PRODUCTION_STAGES))
        raise ValueError(f"Unsupported stop-after stage '{value}'. Expected one of: {choices}")
    return normalized


def _effective_jobs(value: Optional[int], production_mode: str) -> int:
    if value:
        return max(1, int(value))
    return 1 if production_mode == "preview" else 2


def _effective_with_anchors(value: Optional[bool], production_mode: str) -> bool:
    if value is not None:
        return bool(value)
    return production_mode in {"balanced", "master"}


def _effective_review_mode(value: Optional[str], production_mode: str) -> str:
    normalized = str(value or os.getenv("STORYBOOK_REVIEW_MODE", "")).strip().lower()
    if normalized in {"score_only", "repair"}:
        return normalized
    return "repair" if production_mode == "master" else "score_only"


def _is_vertical_project(project: Dict[str, Any]) -> bool:
    size_value = str(project.get("size") or "").strip().lower()
    if "x" not in size_value:
        return False
    width_text, height_text = size_value.split("x", 1)
    try:
        return int(height_text) > int(width_text)
    except ValueError:
        return False


def _video_client_from_env(timeout_override: Optional[int]) -> OpenAIVideosClient:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing.")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    timeout = timeout_override or int(os.getenv("OPENAI_VIDEO_TIMEOUT_SECONDS", "1800"))
    return OpenAIVideosClient(api_key=api_key, base_url=base_url, timeout=timeout)


def _responses_client_from_env() -> OpenAIResponsesClient:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing.")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    timeout = int(os.getenv("OPENAI_AGENT_TIMEOUT_SECONDS", "600"))
    return OpenAIResponsesClient(api_key=api_key, base_url=base_url, timeout=timeout)


def _image_client_from_env() -> OpenAIImagesClient:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing.")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    timeout = int(os.getenv("OPENAI_AGENT_TIMEOUT_SECONDS", "600"))
    return OpenAIImagesClient(api_key=api_key, base_url=base_url, timeout=timeout)


def _speech_client_from_env() -> OpenAISpeechClient:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing.")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    timeout = int(os.getenv("OPENAI_TTS_TIMEOUT_SECONDS", "600"))
    return OpenAISpeechClient(api_key=api_key, base_url=base_url, timeout=timeout)


def _read_prompt_text(prompt: Optional[str], prompt_file: Optional[Path]) -> str:
    if prompt and prompt.strip():
        return prompt.strip()
    if prompt_file:
        return Path(prompt_file).expanduser().resolve().read_text(encoding="utf-8").strip()
    raise ValueError("Either prompt or prompt_file is required.")
