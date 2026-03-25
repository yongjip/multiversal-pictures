from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .agents import StoryAgentConfig, StoryToShotlistAgent, default_agent_model, default_agent_reasoning_effort
from .anchors import generate_anchor_images
from .dotenv import load_dotenv
from .files import ensure_dir, read_json, write_bytes, write_json
from .openai_images import OpenAIImagesClient
from .narration import build_narration_plan, render_narration_markdown
from .openai_responses import OpenAIResponsesClient
from .openai_speech import OpenAISpeechClient
from .openai_videos import OpenAIAPIError, OpenAIVideosClient
from .media import subtitle_layout_names, subtitle_preset_names
from .output_presets import default_output_preset_name, output_preset_names, preset_project_overrides, resolve_output_preset
from .production import StorybookProductionConfig, run_storybook_production
from .rendering import render_shots
from .review import review_rendered_shots
from .shotlist import load_shotlist, resolve_shot_order
from .stitching import stitch_run
from .subtitles import export_subtitles
from .tts import synthesize_narration
from .youtube import YouTubeUploadConfig, upload_youtube_video


SAMPLE_SHOTLIST = {
    "project": {
        "title": "Pobi Bamboo Breakfast",
        "output_preset": "storybook-landscape",
        "model": "sora-2-pro",
        "size": "1280x720",
        "seconds": "8",
        "poll_interval_seconds": 10,
        "download_variants": ["video", "thumbnail", "spritesheet"],
        "style_notes": "polished storybook animation, gentle cinematic motion, soft textures, clear focal composition",
        "format_guidance": "Keep the lower-center area visually clean for optional subtitles. Hold a strong hero composition that reads clearly in the first frame.",
        "narration_style": "warm, calm bedtime-story narrator",
        "narration_notes": "Keep each line short and clear enough to sit comfortably over the shot. Let narration carry the story so visuals stay expressive and simple.",
        "consistency_notes": "Pobi is a small round panda cub with soft black-and-white fur, bright curious eyes, and a tiny green scarf. Keep his face shape, body proportions, and scarf consistent across all shots.",
        "constraints": [
            "family-friendly children's story tone",
            "no text, no subtitles, no watermark",
            "clean anatomy and natural motion",
            "no scary imagery or aggressive action"
        ],
        "audio_notes": "Gentle bamboo forest ambience and soft birdsong under external narration.",
        "characters": [
            {
                "id": "pobi",
                "name": "Pobi",
                "description": "a small round panda cub with soft black-and-white fur, bright curious eyes, and a tiny green scarf",
                "continuity_rules": [
                    "keep Pobi's face shape and body proportions consistent",
                    "keep the small green scarf in every shot",
                    "preserve child-friendly expression and gentle demeanor"
                ]
            },
            {
                "id": "timi",
                "name": "Timi",
                "description": "a tiny red bird with a round body, bright eyes, and tidy smooth feathers",
                "continuity_rules": [
                    "keep the red bird compact and friendly, never realistic or threatening",
                    "preserve the bright red plumage and tiny beak"
                ]
            }
        ]
    },
    "shots": [
        {
            "id": "shot-01-morning",
            "title": "Pobi wakes up",
            "mode": "generate",
            "seconds": "8",
            "size": "1280x720",
            "priority": "high",
            "shot_type": "Wide storybook shot",
            "subject": "Pobi, a small round panda cub",
            "action": "wakes up in a bamboo bed, stretches his paws, and smiles sleepily",
            "setting": "a cozy bamboo hut on a green mountain at sunrise",
            "lighting": "soft golden sunrise light through paper windows",
            "camera_motion": "slow push-in",
            "mood": "warm, calm, child-friendly",
            "characters": ["pobi"],
            "start_frame": "Pobi curled asleep in a bamboo bed, green scarf visible beside his cheek, sunrise entering through paper windows.",
            "end_frame": "Pobi finishes stretching and looks toward the bright morning window with a gentle smile.",
            "must_keep": ["Pobi's green scarf", "cozy bamboo textures", "clear center framing on Pobi"],
            "negative_constraints": ["no extra characters", "no modern objects", "no messy clutter"],
            "narration_line": "On a soft green mountain, little Pobi opened his eyes to a brand-new morning.",
            "narration_cue": "start softly after the first half-second",
            "narration_offset_ms": 500,
            "sfx_notes": "light breeze, soft blanket rustle, tiny morning birds"
        },
        {
            "id": "shot-02-walk",
            "title": "Pobi walks to breakfast",
            "mode": "generate",
            "seconds": "8",
            "size": "1280x720",
            "priority": "normal",
            "shot_type": "Medium tracking shot",
            "subject": "Pobi, the same panda cub",
            "action": "waddles happily along a forest path toward a bamboo grove",
            "setting": "a misty bamboo forest with dew on the leaves",
            "lighting": "fresh morning light with soft haze",
            "camera_motion": "gentle side-tracking move",
            "mood": "playful and peaceful",
            "characters": ["pobi"],
            "start_frame": "Pobi steps out onto the forest path with the scarf bouncing lightly.",
            "end_frame": "Pobi reaches the edge of the bright bamboo grove and looks delighted.",
            "must_keep": ["same panda proportions and scarf", "morning mist", "clear path direction"],
            "negative_constraints": ["no crowding foliage over Pobi's face", "no sudden camera shake"],
            "narration_line": "His tummy gave a tiny rumble, so he set off to find the freshest bamboo in the forest.",
            "narration_cue": "land the second clause as he reaches the grove",
            "narration_offset_ms": 350,
            "sfx_notes": "gentle footsteps on leaves, soft forest ambience"
        },
        {
            "id": "shot-03-bamboo",
            "title": "Crunchy bamboo breakfast",
            "mode": "generate",
            "seconds": "8",
            "size": "1280x720",
            "priority": "high",
            "shot_type": "Close-up storybook shot",
            "subject": "Pobi, the same panda cub",
            "action": "takes a big crunchy bite of fresh bamboo and smiles with delight",
            "setting": "a bright bamboo grove filled with fresh green leaves",
            "lighting": "clean daylight with soft highlights on the leaves",
            "camera_motion": "subtle handheld-like drift",
            "mood": "cozy and joyful",
            "characters": ["pobi"],
            "start_frame": "Pobi raises a fresh bamboo stalk near his mouth, eyes bright and focused.",
            "end_frame": "Pobi smiles after the bite with crisp leaf texture and a joyful expression.",
            "must_keep": ["clean close-up on Pobi", "visible bamboo stalk", "gentle storybook styling"],
            "negative_constraints": ["no distorted teeth", "no messy mouth details", "no duplicate bamboo stalks"],
            "narration_line": "Crunch, crunch, crunch. Pobi's breakfast was cool, sweet, and delicious.",
            "narration_cue": "let the first crunch happen before the narration starts",
            "narration_offset_ms": 900,
            "sfx_notes": "clear bamboo crunch, leaf rustle, soft happy hum"
        },
        {
            "id": "shot-04-sharing",
            "title": "Sharing with friends",
            "mode": "generate",
            "seconds": "8",
            "size": "1280x720",
            "priority": "normal",
            "shot_type": "Wide ensemble shot",
            "subject": "Pobi, the same panda cub, with a tiny red bird, a rabbit, and a shy deer",
            "action": "shares berries, apples, and tender leaves with the forest friends",
            "setting": "a sunny clearing beside the bamboo grove",
            "lighting": "warm morning sunlight with soft sparkles through the trees",
            "camera_motion": "slow circular move around the group",
            "mood": "kind, gentle, celebratory",
            "characters": ["pobi", "timi"],
            "start_frame": "Pobi places fruit on a leaf table while the tiny red bird lands nearby and the other friends gather.",
            "end_frame": "The group settles into a warm shared breakfast tableau with Pobi centered.",
            "must_keep": ["Pobi centered in the group", "tiny red bird readable in frame", "sunny clearing mood"],
            "negative_constraints": ["no aggressive animal behavior", "no photorealistic deer", "no clutter over the subtitle safe area"],
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
    generate_parser.add_argument("--output-preset", choices=output_preset_names(), help="Preset for render size, duration, and subtitle defaults.")
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
    render_parser.add_argument("--output-preset", choices=output_preset_names(), help="Preset for render size, duration, and subtitle defaults.")
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

    anchor_parser = subparsers.add_parser("generate-anchors", help="Generate anchor images and write a derived shot list with input_reference paths.")
    anchor_parser.add_argument("--shotlist", required=True, help="Shot list JSON path.")
    anchor_parser.add_argument("--output-dir", required=True, help="Output directory for raw and normalized anchor assets.")
    anchor_parser.add_argument("--output-shotlist", help="Optional path for the derived shot list. Defaults to <output-dir>/anchored-shotlist.json.")
    anchor_parser.add_argument("--model", help="Override image model.")
    anchor_parser.add_argument("--quality", help="Override image quality.")
    anchor_parser.add_argument(
        "--replace-existing-input-reference",
        action="store_true",
        help="Regenerate anchor images even when a shot already has input_reference configured.",
    )

    review_parser = subparsers.add_parser("review-shots", help="Review rendered shots, score candidates, and optionally create extra best-of candidates.")
    review_parser.add_argument("--run-dir", required=True, help="Render run directory containing run-manifest.json and shotlist.json.")
    review_parser.add_argument("--only", help="Comma-separated shot IDs to review.")
    review_parser.add_argument("--model", help="Override the review model.")
    review_parser.add_argument("--threshold", type=float, help="Minimum overall score required to auto-keep the selected candidate.")
    review_parser.add_argument("--best-of", type=int, help="Maximum candidate count per eligible shot.")
    review_parser.add_argument("--mode", choices=["score_only", "repair"], help="Score existing renders only, or allow repair rerenders for low-score shots.")
    review_parser.add_argument("--poll-interval", type=int, help="Polling interval seconds for extra candidate renders.")
    review_parser.add_argument("--timeout-seconds", type=int, help="Maximum wait time per extra candidate render.")
    review_parser.add_argument("--reasoning-effort", choices=["minimal", "low", "medium", "high"], help="Override reasoning effort for the review model.")

    produce_parser = subparsers.add_parser("produce", help="Run the storybook pipeline end-to-end and overlap narration with rendering.")
    produce_input = produce_parser.add_mutually_exclusive_group(required=True)
    produce_input.add_argument("--shotlist", help="Existing shot list JSON path.")
    produce_input.add_argument("--prompt", help="Story premise or creative prompt.")
    produce_input.add_argument("--prompt-file", help="Path to a text file containing the story premise.")
    produce_parser.add_argument("--output", required=True, help="Output run directory.")
    produce_parser.add_argument("--final-output", help="Optional final stitched video path. Defaults to <output>/story.mp4.")
    produce_parser.add_argument("--brief-output", help="Optional path for the intermediate story brief JSON when generating from a prompt.")
    produce_parser.add_argument("--trace-output", help="Optional path for the raw agent trace JSON when generating from a prompt.")
    produce_parser.add_argument("--audience", default="children and families", help="Target audience description.")
    produce_parser.add_argument("--language", default="en", help="Target language for user-facing text.")
    produce_parser.add_argument("--style", default="polished storybook animation, gentle cinematic motion, soft textures", help="Desired visual style.")
    produce_parser.add_argument("--shots", type=int, default=4, help="Target shot count when generating from a prompt.")
    produce_parser.add_argument("--model", help="Override the planning model.")
    produce_parser.add_argument("--reasoning-effort", choices=["minimal", "low", "medium", "high"], help="Override reasoning effort for the planning model.")
    produce_parser.add_argument("--output-preset", choices=output_preset_names(), help="Preset for render size, duration, and subtitle defaults.")
    produce_parser.add_argument("--size", help="Default output size to write into the shot list when generating from a prompt.")
    produce_parser.add_argument("--seconds", help="Default clip length to write into the shot list when generating from a prompt.")
    produce_parser.add_argument("--production-mode", choices=["preview", "balanced", "master"], help="Production defaults for speed vs quality. Defaults to balanced.")
    produce_parser.add_argument("--resume", action="store_true", help="Resume a partially completed production run from existing manifests.")
    produce_parser.add_argument("--stop-after", choices=["anchors", "narration", "render", "review", "stitch"], help="Stop after a production phase and keep the incremental manifest.")
    produce_parser.add_argument("--download-variants", help="Override variants, e.g. video,thumbnail.")
    produce_anchor_group = produce_parser.add_mutually_exclusive_group()
    produce_anchor_group.add_argument("--with-anchors", dest="with_anchors", action="store_const", const=True, help="Generate GPT Image anchor frames and inject them as input_reference before rendering.")
    produce_anchor_group.add_argument("--no-anchors", dest="with_anchors", action="store_const", const=False, help="Disable anchor generation even when the selected production mode would enable it.")
    produce_parser.add_argument("--image-model", help="Override image model for anchor generation.")
    produce_parser.add_argument("--image-quality", help="Override image quality for anchor generation.")
    produce_parser.add_argument("--with-review", action="store_true", help="Run the review loop after rendering and auto-select the best candidate.")
    produce_parser.add_argument("--review-mode", choices=["score_only", "repair"], help="Score-only review or repair review with limited rerenders.")
    produce_parser.add_argument("--review-model", help="Override review model.")
    produce_parser.add_argument("--review-threshold", type=float, help="Minimum review score required to auto-keep a shot.")
    produce_parser.add_argument("--review-best-of", type=int, help="Maximum candidate count per eligible shot during review.")
    produce_parser.add_argument("--skip-existing", action="store_true", help="Skip shots with an existing completed manifest in the output run directory.")
    produce_parser.add_argument("--jobs", type=int, help="Number of shots to render concurrently. Defaults come from the selected production mode.")
    produce_parser.add_argument("--poll-interval", type=int, help="Polling interval seconds.")
    produce_parser.add_argument("--timeout-seconds", type=int, help="Maximum wait time per shot.")
    produce_parser.add_argument("--narration-model", help="Override TTS model.")
    produce_parser.add_argument("--narration-voice", help="Override TTS voice.")
    produce_parser.add_argument("--narration-response-format", choices=["mp3", "wav", "opus", "aac", "flac", "pcm"], help="Override TTS response format.")
    produce_parser.add_argument("--default-offset-ms", type=int, help="Fallback narration offset when a shot does not define one.")
    produce_parser.add_argument("--background-music", help="Optional background music file to mix into the stitched output.")
    produce_parser.add_argument("--subtitle-file", help="Optional SRT or VTT subtitle file to use instead of the generated captions.")
    produce_parser.add_argument("--subtitle-language", default="eng", help="Subtitle language tag for the embedded subtitle track.")
    produce_parser.add_argument("--burn-subtitles", action="store_true", help="Burn subtitle text into video frames instead of embedding a subtitle track.")
    produce_parser.add_argument("--subtitle-preset", choices=subtitle_preset_names(), help="Preset style for burned subtitles.")
    produce_parser.add_argument("--subtitle-layout", choices=subtitle_layout_names(), help="Layout profile for burned subtitles.")
    produce_parser.add_argument("--subtitle-style", help="Optional ffmpeg ASS force_style overrides for burned subtitles.")
    produce_parser.add_argument("--clip-audio-volume", type=float, help="Mix level for original clip audio when narration is present.")
    produce_parser.add_argument("--narration-volume", type=float, help="Mix level for narration audio.")
    produce_parser.add_argument("--music-volume", type=float, help="Mix level for background music.")
    produce_parser.add_argument("--mute-clip-audio", action="store_true", help="Mute original clip audio when mixing narration.")
    produce_parser.add_argument("--no-music-ducking", action="store_true", help="Do not duck background music under narration.")
    produce_parser.add_argument("--overwrite", action="store_true", help="Allow overwriting an existing final stitched output.")
    produce_parser.add_argument("--upload-youtube", action="store_true", help="Upload the final stitched video to YouTube after production completes.")
    _add_youtube_upload_arguments(produce_parser, option_prefix="youtube-", dest_prefix="youtube_", include_video_source=False)

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
    subtitle_parser.add_argument("--max-words-per-cue", type=int, help="Maximum words to keep in a single subtitle cue. Defaults are layout-aware.")

    stitch_parser = subparsers.add_parser("stitch-run", help="Combine completed shot videos from a render run into one video.")
    stitch_parser.add_argument("--run-dir", required=True, help="Render run directory containing run-manifest.json.")
    stitch_parser.add_argument("--output", required=True, help="Output stitched video path.")
    stitch_parser.add_argument("--overwrite", action="store_true", help="Allow overwriting an existing output file.")
    stitch_parser.add_argument("--output-preset", choices=output_preset_names(), help="Preset for subtitle defaults on stitched outputs.")
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

    youtube_parser = subparsers.add_parser("upload-youtube", help="Upload a completed video to YouTube using OAuth 2.0.")
    _add_youtube_upload_arguments(youtube_parser)

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
        if args.command == "generate-anchors":
            return cmd_generate_anchors(args)
        if args.command == "review-shots":
            return cmd_review_shots(args)
        if args.command == "produce":
            return cmd_produce(args)
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
        if args.command == "upload-youtube":
            return cmd_upload_youtube(args)
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
    resolved_output_preset = resolve_output_preset(args.output_preset or default_output_preset_name())
    size = args.size or (resolved_output_preset["size"] if resolved_output_preset else os.getenv("OPENAI_VIDEO_SIZE", "1280x720"))
    seconds = args.seconds or (resolved_output_preset["seconds"] if resolved_output_preset else os.getenv("OPENAI_VIDEO_SECONDS", "8"))

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
            output_preset=resolved_output_preset["name"] if resolved_output_preset else None,
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
    base_project = dict(shotlist.get("project") or {})
    resolved_output_preset = resolve_output_preset(
        args.output_preset or base_project.get("output_preset") or default_output_preset_name()
    )
    project = preset_project_overrides(project=base_project, preset=resolved_output_preset)
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
                subtitle_preset=args.subtitle_preset or str(project.get("subtitle_preset") or (resolved_output_preset["subtitle_preset"] if resolved_output_preset else "")) or None,
                subtitle_layout=args.subtitle_layout or str(project.get("subtitle_layout") or (resolved_output_preset["subtitle_layout"] if resolved_output_preset else "")) or None,
                subtitle_style=args.subtitle_style,
                clip_audio_volume=0.0 if args.mute_clip_audio else args.clip_audio_volume,
                narration_volume=args.narration_volume,
                music_volume=args.music_volume,
                duck_music_under_narration=not bool(args.no_music_ducking),
            )
            print(f"Wrote stitched video: {stitch_manifest['output_path']}")
    return 0


def cmd_generate_anchors(args: argparse.Namespace) -> int:
    shotlist_path = Path(args.shotlist).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_shotlist_path = Path(args.output_shotlist).resolve() if args.output_shotlist else output_dir / "anchored-shotlist.json"
    manifest = generate_anchor_images(
        shotlist_path=shotlist_path,
        output_dir=output_dir,
        output_shotlist_path=output_shotlist_path,
        client=_image_client_from_env(),
        model=args.model or os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1.5"),
        quality=args.quality or os.getenv("OPENAI_IMAGE_QUALITY", "high"),
        replace_existing_input_reference=bool(args.replace_existing_input_reference),
    )
    print(f"Wrote anchor manifest: {output_dir / 'anchors-manifest.json'}")
    print(f"Wrote anchored shot list: {output_shotlist_path}")
    print(f"Processed shots: {len(manifest.get('shots') or [])}")
    return 0


def cmd_review_shots(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    review_mode = str(args.mode or os.getenv("STORYBOOK_REVIEW_MODE", "score_only")).strip().lower()
    threshold = float(args.threshold if args.threshold is not None else os.getenv("STORYBOOK_QA_THRESHOLD", "0.78"))
    default_best_of = 2 if review_mode == "repair" else 1
    best_of = int(args.best_of if args.best_of is not None else os.getenv("STORYBOOK_QA_BEST_OF", str(default_best_of)))
    poll_interval = int(args.poll_interval if args.poll_interval is not None else os.getenv("OPENAI_POLL_INTERVAL_SECONDS", "10"))
    timeout_seconds = int(args.timeout_seconds if args.timeout_seconds is not None else os.getenv("OPENAI_VIDEO_TIMEOUT_SECONDS", "1800"))
    manifest = review_rendered_shots(
        run_dir=run_dir,
        response_client=_responses_client_from_env(),
        video_client=_client_from_env(timeout_seconds),
        model=args.model or os.getenv("STORYBOOK_QA_MODEL", default_agent_model()),
        mode=review_mode,
        threshold=threshold,
        best_of=best_of,
        poll_interval=poll_interval,
        timeout_seconds=timeout_seconds,
        selected_ids=_selected_ids(args.only),
        reasoning_effort=args.reasoning_effort or default_agent_reasoning_effort(),
    )
    reviewed_shots = manifest.get("shots") or []
    kept = sum(1 for item in reviewed_shots if item.get("recommended_action") == "keep")
    edited = sum(1 for item in reviewed_shots if item.get("recommended_action") == "edit")
    rerender = sum(1 for item in reviewed_shots if item.get("recommended_action") == "rerender")
    print(f"Wrote review manifest: {run_dir / 'review-manifest.json'}")
    print(f"Reviewed shots: {len(reviewed_shots)}")
    print(f"Keep: {kept} | Edit: {edited} | Rerender: {rerender}")
    return 0


def cmd_produce(args: argparse.Namespace) -> int:
    run_dir = Path(args.output).resolve()
    final_output_path = Path(args.final_output).resolve() if args.final_output else run_dir / "story.mp4"
    default_offset_ms = args.default_offset_ms or int(os.getenv("STORYBOOK_NARRATION_OFFSET_MS", "500"))
    manifest = run_storybook_production(
        StorybookProductionConfig(
            run_dir=run_dir,
            output_path=final_output_path,
            prompt=args.prompt,
            prompt_file=Path(args.prompt_file).resolve() if args.prompt_file else None,
            shotlist_path=Path(args.shotlist).resolve() if args.shotlist else None,
            brief_output_path=Path(args.brief_output).resolve() if args.brief_output else None,
            trace_output_path=Path(args.trace_output).resolve() if args.trace_output else None,
            audience=args.audience,
            language=args.language,
            style=args.style,
            shot_count=max(1, int(args.shots or 1)),
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            output_preset=args.output_preset,
            size=args.size,
            seconds=args.seconds,
            jobs=max(1, int(args.jobs)) if args.jobs else None,
            download_variants=args.download_variants,
            with_anchors=args.with_anchors,
            image_model=args.image_model,
            image_quality=args.image_quality,
            with_review=bool(args.with_review),
            review_mode=args.review_mode,
            review_model=args.review_model,
            review_threshold=args.review_threshold,
            review_best_of=args.review_best_of,
            skip_existing=bool(args.skip_existing),
            poll_interval=args.poll_interval,
            timeout_seconds=args.timeout_seconds,
            narration_model=args.narration_model,
            narration_voice=args.narration_voice,
            narration_response_format=args.narration_response_format,
            default_offset_ms=default_offset_ms,
            subtitle_file=Path(args.subtitle_file).resolve() if args.subtitle_file else None,
            subtitle_language=args.subtitle_language,
            burn_subtitles=bool(args.burn_subtitles),
            subtitle_preset=args.subtitle_preset,
            subtitle_layout=args.subtitle_layout,
            subtitle_style=args.subtitle_style,
            clip_audio_volume=args.clip_audio_volume,
            narration_volume=args.narration_volume,
            music_volume=args.music_volume,
            background_music_path=Path(args.background_music).resolve() if args.background_music else None,
            mute_clip_audio=bool(args.mute_clip_audio),
            no_music_ducking=bool(args.no_music_ducking),
            overwrite=bool(args.overwrite),
            production_mode=args.production_mode,
            resume=bool(args.resume),
            stop_after=args.stop_after,
        )
    )
    print(f"Wrote production manifest: {run_dir / 'production-manifest.json'}")
    shotlist_path = manifest.get("shotlist_path") or manifest.get("current_shotlist_path") or manifest.get("input_shotlist_path")
    if shotlist_path:
        print(f"Wrote shot list: {shotlist_path}")
    if manifest.get("anchor_manifest"):
        print(f"Wrote anchor manifest: {run_dir / 'anchors' / 'anchors-manifest.json'}")
    narration_manifest = manifest.get("narration_manifest") or {}
    if narration_manifest.get("master_audio_path"):
        print(f"Wrote narration audio: {narration_manifest['master_audio_path']}")
    if manifest.get("render_manifest") or (run_dir / "run-manifest.json").exists():
        print(f"Wrote run manifest: {run_dir / 'run-manifest.json'}")
    if manifest.get("review_manifest"):
        print(f"Wrote review manifest: {run_dir / 'review-manifest.json'}")
    if manifest.get("completed_stage") == "stitch" and manifest.get("output_path"):
        print(f"Wrote stitched video: {manifest['output_path']}")
    else:
        print(f"Stopped after stage: {manifest.get('completed_stage')}")
    if args.upload_youtube:
        if manifest.get("completed_stage") != "stitch" or not manifest.get("output_path"):
            raise ValueError("YouTube upload requires the stitch stage to complete.")
        upload_manifest_path, upload_manifest = _run_youtube_upload(
            video_path=Path(manifest["output_path"]).resolve(),
            shotlist_path=Path(manifest["shotlist_path"]).resolve() if manifest.get("shotlist_path") else None,
            title=args.youtube_title,
            description=args.youtube_description,
            description_file=args.youtube_description_file,
            tags=args.youtube_tags,
            category_id=args.youtube_category_id,
            privacy_status=args.youtube_privacy_status,
            client_secrets=args.youtube_client_secrets,
            token_file=args.youtube_token_file,
            manifest_output=args.youtube_manifest_output,
            no_browser=bool(args.youtube_no_browser),
            default_manifest_output=run_dir / "youtube-upload.json",
        )
        print(f"Wrote YouTube upload manifest: {upload_manifest_path}")
        print(f"YouTube video URL: {upload_manifest['video_url']}")
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
    model = args.model or os.getenv("OPENAI_TTS_MODEL", "tts-1-hd")
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
        max_words_per_cue=max(1, int(args.max_words_per_cue)) if args.max_words_per_cue else None,
    )
    print(f"Wrote subtitles: {output_path}")
    print(f"Cue count: {subtitle_plan['cue_count']}")
    return 0


def cmd_stitch_run(args: argparse.Namespace) -> int:
    resolved_output_preset = resolve_output_preset(args.output_preset or default_output_preset_name())
    stitch_manifest = stitch_run(
        run_dir=Path(args.run_dir).resolve(),
        output_path=Path(args.output).resolve(),
        overwrite=bool(args.overwrite),
        narration_audio_path=Path(args.narration_audio).resolve() if args.narration_audio else None,
        background_music_path=Path(args.background_music).resolve() if args.background_music else None,
        subtitle_path=Path(args.subtitle_file).resolve() if args.subtitle_file else None,
        subtitle_language=args.subtitle_language,
        burn_subtitles=bool(args.burn_subtitles),
        subtitle_preset=args.subtitle_preset or (resolved_output_preset["subtitle_preset"] if resolved_output_preset else None),
        subtitle_layout=args.subtitle_layout or (resolved_output_preset["subtitle_layout"] if resolved_output_preset else None),
        subtitle_style=args.subtitle_style,
        clip_audio_volume=0.0 if args.mute_clip_audio else args.clip_audio_volume,
        narration_volume=args.narration_volume,
        music_volume=args.music_volume,
        duck_music_under_narration=not bool(args.no_music_ducking),
    )
    print(f"Wrote stitched video: {stitch_manifest['output_path']}")
    return 0


def cmd_upload_youtube(args: argparse.Namespace) -> int:
    video_path, shotlist_path, run_dir = _resolve_youtube_video_source(
        video=args.video,
        run_dir=args.run_dir,
    )
    default_manifest_output = (run_dir / "youtube-upload.json") if run_dir else video_path.with_suffix(".youtube-upload.json")
    upload_manifest_path, upload_manifest = _run_youtube_upload(
        video_path=video_path,
        shotlist_path=shotlist_path,
        title=args.title,
        description=args.description,
        description_file=args.description_file,
        tags=args.tags,
        category_id=args.category_id,
        privacy_status=args.privacy_status,
        client_secrets=args.client_secrets,
        token_file=args.token_file,
        manifest_output=args.manifest_output,
        no_browser=bool(args.no_browser),
        default_manifest_output=default_manifest_output,
    )
    print(f"Wrote YouTube upload manifest: {upload_manifest_path}")
    print(f"YouTube video URL: {upload_manifest['video_url']}")
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


def _add_youtube_upload_arguments(
    parser: argparse.ArgumentParser,
    *,
    option_prefix: str = "",
    dest_prefix: str = "",
    include_video_source: bool = True,
) -> None:
    if include_video_source:
        source_group = parser.add_mutually_exclusive_group(required=True)
        source_group.add_argument(
            f"--{option_prefix}video",
            dest=f"{dest_prefix}video",
            help="Video file path to upload.",
        )
        source_group.add_argument(
            f"--{option_prefix}run-dir",
            dest=f"{dest_prefix}run_dir",
            help="Run directory containing production-manifest.json, stitch-manifest.json, or story.mp4.",
        )

    parser.add_argument(f"--{option_prefix}title", dest=f"{dest_prefix}title", help="YouTube video title. Defaults to the project title or file stem.")
    parser.add_argument(f"--{option_prefix}description", dest=f"{dest_prefix}description", help="YouTube video description.")
    parser.add_argument(f"--{option_prefix}description-file", dest=f"{dest_prefix}description_file", help="Path to a text file containing the YouTube description.")
    parser.add_argument(f"--{option_prefix}tags", dest=f"{dest_prefix}tags", help="Comma-separated YouTube tags.")
    parser.add_argument(f"--{option_prefix}category-id", dest=f"{dest_prefix}category_id", help="YouTube category ID. Defaults to 22 (People & Blogs).")
    parser.add_argument(
        f"--{option_prefix}privacy-status",
        dest=f"{dest_prefix}privacy_status",
        choices=["public", "private", "unlisted"],
        help="YouTube visibility for the uploaded video.",
    )
    parser.add_argument(
        f"--{option_prefix}client-secrets",
        dest=f"{dest_prefix}client_secrets",
        help="OAuth desktop client JSON downloaded from Google Cloud.",
    )
    parser.add_argument(
        f"--{option_prefix}token-file",
        dest=f"{dest_prefix}token_file",
        help="Path to store the YouTube OAuth token JSON.",
    )
    parser.add_argument(
        f"--{option_prefix}manifest-output",
        dest=f"{dest_prefix}manifest_output",
        help="Optional path to write the YouTube upload manifest JSON.",
    )
    parser.add_argument(
        f"--{option_prefix}no-browser",
        dest=f"{dest_prefix}no_browser",
        action="store_true",
        help="Print the OAuth consent URL instead of opening a browser automatically.",
    )


def _run_youtube_upload(
    *,
    video_path: Path,
    shotlist_path: Optional[Path],
    title: Optional[str],
    description: Optional[str],
    description_file: Optional[str],
    tags: Optional[str],
    category_id: Optional[str],
    privacy_status: Optional[str],
    client_secrets: Optional[str],
    token_file: Optional[str],
    manifest_output: Optional[str],
    no_browser: bool,
    default_manifest_output: Path,
) -> tuple[Path, Dict[str, Any]]:
    resolved_video_path = video_path.expanduser().resolve()
    resolved_shotlist_path = shotlist_path.expanduser().resolve() if shotlist_path else None
    resolved_title = _resolve_youtube_title(title=title, video_path=resolved_video_path, shotlist_path=resolved_shotlist_path)
    resolved_description = _read_optional_text(value=description, file_path=description_file)
    resolved_tags = _parse_csv(tags)
    resolved_category_id = (category_id or os.getenv("YOUTUBE_CATEGORY_ID") or "22").strip()
    resolved_privacy_status = (privacy_status or os.getenv("YOUTUBE_PRIVACY_STATUS") or "private").strip().lower()
    client_secrets_value = client_secrets or os.getenv("YOUTUBE_CLIENT_SECRETS_FILE")
    if not client_secrets_value:
        raise ValueError("YouTube upload requires --client-secrets or YOUTUBE_CLIENT_SECRETS_FILE.")

    token_path = Path(
        token_file or os.getenv("YOUTUBE_TOKEN_FILE") or (Path.home() / ".multiversal-pictures" / "youtube-token.json")
    ).expanduser()
    upload_manifest = upload_youtube_video(
        YouTubeUploadConfig(
            video_path=resolved_video_path,
            client_secrets_path=Path(client_secrets_value).expanduser(),
            token_path=token_path,
            title=resolved_title,
            description=resolved_description,
            tags=resolved_tags,
            category_id=resolved_category_id,
            privacy_status=resolved_privacy_status,
            open_browser=not no_browser,
        )
    )
    manifest_path = Path(manifest_output).expanduser().resolve() if manifest_output else default_manifest_output.expanduser().resolve()
    write_json(manifest_path, upload_manifest)
    return manifest_path, upload_manifest


def _resolve_youtube_video_source(*, video: Optional[str], run_dir: Optional[str]) -> tuple[Path, Optional[Path], Optional[Path]]:
    if video:
        resolved_video_path = Path(video).expanduser().resolve()
        if not resolved_video_path.exists():
            raise FileNotFoundError(resolved_video_path)
        return resolved_video_path, None, None

    if not run_dir:
        raise ValueError("Either --video or --run-dir is required.")

    resolved_run_dir = Path(run_dir).expanduser().resolve()
    if not resolved_run_dir.exists():
        raise FileNotFoundError(resolved_run_dir)

    production_manifest_path = resolved_run_dir / "production-manifest.json"
    if production_manifest_path.exists():
        production_manifest = read_json(production_manifest_path)
        output_path = Path(str(production_manifest.get("output_path") or resolved_run_dir / "story.mp4")).expanduser().resolve()
        shotlist_path = Path(str(production_manifest["shotlist_path"])).expanduser().resolve() if production_manifest.get("shotlist_path") else None
        if not output_path.exists():
            raise FileNotFoundError(output_path)
        return output_path, shotlist_path, resolved_run_dir

    stitch_manifest_path = resolved_run_dir / "stitch-manifest.json"
    if stitch_manifest_path.exists():
        stitch_manifest = read_json(stitch_manifest_path)
        output_path = Path(str(stitch_manifest.get("output_path") or resolved_run_dir / "story.mp4")).expanduser().resolve()
        shotlist_path = (resolved_run_dir / "shotlist.json") if (resolved_run_dir / "shotlist.json").exists() else None
        if not output_path.exists():
            raise FileNotFoundError(output_path)
        return output_path, shotlist_path, resolved_run_dir

    default_video_path = resolved_run_dir / "story.mp4"
    if default_video_path.exists():
        shotlist_path = (resolved_run_dir / "shotlist.json") if (resolved_run_dir / "shotlist.json").exists() else None
        return default_video_path, shotlist_path, resolved_run_dir

    raise FileNotFoundError(f"Could not find a stitched video in {resolved_run_dir}.")


def _resolve_youtube_title(*, title: Optional[str], video_path: Path, shotlist_path: Optional[Path]) -> str:
    if title and title.strip():
        return title.strip()

    if shotlist_path and shotlist_path.exists():
        try:
            shotlist = load_shotlist(shotlist_path)
        except Exception:
            shotlist = None
        if shotlist:
            project_title = str((shotlist.get("project") or {}).get("title") or "").strip()
            if project_title:
                return project_title

    return _humanize_video_stem(video_path.stem)


def _read_optional_text(*, value: Optional[str], file_path: Optional[str]) -> str:
    if value and file_path:
        raise ValueError("Choose either a direct description or --description-file, not both.")
    if value:
        return value.strip()
    if file_path:
        return Path(file_path).expanduser().resolve().read_text(encoding="utf-8").strip()
    return ""


def _parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _humanize_video_stem(value: str) -> str:
    parts = [part for part in value.replace("_", " ").replace("-", " ").split() if part]
    if not parts:
        return "Story Video"
    return " ".join(part.capitalize() if part.islower() else part for part in parts)
