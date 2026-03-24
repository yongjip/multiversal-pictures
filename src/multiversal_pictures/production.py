from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .agents import StoryAgentConfig, StoryToShotlistAgent, default_agent_model, default_agent_reasoning_effort
from .files import ensure_dir, write_json
from .openai_responses import OpenAIResponsesClient
from .openai_speech import OpenAISpeechClient
from .openai_videos import OpenAIVideosClient
from .output_presets import default_output_preset_name, preset_project_overrides, resolve_output_preset
from .rendering import render_shots
from .shotlist import load_shotlist, resolve_shot_order
from .stitching import stitch_run
from .tts import synthesize_narration


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
    jobs: int = 1
    download_variants: Optional[str] = None
    skip_existing: bool = False
    poll_interval: Optional[int] = None
    timeout_seconds: Optional[int] = None
    narration_model: Optional[str] = None
    narration_voice: Optional[str] = None
    narration_response_format: Optional[str] = None
    default_offset_ms: int = 500
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


def run_storybook_production(config: StorybookProductionConfig) -> Dict[str, Any]:
    run_dir = ensure_dir(config.run_dir.expanduser().resolve())
    output_path = config.output_path.expanduser().resolve()
    resolved_output_preset = resolve_output_preset(config.output_preset or default_output_preset_name())

    source_shotlist_path = run_dir / "source-shotlist.json"
    brief_output_path = config.brief_output_path.expanduser().resolve() if config.brief_output_path else run_dir / "story-brief.json"
    trace_output_path = config.trace_output_path.expanduser().resolve() if config.trace_output_path else run_dir / "agent-trace.json"

    shotlist_source = _prepare_shotlist(
        config=config,
        staged_shotlist_path=source_shotlist_path,
        brief_output_path=brief_output_path,
        trace_output_path=trace_output_path,
        resolved_output_preset=resolved_output_preset,
    )

    video_client = _video_client_from_env(config.timeout_seconds)
    speech_client = _speech_client_from_env()

    shotlist = load_shotlist(source_shotlist_path)
    project = dict(shotlist.get("project") or {})
    if resolved_output_preset:
        project = preset_project_overrides(project=project, preset=resolved_output_preset)
        shotlist["project"] = project
        write_json(source_shotlist_path, shotlist)
    ordered_shots = resolve_shot_order(shotlist["shots"])

    poll_interval = config.poll_interval or int(project.get("poll_interval_seconds") or os.getenv("OPENAI_POLL_INTERVAL_SECONDS", "10"))
    timeout_seconds = config.timeout_seconds or int(os.getenv("OPENAI_VIDEO_TIMEOUT_SECONDS", "1800"))
    narration_model = config.narration_model or os.getenv("OPENAI_TTS_MODEL", "tts-1-hd")
    narration_voice = config.narration_voice or os.getenv("OPENAI_TTS_VOICE", "alloy")
    narration_response_format = config.narration_response_format or os.getenv("OPENAI_TTS_RESPONSE_FORMAT", "wav")

    render_future = None
    narration_future = None
    with ThreadPoolExecutor(max_workers=2) as executor:
        render_future = executor.submit(
            render_shots,
            shotlist_path=source_shotlist_path,
            project=project,
            ordered_shots=ordered_shots,
            output_dir=run_dir,
            selected_ids=set(),
            download_variants_override=config.download_variants,
            dry_run=False,
            skip_existing=config.skip_existing,
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
            jobs=max(1, int(config.jobs or 1)),
            client=video_client,
        )
        narration_future = executor.submit(
            synthesize_narration,
            shotlist_path=source_shotlist_path,
            output_dir=run_dir / "narration",
            client=speech_client,
            model=narration_model,
            voice=narration_voice,
            response_format=narration_response_format,
            default_offset_ms=int(config.default_offset_ms),
        )

        render_manifest: Dict[str, Any] = {}
        narration_manifest: Dict[str, Any] = {}
        errors: list[BaseException] = []
        for future in as_completed([render_future, narration_future]):
            try:
                result = future.result()
            except BaseException as error:  # noqa: BLE001
                errors.append(error)
            else:
                if future is render_future:
                    render_manifest = result
                else:
                    narration_manifest = result

        if errors:
            raise errors[0]

    subtitle_path = config.subtitle_file.expanduser().resolve() if config.subtitle_file else Path(narration_manifest["subtitle_paths"]["srt"])
    stitch_manifest = stitch_run(
        run_dir=run_dir,
        output_path=output_path,
        overwrite=bool(config.overwrite),
        narration_audio_path=Path(narration_manifest["master_audio_path"]).resolve(),
        background_music_path=config.background_music_path.expanduser().resolve() if config.background_music_path else None,
        clip_audio_volume=0.0 if config.mute_clip_audio else config.clip_audio_volume,
        narration_volume=config.narration_volume,
        music_volume=config.music_volume,
        duck_music_under_narration=not bool(config.no_music_ducking) if config.duck_music_under_narration is None else bool(config.duck_music_under_narration),
        subtitle_path=subtitle_path,
        subtitle_language=config.subtitle_language,
        burn_subtitles=bool(config.burn_subtitles),
        subtitle_preset=config.subtitle_preset or (resolved_output_preset["subtitle_preset"] if resolved_output_preset else None),
        subtitle_layout=config.subtitle_layout or (resolved_output_preset["subtitle_layout"] if resolved_output_preset else None),
        subtitle_style=config.subtitle_style,
    )

    effective_shotlist_path = run_dir / "shotlist.json"
    production_manifest = {
        "run_dir": str(run_dir),
        "output_path": str(output_path),
        "input_shotlist_path": str(source_shotlist_path),
        "shotlist_path": str(effective_shotlist_path if effective_shotlist_path.exists() else source_shotlist_path),
        "shotlist_source": shotlist_source,
        "brief_output_path": str(brief_output_path) if brief_output_path.exists() else None,
        "trace_output_path": str(trace_output_path) if trace_output_path.exists() else None,
        "render_manifest": render_manifest,
        "narration_manifest": narration_manifest,
        "stitch_manifest": stitch_manifest,
    }
    write_json(run_dir / "production-manifest.json", production_manifest)
    return production_manifest


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
