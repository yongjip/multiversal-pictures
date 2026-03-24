from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .agents import StoryAgentConfig, StoryToShotlistAgent, default_agent_model, default_agent_reasoning_effort
from .dotenv import load_dotenv
from .files import ensure_dir, write_bytes, write_json
from .narration import build_narration_plan, render_narration_markdown
from .openai_responses import OpenAIResponsesClient
from .openai_speech import OpenAISpeechClient
from .openai_videos import OpenAIAPIError, OpenAIVideosClient
from .media import subtitle_layout_names, subtitle_preset_names
from .rendering import render_shots
from .shotlist import load_shotlist, resolve_shot_order
from .stitching import stitch_run
from .subtitles import export_subtitles
from .tts import synthesize_narration


SAMPLE_SHOTLIST = {
    "project": {
        "title": "Pobi Bamboo Breakfast",
        "model": "sora-2-pro",
        "size": "1280x720",
        "seconds": "8",
        "poll_interval_seconds": 10,
        "download_variants": ["video", "thumbnail"],
        "style_notes": "polished storybook animation, gentle cinematic motion, soft textures, clear focal composition",
        "narration_style": "warm, calm bedtime-story narrator",
        "narration_notes": "Keep each line short and clear enough to sit comfortably over the shot. Let narration carry the story so visuals stay expressive and simple.",
        "consistency_notes": "Pobi is a small round panda cub with soft black-and-white fur, bright curious eyes, and a tiny green scarf. Keep his face shape, body proportions, and scarf consistent across all shots.",
        "constraints": [
            "family-friendly children's story tone",
            "no text, no subtitles, no watermark",
            "clean anatomy and natural motion",
            "no scary imagery or aggressive action"
        ],
        "audio_notes": "Gentle bamboo forest ambience and soft birdsong under external narration."
    },
    "shots": [
        {
            "id": "shot-01-morning",
            "title": "Pobi wakes up",
            "shot_type": "Wide storybook shot",
            "subject": "Pobi, a small round panda cub",
            "action": "wakes up in a bamboo bed, stretches his paws, and smiles sleepily",
            "setting": "a cozy bamboo hut on a green mountain at sunrise",
            "lighting": "soft golden sunrise light through paper windows",
            "camera_motion": "slow push-in",
            "mood": "warm, calm, child-friendly",
            "narration_line": "On a soft green mountain, little Pobi opened his eyes to a brand-new morning.",
            "narration_cue": "start softly after the first half-second",
            "narration_offset_ms": 500,
            "sfx_notes": "light breeze, soft blanket rustle, tiny morning birds"
        },
        {
            "id": "shot-02-walk",
            "title": "Pobi walks to breakfast",
            "shot_type": "Medium tracking shot",
            "subject": "Pobi, the same panda cub",
            "action": "waddles happily along a forest path toward a bamboo grove",
            "setting": "a misty bamboo forest with dew on the leaves",
            "lighting": "fresh morning light with soft haze",
            "camera_motion": "gentle side-tracking move",
            "mood": "playful and peaceful",
            "narration_line": "His tummy gave a tiny rumble, so he set off to find the freshest bamboo in the forest.",
            "narration_cue": "land the second clause as he reaches the grove",
            "narration_offset_ms": 350,
            "sfx_notes": "gentle footsteps on leaves, soft forest ambience"
        },
        {
            "id": "shot-03-bamboo",
            "title": "Crunchy bamboo breakfast",
            "shot_type": "Close-up storybook shot",
            "subject": "Pobi, the same panda cub",
            "action": "takes a big crunchy bite of fresh bamboo and smiles with delight",
            "setting": "a bright bamboo grove filled with fresh green leaves",
            "lighting": "clean daylight with soft highlights on the leaves",
            "camera_motion": "subtle handheld-like drift",
            "mood": "cozy and joyful",
            "narration_line": "Crunch, crunch, crunch. Pobi's breakfast was cool, sweet, and delicious.",
            "narration_cue": "let the first crunch happen before the narration starts",
            "narration_offset_ms": 900,
            "sfx_notes": "clear bamboo crunch, leaf rustle, soft happy hum"
        },
        {
            "id": "shot-04-sharing",
            "title": "Sharing with friends",
            "shot_type": "Wide ensemble shot",
            "subject": "Pobi, the same panda cub, with a tiny red bird, a rabbit, and a shy deer",
            "action": "shares berries, apples, and tender leaves with the forest friends",
            "setting": "a sunny clearing beside the bamboo grove",
            "lighting": "warm morning sunlight with soft sparkles through the trees",
            "camera_motion": "slow circular move around the group",
            "mood": "kind, gentle, celebratory",
            "narration_line": "Soon everyone was smiling in the sunshine, because breakfast always tastes better when it is shared.",
            "narration_cue": "deliver the final clause as the camera opens to the group",
            "narration_offset_ms": 400,
            "sfx_notes": "soft chirps, friendly nibbling, gentle musical swell"
        }
    ]
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="multiversal-pictures",
        description="Multiversal Pictures CLI for shotlist-driven OpenAI video generation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-shotlist", help="Write a sample shot list JSON file.")
    init_parser.add_argument("--out", required=True, help="Output JSON path.")

    generate_parser = subparsers.add_parser("generate-shotlist", help="Use the planning agents to turn a story prompt into a shot list.")
    generate_input = generate_parser.add_mutually_exclusive_group(required=True)
    generate_input.add_argument("--prompt", help="Story premise or creative prompt.")
    generate_input.add_argument("--prompt-file", help="Path to a text file containing the story premise.")
    generate_parser.add_argument("--output", required=True, help="Output shot list JSON path.")
    generate_parser.add_argument("--brief-output", help="Optional path for the intermediate story brief JSON.")
    generate_parser.add_argument("--trace-output", help="Optional path for the raw agent trace JSON.")
    generate_parser.add_argument("--audience", default="children and families", help="Target audience description.")
    generate_parser.add_argument("--language", default="en", help="Target language for user-facing text.")
    generate_parser.add_argument("--style", default="polished storybook animation, gentle cinematic motion, soft textures", help="Desired visual style.")
    generate_parser.add_argument("--shots", type=int, default=4, help="Target shot count.")
    generate_parser.add_argument("--model", help="Override the planning model.")
    generate_parser.add_argument("--reasoning-effort", choices=["minimal", "low", "medium", "high"], help="Override reasoning effort for the planning model.")
    generate_parser.add_argument("--size", help="Default output size to write into the shot list.")
    generate_parser.add_argument("--seconds", help="Default clip length to write into the shot list.")
    generate_parser.add_argument("--dry-run", action="store_true", help="Write the request trace without calling the API.")

    render_parser = subparsers.add_parser("render-shotlist", help="Render every shot in a shot list.")
    render_parser.add_argument("--shotlist", required=True, help="Shot list JSON path.")
    render_parser.add_argument("--output", required=True, help="Output run directory.")
    render_parser.add_argument("--only", help="Comma-separated shot IDs to render.")
    render_parser.add_argument("--download-variants", help="Override variants, e.g. video,thumbnail.")
    render_parser.add_argument("--dry-run", action="store_true", help="Resolve prompts and requests without API calls.")
    render_parser.add_argument("--skip-existing", action="store_true", help="Skip shots with an existing completed manifest.")
    render_parser.add_argument("--jobs", type=int, default=1, help="Number of shots to render concurrently.")
    render_parser.add_argument("--poll-interval", type=int, help="Polling interval seconds.")
    render_parser.add_argument("--timeout-seconds", type=int, help="Maximum wait time per shot.")
    render_parser.add_argument("--stitch-output", help="Optional output video path to stitch completed shot videos after rendering.")
    render_parser.add_argument("--stitch-overwrite", action="store_true", help="Allow overwriting an existing stitched output.")
    render_parser.add_argument("--narration-audio", help="Optional narration audio file to mix into the stitched output.")
    render_parser.add_argument("--background-music", help="Optional background music file to mix into the stitched output.")
    render_parser.add_argument("--subtitle-file", help="Optional SRT or VTT subtitle file to embed or burn into the stitched output.")
    render_parser.add_argument("--subtitle-language", default="eng", help="Subtitle language tag for the embedded subtitle track.")
    render_parser.add_argument("--burn-subtitles", action="store_true", help="Burn subtitle text into video frames instead of embedding a subtitle track.")
    render_parser.add_argument("--subtitle-preset", choices=subtitle_preset_names(), help="Preset style for burned subtitles.")
    render_parser.add_argument("--subtitle-layout", choices=subtitle_layout_names(), help="Layout profile for burned subtitles.")
    render_parser.add_argument("--subtitle-style", help="Optional ffmpeg ASS force_style overrides for burned subtitles.")
    render_parser.add_argument("--clip-audio-volume", type=float, help="Mix level for original clip audio when narration is present.")
    render_parser.add_argument("--narration-volume", type=float, help="Mix level for narration audio.")
    render_parser.add_argument("--music-volume", type=float, help="Mix level for background music.")
    render_parser.add_argument("--mute-clip-audio", action="store_true", help="Mute original clip audio when mixing narration.")
    render_parser.add_argument("--no-music-ducking", action="store_true", help="Do not duck background music under narration.")

    character_parser = subparsers.add_parser("create-character", help="Create a reusable character from a reference video.")
    character_parser.add_argument("--video", required=True, help="Absolute or relative path to a reference video file.")
    character_parser.add_argument("--name", help="Optional character name.")
    character_parser.add_argument("--output", help="Optional path to write the character JSON.")

    download_parser = subparsers.add_parser("download", help="Download video, thumbnail, or spritesheet for a completed job.")
    download_parser.add_argument("--video-id", required=True, help="OpenAI video job ID.")
    download_parser.add_argument("--variant", default="video", help="video | thumbnail | spritesheet")
    download_parser.add_argument("--output", required=True, help="Output file path.")

    narration_parser = subparsers.add_parser("export-narration", help="Export a narration script from a shot list.")
    narration_parser.add_argument("--shotlist", required=True, help="Shot list JSON path.")
    narration_parser.add_argument("--output", required=True, help="Output file path.")
    narration_parser.add_argument("--format", choices=["markdown", "json"], help="Override output format.")

    synth_parser = subparsers.add_parser("synthesize-narration", help="Generate narration audio from a shot list with OpenAI TTS.")
    synth_parser.add_argument("--shotlist", required=True, help="Shot list JSON path.")
    synth_parser.add_argument("--output-dir", required=True, help="Output directory for narration assets.")
    synth_parser.add_argument("--model", help="Override TTS model.")
    synth_parser.add_argument("--voice", help="Override TTS voice.")
    synth_parser.add_argument("--response-format", choices=["mp3", "wav", "opus", "aac", "flac", "pcm"], help="Override TTS response format.")
    synth_parser.add_argument("--default-offset-ms", type=int, help="Fallback narration offset when a shot does not define one.")

    subtitle_parser = subparsers.add_parser("export-subtitles", help="Export SRT, VTT, or JSON subtitles from a shot list.")
    subtitle_parser.add_argument("--shotlist", required=True, help="Shot list JSON path.")
    subtitle_parser.add_argument("--output", required=True, help="Output subtitle path.")
    subtitle_parser.add_argument("--format", choices=["srt", "vtt", "json"], help="Override subtitle format.")
    subtitle_parser.add_argument("--narration-manifest", help="Optional narration-manifest.json for precise cue timing.")
    subtitle_parser.add_argument("--default-offset-ms", type=int, help="Fallback narration offset when a shot does not define one.")
    subtitle_parser.add_argument("--max-words-per-cue", type=int, default=8, help="Maximum words to keep in a single subtitle cue.")

    stitch_parser = subparsers.add_parser("stitch-run", help="Combine completed shot videos from a render run into one video.")
    stitch_parser.add_argument("--run-dir", required=True, help="Render run directory containing run-manifest.json.")
    stitch_parser.add_argument("--output", required=True, help="Output stitched video path.")
    stitch_parser.add_argument("--overwrite", action="store_true", help="Allow overwriting an existing output file.")
    stitch_parser.add_argument("--narration-audio", help="Optional narration audio file to mix into the stitched video.")
    stitch_parser.add_argument("--background-music", help="Optional background music file to mix into the stitched video.")
    stitch_parser.add_argument("--subtitle-file", help="Optional SRT or VTT subtitle file to embed or burn into the stitched video.")
    stitch_parser.add_argument("--subtitle-language", default="eng", help="Subtitle language tag for the embedded subtitle track.")
    stitch_parser.add_argument("--burn-subtitles", action="store_true", help="Burn subtitle text into video frames instead of embedding a subtitle track.")
    stitch_parser.add_argument("--subtitle-preset", choices=subtitle_preset_names(), help="Preset style for burned subtitles.")
    stitch_parser.add_argument("--subtitle-layout", choices=subtitle_layout_names(), help="Layout profile for burned subtitles.")
    stitch_parser.add_argument("--subtitle-style", help="Optional ffmpeg ASS force_style overrides for burned subtitles.")
    stitch_parser.add_argument("--clip-audio-volume", type=float, help="Mix level for original clip audio when narration is present.")
    stitch_parser.add_argument("--narration-volume", type=float, help="Mix level for narration audio.")
    stitch_parser.add_argument("--music-volume", type=float, help="Mix level for background music.")
    stitch_parser.add_argument("--mute-clip-audio", action="store_true", help="Mute original clip audio when mixing narration.")
    stitch_parser.add_argument("--no-music-ducking", action="store_true", help="Do not duck background music under narration.")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path.cwd()
    load_dotenv(project_root)

    try:
        if args.command == "init-shotlist":
            return cmd_init_shotlist(args)
        if args.command == "generate-shotlist":
            return cmd_generate_shotlist(args)
        if args.command == "render-shotlist":
            return cmd_render_shotlist(args)
        if args.command == "create-character":
            return cmd_create_character(args)
        if args.command == "download":
            return cmd_download(args)
        if args.command == "export-narration":
            return cmd_export_narration(args)
        if args.command == "synthesize-narration":
            return cmd_synthesize_narration(args)
        if args.command == "export-subtitles":
            return cmd_export_subtitles(args)
        if args.command == "stitch-run":
            return cmd_stitch_run(args)
    except (OpenAIAPIError, TimeoutError, ValueError, FileNotFoundError) as error:
        print(f"Error: {error}")
        return 1

    parser.print_help()
    return 1


def cmd_init_shotlist(args: argparse.Namespace) -> int:
    output_path = Path(args.out).resolve()
    write_json(output_path, SAMPLE_SHOTLIST)
    print(f"Wrote sample shot list: {output_path}")
    return 0


def cmd_generate_shotlist(args: argparse.Namespace) -> int:
    prompt_text = _read_prompt_text(args.prompt, args.prompt_file)
    output_path = Path(args.output).resolve()
    brief_output_path = Path(args.brief_output).resolve() if args.brief_output else output_path.with_name(f"{output_path.stem}.story-brief.json")
    trace_output_path = Path(args.trace_output).resolve() if args.trace_output else output_path.with_name(f"{output_path.stem}.agent-trace.json")
    model = args.model or default_agent_model()
    reasoning_effort = args.reasoning_effort or default_agent_reasoning_effort()
    video_model = os.getenv("OPENAI_VIDEO_MODEL", "sora-2-pro")
    size = args.size or os.getenv("OPENAI_VIDEO_SIZE", "1280x720")
    seconds = args.seconds or os.getenv("OPENAI_VIDEO_SECONDS", "8")

    client = None if args.dry_run else _responses_client_from_env()
    agent = StoryToShotlistAgent(client)
    result = agent.run(
        StoryAgentConfig(
            prompt=prompt_text,
            output_path=output_path,
            audience=args.audience,
            language=args.language,
            visual_style=args.style,
            shot_count=max(1, args.shots),
            model=model,
            video_model=video_model,
            reasoning_effort=reasoning_effort,
            size=size,
            seconds=seconds,
            dry_run=bool(args.dry_run),
            brief_output_path=brief_output_path,
            trace_output_path=trace_output_path,
        )
    )

    if result["dry_run"]:
        print(f"Wrote dry-run trace: {trace_output_path}")
        return 0

    print(f"Wrote story brief: {brief_output_path}")
    print(f"Wrote shot list: {output_path}")
    print(f"Wrote agent trace: {trace_output_path}")
    return 0


def cmd_render_shotlist(args: argparse.Namespace) -> int:
    shotlist_path = Path(args.shotlist).resolve()
    output_dir = Path(args.output).resolve()
    shotlist = load_shotlist(shotlist_path)
    project = dict(shotlist.get("project") or {})
    ordered_shots = resolve_shot_order(shotlist["shots"])
    selected_ids = _selected_ids(args.only)
    client = None if args.dry_run else _client_from_env(args.timeout_seconds)
    poll_interval = args.poll_interval or int(project.get("poll_interval_seconds") or os.getenv("OPENAI_POLL_INTERVAL_SECONDS", "10"))
    timeout_seconds = args.timeout_seconds or int(os.getenv("OPENAI_VIDEO_TIMEOUT_SECONDS", "1800"))
    run_manifest = render_shots(
        shotlist_path=shotlist_path,
        project=project,
        ordered_shots=ordered_shots,
        output_dir=output_dir,
        selected_ids=selected_ids,
        download_variants_override=args.download_variants,
        dry_run=bool(args.dry_run),
        skip_existing=bool(args.skip_existing),
        poll_interval=poll_interval,
        timeout_seconds=timeout_seconds,
        jobs=max(1, int(args.jobs or 1)),
        client=client,
    )
    print(f"Wrote run manifest: {output_dir / 'run-manifest.json'}")

    if args.stitch_output:
        if args.dry_run:
            print("Skipped stitching because render ran in dry-run mode.")
        else:
            stitch_manifest = stitch_run(
                run_dir=output_dir,
                output_path=Path(args.stitch_output).resolve(),
                overwrite=bool(args.stitch_overwrite),
                narration_audio_path=Path(args.narration_audio).resolve() if args.narration_audio else None,
                background_music_path=Path(args.background_music).resolve() if args.background_music else None,
                subtitle_path=Path(args.subtitle_file).resolve() if args.subtitle_file else None,
                subtitle_language=args.subtitle_language,
                burn_subtitles=bool(args.burn_subtitles),
                subtitle_preset=args.subtitle_preset,
                subtitle_layout=args.subtitle_layout,
                subtitle_style=args.subtitle_style,
                clip_audio_volume=0.0 if args.mute_clip_audio else args.clip_audio_volume,
                narration_volume=args.narration_volume,
                music_volume=args.music_volume,
                duck_music_under_narration=not bool(args.no_music_ducking),
            )
            print(f"Wrote stitched video: {stitch_manifest['output_path']}")
    return 0


def cmd_create_character(args: argparse.Namespace) -> int:
    client = _client_from_env(timeout_override=None)
    video_path = Path(args.video).expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    character = client.create_character(video_path, name=args.name)
    if args.output:
        output_path = Path(args.output).resolve()
        write_json(output_path, character)
        print(f"Wrote character JSON: {output_path}")
    else:
        print(character)
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    client = _client_from_env(timeout_override=None)
    output_path = Path(args.output).resolve()
    content = client.download_content(args.video_id, variant=args.variant)
    write_bytes(output_path, content)
    print(f"Downloaded {args.variant}: {output_path}")
    return 0


def cmd_export_narration(args: argparse.Namespace) -> int:
    shotlist_path = Path(args.shotlist).resolve()
    output_path = Path(args.output).resolve()
    output_format = args.format or ("json" if output_path.suffix.lower() == ".json" else "markdown")
    shotlist = load_shotlist(shotlist_path)
    plan = build_narration_plan(shotlist)

    if output_format == "json":
        write_json(output_path, plan)
    else:
        ensure_dir(output_path.parent)
        output_path.write_text(render_narration_markdown(plan), encoding="utf-8")

    print(f"Wrote narration {output_format}: {output_path}")
    return 0


def cmd_synthesize_narration(args: argparse.Namespace) -> int:
    client = _speech_client_from_env()
    model = args.model or os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    voice = args.voice or os.getenv("OPENAI_TTS_VOICE", "alloy")
    response_format = args.response_format or os.getenv("OPENAI_TTS_RESPONSE_FORMAT", "wav")
    default_offset_ms = args.default_offset_ms or int(os.getenv("STORYBOOK_NARRATION_OFFSET_MS", "500"))
    manifest = synthesize_narration(
        shotlist_path=Path(args.shotlist).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        client=client,
        model=model,
        voice=voice,
        response_format=response_format,
        default_offset_ms=default_offset_ms,
    )
    print(f"Wrote narration manifest: {Path(args.output_dir).resolve() / 'narration-manifest.json'}")
    print(f"Wrote narration audio: {manifest['master_audio_path']}")
    if manifest.get("subtitle_paths"):
        print(f"Wrote subtitles: {manifest['subtitle_paths']['srt']}")
    return 0


def cmd_export_subtitles(args: argparse.Namespace) -> int:
    output_path = Path(args.output).resolve()
    default_offset_ms = args.default_offset_ms or int(os.getenv("STORYBOOK_NARRATION_OFFSET_MS", "500"))
    subtitle_plan = export_subtitles(
        shotlist_path=Path(args.shotlist).resolve(),
        output_path=output_path,
        output_format=args.format,
        narration_manifest_path=Path(args.narration_manifest).resolve() if args.narration_manifest else None,
        default_offset_ms=default_offset_ms,
        max_words_per_cue=max(1, int(args.max_words_per_cue or 8)),
    )
    print(f"Wrote subtitles: {output_path}")
    print(f"Cue count: {subtitle_plan['cue_count']}")
    return 0


def cmd_stitch_run(args: argparse.Namespace) -> int:
    stitch_manifest = stitch_run(
        run_dir=Path(args.run_dir).resolve(),
        output_path=Path(args.output).resolve(),
        overwrite=bool(args.overwrite),
        narration_audio_path=Path(args.narration_audio).resolve() if args.narration_audio else None,
        background_music_path=Path(args.background_music).resolve() if args.background_music else None,
        subtitle_path=Path(args.subtitle_file).resolve() if args.subtitle_file else None,
        subtitle_language=args.subtitle_language,
        burn_subtitles=bool(args.burn_subtitles),
        subtitle_preset=args.subtitle_preset,
        subtitle_layout=args.subtitle_layout,
        subtitle_style=args.subtitle_style,
        clip_audio_volume=0.0 if args.mute_clip_audio else args.clip_audio_volume,
        narration_volume=args.narration_volume,
        music_volume=args.music_volume,
        duck_music_under_narration=not bool(args.no_music_ducking),
    )
    print(f"Wrote stitched video: {stitch_manifest['output_path']}")
    return 0


def _client_from_env(timeout_override: Optional[int]) -> OpenAIVideosClient:
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


def _read_prompt_text(prompt: Optional[str], prompt_file: Optional[str]) -> str:
    if prompt and prompt.strip():
        return prompt.strip()
    if prompt_file:
        return Path(prompt_file).expanduser().resolve().read_text(encoding="utf-8").strip()
    raise ValueError("Either --prompt or --prompt-file is required.")


def _selected_ids(value: Optional[str]) -> Set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}
