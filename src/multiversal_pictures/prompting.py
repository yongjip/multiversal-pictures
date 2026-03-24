from __future__ import annotations

from typing import Any, Dict, Iterable, List


DEFAULT_CONSTRAINTS = [
    "family-friendly children's story tone",
    "no text, no subtitles, no watermark",
    "clean anatomy and natural motion",
    "consistent character proportions and face design",
]


def _join_constraints(items: Iterable[str]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return "; ".join(cleaned)


def build_shot_prompt(project: Dict[str, Any], shot: Dict[str, Any]) -> str:
    explicit_prompt = str(shot.get("prompt") or "").strip()
    if explicit_prompt:
        return explicit_prompt

    shot_type = shot.get("shot_type") or project.get("default_shot_type") or "Cinematic medium shot"
    subject = shot.get("subject") or project.get("default_subject") or "the main subject"
    action = shot.get("action") or "moves naturally through the scene"
    setting = shot.get("setting") or project.get("default_setting") or "a visually clear environment"
    lighting = shot.get("lighting") or project.get("default_lighting") or "soft natural light"
    camera_motion = shot.get("camera_motion") or project.get("default_camera_motion") or "steady camera"
    mood = shot.get("mood") or project.get("default_mood") or "warm and grounded"
    style_notes = shot.get("style_notes") or project.get("style_notes")
    continuity_notes = shot.get("consistency_notes") or project.get("consistency_notes")
    audio_notes = shot.get("audio_notes") or project.get("audio_notes")

    constraints: List[str] = []
    constraints.extend(project.get("constraints") or [])
    constraints.extend(shot.get("constraints") or [])
    if not constraints:
        constraints = list(DEFAULT_CONSTRAINTS)

    sentences = [
        f"{shot_type}.",
        f"Subject: {subject}.",
        f"Action: {action}.",
        f"Setting: {setting}.",
        f"Lighting: {lighting}.",
        f"Camera: {camera_motion}.",
        f"Mood: {mood}.",
    ]

    if style_notes:
        sentences.append(f"Style: {style_notes}.")

    if continuity_notes:
        sentences.append(f"Continuity: {continuity_notes}.")

    if audio_notes:
        sentences.append(f"Audio direction: {audio_notes}.")

    narration_line = str(shot.get("narration_line") or "").strip()
    narration_cue = str(shot.get("narration_cue") or "").strip()
    sfx_notes = str(shot.get("sfx_notes") or "").strip()

    sentences.append(
        "Narration is added later as external voiceover; do not depend on visible speaking, lip-sync, or character dialogue performance."
    )
    if narration_line:
        if narration_cue:
            sentences.append(f"Voiceover reference: {narration_cue} narration says '{narration_line}'.")
        else:
            sentences.append(f"Voiceover reference: narration says '{narration_line}'.")
    if sfx_notes:
        sentences.append(f"SFX: {sfx_notes}.")

    sentences.append(f"Constraints: {_join_constraints(constraints)}.")
    return " ".join(sentences)
