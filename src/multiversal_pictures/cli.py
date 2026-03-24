from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .agents import StoryAgentConfig, StoryToShotlistAgent, default_agent_model, default_agent_reasoning_effort
from .dotenv import load_dotenv
from .files import ensure_dir, read_json, slugify, utc_timestamp, write_bytes, write_json
from .openai_responses import OpenAIResponsesClient
from .openai_videos import OpenAIAPIError, OpenAIVideosClient
from .shotlist import build_shot_request, load_shotlist, preferred_variants, resolve_shot_order


SAMPLE_SHOTLIST = {
    "project": {
        "title": "Pobi Bamboo Breakfast",
        "model": "sora-2-pro",
        "size": "1280x720",
        "seconds": "8",
        "poll_interval_seconds": 10,
        "download_variants": ["video", "thumbnail"],
        "style_notes": "polished storybook animation, gentle cinematic motion, soft textures, clear focal composition",
        "consistency_notes": "Pobi is a small round panda cub with soft black-and-white fur, bright curious eyes, and a tiny green scarf. Keep his face shape, body proportions, and scarf consistent across all shots.",
        "constraints": [
            "family-friendly children's story tone",
            "no text, no subtitles, no watermark",
            "clean anatomy and natural motion",
            "no scary imagery or aggressive action"
        ],
        "audio_notes": "Gentle bamboo forest ambience and soft birdsong, no spoken dialogue."
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
            "mood": "warm, calm, child-friendly"
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
            "mood": "playful and peaceful"
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
            "mood": "cozy and joyful"
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
            "mood": "kind, gentle, celebratory"
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
    render_parser.add_argument("--poll-interval", type=int, help="Polling interval seconds.")
    render_parser.add_argument("--timeout-seconds", type=int, help="Maximum wait time per shot.")

    character_parser = subparsers.add_parser("create-character", help="Create a reusable character from a reference video.")
    character_parser.add_argument("--video", required=True, help="Absolute or relative path to a reference video file.")
    character_parser.add_argument("--name", help="Optional character name.")
    character_parser.add_argument("--output", help="Optional path to write the character JSON.")

    download_parser = subparsers.add_parser("download", help="Download video, thumbnail, or spritesheet for a completed job.")
    download_parser.add_argument("--video-id", required=True, help="OpenAI video job ID.")
    download_parser.add_argument("--variant", default="video", help="video | thumbnail | spritesheet")
    download_parser.add_argument("--output", required=True, help="Output file path.")

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
    known_videos: Dict[str, str] = {}

    run_dir = ensure_dir(output_dir)
    requests_dir = ensure_dir(run_dir / "requests")
    shots_dir = ensure_dir(run_dir / "shots")

    run_manifest: Dict[str, Any] = {
        "project_title": project.get("title") or shotlist_path.stem,
        "shotlist_path": str(shotlist_path),
        "generated_at": utc_timestamp(),
        "dry_run": bool(args.dry_run),
        "shots": [],
    }

    write_json(run_dir / "shotlist.json", shotlist)

    client = None if args.dry_run else _client_from_env(args.timeout_seconds)
    poll_interval = args.poll_interval or int(project.get("poll_interval_seconds") or os.getenv("OPENAI_POLL_INTERVAL_SECONDS", "10"))
    timeout_seconds = args.timeout_seconds or int(os.getenv("OPENAI_VIDEO_TIMEOUT_SECONDS", "1800"))

    for shot in ordered_shots:
        if selected_ids and shot["id"] not in selected_ids:
            continue

        shot_dir = ensure_dir(shots_dir / f"{shot['order']:02d}-{slugify(shot['id'])}")
        shot_manifest_path = shot_dir / "shot-manifest.json"
        if args.skip_existing and shot_manifest_path.exists():
            previous = read_json(shot_manifest_path)
            if previous.get("status") == "completed" and previous.get("video_id"):
                known_videos[shot["id"]] = previous["video_id"]
                run_manifest["shots"].append(previous)
                print(f"Skipping existing shot: {shot['id']}")
                continue

        request_payload = build_shot_request(
            project=project,
            shot=shot,
            shotlist_dir=shotlist_path.parent,
            known_videos=known_videos,
        )
        request_path = requests_dir / f"{shot['order']:02d}-{slugify(shot['id'])}.json"
        write_json(request_path, request_payload)

        shot_manifest: Dict[str, Any] = {
            "id": shot["id"],
            "title": shot["title"],
            "mode": shot.get("mode", "generate"),
            "request_path": str(request_path),
            "generated_at": utc_timestamp(),
            "status": "dry_run" if args.dry_run else "queued",
            "downloads": [],
        }

        if args.dry_run:
            write_json(shot_manifest_path, shot_manifest)
            run_manifest["shots"].append(shot_manifest)
            print(f"Prepared request: {shot['id']}")
            continue

        assert client is not None
        creation_method = str(shot.get("mode") or "generate").lower()
        if creation_method == "generate":
            job = client.create_video(request_payload)
        elif creation_method == "extend":
            job = client.create_extension(request_payload)
        elif creation_method == "edit":
            job = client.create_edit(request_payload)
        else:
            raise ValueError(f"Unsupported shot mode: {creation_method}")

        shot_manifest["video_id"] = job["id"]
        shot_manifest["job_path"] = str(shot_dir / "job.json")
        write_json(Path(shot_manifest["job_path"]), job)
        print(f"Started {shot['id']}: {job['id']} ({job.get('status')})")

        final_job = client.wait_for_video(
            job["id"],
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
            on_update=lambda current, shot_id=shot["id"]: _print_progress(shot_id, current),
        )
        print("")
        write_json(Path(shot_manifest["job_path"]), final_job)
        shot_manifest["status"] = str(final_job.get("status"))

        if final_job.get("status") != "completed":
            shot_manifest["error"] = final_job.get("error")
            write_json(shot_manifest_path, shot_manifest)
            run_manifest["shots"].append(shot_manifest)
            print(f"Failed {shot['id']}: {final_job.get('error')}")
            continue

        known_videos[shot["id"]] = final_job["id"]
        variants = preferred_variants(project, shot, args.download_variants)
        for variant in variants:
            extension = _variant_extension(variant)
            output_path = shot_dir / f"{variant}{extension}"
            content = client.download_content(final_job["id"], variant=variant)
            write_bytes(output_path, content)
            shot_manifest["downloads"].append(
                {
                    "variant": variant,
                    "path": str(output_path),
                }
            )

        write_json(shot_manifest_path, shot_manifest)
        run_manifest["shots"].append(shot_manifest)
        print(f"Completed {shot['id']}: {final_job['id']}")

    write_json(run_dir / "run-manifest.json", run_manifest)
    print(f"Wrote run manifest: {run_dir / 'run-manifest.json'}")
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


def _variant_extension(variant: str) -> str:
    mapping = {
        "video": ".mp4",
        "thumbnail": ".webp",
        "spritesheet": ".jpg",
    }
    return mapping.get(variant, ".bin")


def _print_progress(shot_id: str, video: Dict[str, Any]) -> None:
    progress = video.get("progress", 0)
    status = video.get("status", "unknown")
    print(f"\r{shot_id}: {status} {progress}%", end="", flush=True)
