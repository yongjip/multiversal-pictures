from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .files import utc_timestamp, write_json
from .openai_responses import OpenAIResponsesClient, extract_response_json
from .output_presets import resolve_output_preset
from .shotlist import normalize_generated_shotlist


@dataclass
class StoryAgentConfig:
    prompt: str
    output_path: Path
    audience: str
    language: str
    visual_style: str
    shot_count: int
    model: str
    video_model: str
    reasoning_effort: Optional[str]
    size: str
    seconds: str
    output_preset: Optional[str] = None
    dry_run: bool = False
    brief_output_path: Optional[Path] = None
    trace_output_path: Optional[Path] = None


class StoryToShotlistAgent:
    def __init__(self, client: Optional[OpenAIResponsesClient]):
        self.client = client

    def run(self, config: StoryAgentConfig) -> Dict[str, Any]:
        story_brief_request = self._build_story_brief_request(config)
        shotlist_request = self._build_shotlist_request(config)

        trace: Dict[str, Any] = {
            "generated_at": utc_timestamp(),
            "agent": "story-to-shotlist",
            "model": config.model,
            "video_model": config.video_model,
            "reasoning_effort": config.reasoning_effort,
            "story_brief_request": story_brief_request,
            "shotlist_request_template": shotlist_request,
        }

        if config.dry_run:
            if config.trace_output_path:
                write_json(config.trace_output_path, trace)
            return {
                "dry_run": True,
                "trace": trace,
            }

        if self.client is None:
            raise ValueError("OpenAI responses client is required unless --dry-run is used.")

        story_brief_response = self.client.create_structured_response(
            model=config.model,
            instructions=story_brief_request["instructions"],
            input_messages=story_brief_request["input"],
            schema_name="story_brief",
            schema=_story_brief_schema(),
            reasoning_effort=config.reasoning_effort,
        )
        story_brief = extract_response_json(story_brief_response)

        shotlist_request["input"].append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": _format_story_brief_for_model(story_brief),
                    }
                ],
            }
        )

        shotlist_response = self.client.create_structured_response(
            model=config.model,
            instructions=shotlist_request["instructions"],
            input_messages=shotlist_request["input"],
            schema_name="render_shotlist",
            schema=_shotlist_schema(),
            reasoning_effort=config.reasoning_effort,
        )
        shotlist = extract_response_json(shotlist_response)
        resolved_output_preset = resolve_output_preset(config.output_preset) if config.output_preset else None
        shotlist = normalize_generated_shotlist(
            shotlist,
            video_model=config.video_model,
            size=config.size,
            seconds=config.seconds,
            download_variants=["video", "thumbnail"],
            output_preset=config.output_preset,
            subtitle_preset=resolved_output_preset.get("subtitle_preset") if resolved_output_preset else None,
            subtitle_layout=resolved_output_preset.get("subtitle_layout") if resolved_output_preset else None,
            format_guidance=resolved_output_preset.get("format_guidance") if resolved_output_preset else None,
        )

        trace["story_brief_response"] = story_brief_response
        trace["shotlist_request"] = shotlist_request
        trace["shotlist_response"] = shotlist_response

        write_json(config.output_path, shotlist)
        if config.brief_output_path:
            write_json(config.brief_output_path, story_brief)
        if config.trace_output_path:
            write_json(config.trace_output_path, trace)

        return {
            "dry_run": False,
            "story_brief": story_brief,
            "shotlist": shotlist,
            "trace": trace,
        }

    def _build_story_brief_request(self, config: StoryAgentConfig) -> Dict[str, Any]:
        instructions = (
            "You are the Story Agent for Multiversal Pictures. "
            "Turn a rough story premise into a production-ready visual story brief for a narration-led storybook video. "
            "Prioritize visual clarity, character continuity, emotional beats, and family-friendly storytelling. "
            "Assume the final film uses external narration instead of character lip-sync dialogue. "
            "Keep internal IDs short and stable. Use the user's target language for user-facing fields."
        )
        user_prompt = (
            f"Story premise:\n{config.prompt}\n\n"
            f"Target audience: {config.audience}\n"
            f"Language: {config.language}\n"
            f"Desired visual style: {config.visual_style}\n"
            f"Target number of shots: {config.shot_count}\n"
            "Return a brief that another agent can use to plan concrete renderable shots with concise voiceover."
        )
        return {
            "instructions": instructions,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                }
            ],
        }

    def _build_shotlist_request(self, config: StoryAgentConfig) -> Dict[str, Any]:
        instructions = (
            "You are the Shot Planner Agent for Multiversal Pictures. "
            "Convert the story brief into a renderable shot list for OpenAI video generation. "
            "This project specializes in narration-led storybook videos, so visuals should support external voiceover rather than spoken dialogue inside the clip. "
            "Every shot must be concrete, visually specific, and directly usable by a downstream renderer. "
            "Preserve character continuity and keep the project family-friendly. "
            "Use the requested language for shot titles and audience-facing text, but keep IDs machine-safe."
        )
        planner_prompt = (
            "Create the final shot list. "
            f"Use default video model {config.video_model}, size {config.size}, and seconds {config.seconds} unless a shot clearly needs an override. "
            "Valid download variants are video, thumbnail, and spritesheet. "
            f"Generate exactly {config.shot_count} shots unless the brief clearly requires one extra closing beat. "
            "Include continuity notes in the project block and make sure each shot has strong shot_type, subject, action, setting, lighting, camera_motion, and mood fields. "
            "For every shot include a short narration_line, a narration_cue describing when the line lands, a narration_offset_ms integer, and sfx_notes for the sound mix. "
            "Do not rely on visible talking or lip-synced dialogue."
        )
        if config.output_preset:
            preset = resolve_output_preset(config.output_preset)
            planner_prompt += f" Output preset: {preset['name']}. {preset['format_guidance']}"
        return {
            "instructions": instructions,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": planner_prompt}],
                }
            ],
        }


def default_agent_model() -> str:
    return os.getenv("OPENAI_AGENT_MODEL", "gpt-5.4")


def default_agent_reasoning_effort() -> str:
    return os.getenv("OPENAI_AGENT_REASONING_EFFORT", "medium")


def _format_story_brief_for_model(story_brief: Dict[str, Any]) -> str:
    return (
        "Use this story brief as the planning source of truth:\n\n"
        f"{json.dumps(story_brief, ensure_ascii=False, indent=2)}"
    )


def _story_brief_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "logline": {"type": "string"},
            "audience": {"type": "string"},
            "language": {"type": "string"},
            "story_goal": {"type": "string"},
            "moral": {"type": "string"},
            "visual_style": {"type": "string"},
            "narration_style": {"type": "string"},
            "narration_notes": {"type": "string"},
            "consistency_notes": {"type": "string"},
            "audio_notes": {"type": "string"},
            "characters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "continuity_rules": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["id", "name", "description", "continuity_rules"],
                },
            },
            "beats": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "beat_id": {"type": "string"},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "emotional_goal": {"type": "string"},
                        "narration_focus": {"type": "string"},
                        "key_visuals": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["beat_id", "title", "summary", "emotional_goal", "narration_focus", "key_visuals"],
                },
            },
        },
        "required": [
            "title",
            "logline",
            "audience",
            "language",
            "story_goal",
            "moral",
            "visual_style",
            "narration_style",
            "narration_notes",
            "consistency_notes",
            "audio_notes",
            "characters",
            "beats",
        ],
    }


def _shotlist_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "project": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "model": {"type": "string"},
                    "size": {"type": "string"},
                    "seconds": {"type": "string"},
                    "download_variants": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "style_notes": {"type": "string"},
                    "narration_style": {"type": "string"},
                    "narration_notes": {"type": "string"},
                    "consistency_notes": {"type": "string"},
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "audio_notes": {"type": "string"},
                },
                "required": [
                    "title",
                    "model",
                    "size",
                    "seconds",
                    "download_variants",
                    "style_notes",
                    "narration_style",
                    "narration_notes",
                    "consistency_notes",
                    "constraints",
                    "audio_notes",
                ],
            },
            "shots": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "shot_type": {"type": "string"},
                        "subject": {"type": "string"},
                        "action": {"type": "string"},
                        "setting": {"type": "string"},
                        "lighting": {"type": "string"},
                        "camera_motion": {"type": "string"},
                        "mood": {"type": "string"},
                        "narration_line": {"type": "string"},
                        "narration_cue": {"type": "string"},
                        "narration_offset_ms": {"type": "integer"},
                        "sfx_notes": {"type": "string"},
                        "characters": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "id": {"type": "string"},
                                },
                                "required": ["id"],
                            },
                        },
                        "constraints": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "id",
                        "title",
                        "shot_type",
                        "subject",
                        "action",
                        "setting",
                        "lighting",
                        "camera_motion",
                        "mood",
                        "narration_line",
                        "narration_cue",
                        "sfx_notes",
                        "characters",
                        "constraints",
                    ],
                },
            },
        },
        "required": ["project", "shots"],
    }
