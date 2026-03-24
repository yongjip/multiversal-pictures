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
    mode = _shot_mode(shot)
    explicit_prompt = str(shot.get("prompt") or "").strip()
    if mode == "extend":
        return _build_extend_prompt(project, shot, explicit_prompt)
    if mode == "edit":
        return _build_edit_prompt(project, shot, explicit_prompt)
    return _build_generate_prompt(project, shot, explicit_prompt)


def build_anchor_prompt(project: Dict[str, Any], shot: Dict[str, Any]) -> str:
    base_prompt = build_shot_prompt(project, shot)
    start_frame = str(shot.get("start_frame") or "").strip()
    end_frame = str(shot.get("end_frame") or "").strip()
    style_notes = str(shot.get("style_notes") or project.get("style_notes") or "").strip()
    format_guidance = str(shot.get("format_guidance") or project.get("format_guidance") or "").strip()

    sentences = [
        "Create one polished still anchor image for the opening frame of this video shot.",
        "This must be a single illustration frame, not a sequence, contact sheet, storyboard page, or split panel.",
        base_prompt,
    ]
    if start_frame:
        sentences.append(f"Opening frame target: {start_frame}.")
    if end_frame:
        sentences.append(f"Closing beat reference: {end_frame}.")
    if style_notes:
        sentences.append(f"Anchor image style: {style_notes}.")
    if format_guidance:
        sentences.append(f"Anchor framing guidance: {format_guidance}.")
    sentences.append("No text, no subtitles, no speech bubbles, no watermark.")
    return " ".join(sentences)


def _build_generate_prompt(project: Dict[str, Any], shot: Dict[str, Any], explicit_prompt: str) -> str:
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
    format_guidance = shot.get("format_guidance") or project.get("format_guidance")
    start_frame = str(shot.get("start_frame") or "").strip()
    end_frame = str(shot.get("end_frame") or "").strip()
    characters = _selected_character_specs(project, shot)
    constraints = _constraints(project, shot)
    must_keep = _must_keep(project, shot, characters)
    negative_constraints = _negative_constraints(shot)

    sentences: List[str] = []
    if explicit_prompt:
        sentences.append(explicit_prompt)
    else:
        sentences.extend(
            [
                f"{shot_type}.",
                f"Subject: {subject}.",
                f"Action: {action}.",
                f"Setting: {setting}.",
                f"Lighting: {lighting}.",
                f"Camera: {camera_motion}.",
                f"Mood: {mood}.",
            ]
        )

    if characters:
        sentences.append(f"Character continuity: {_character_prompt_block(characters)}.")
    if style_notes:
        sentences.append(f"Style: {style_notes}.")
    if continuity_notes:
        sentences.append(f"Project continuity: {continuity_notes}.")
    if start_frame:
        sentences.append(f"Opening frame: {start_frame}.")
    if end_frame:
        sentences.append(f"Closing beat: {end_frame}.")
    if format_guidance:
        sentences.append(f"Framing guidance: {format_guidance}.")
    if audio_notes:
        sentences.append(f"Audio direction: {audio_notes}.")

    sentences.append("Render as one continuous single shot with no cuts, no montage, and no scene reset.")
    sentences.append("Keep the lower center visually safe for optional subtitles and captions.")
    sentences.append(
        "Narration is added later as external voiceover; do not depend on visible speaking, lip-sync, or character dialogue performance."
    )

    narration_line = str(shot.get("narration_line") or "").strip()
    narration_cue = str(shot.get("narration_cue") or "").strip()
    sfx_notes = str(shot.get("sfx_notes") or "").strip()
    if narration_line:
        if narration_cue:
            sentences.append(f"Voiceover reference: {narration_cue} narration says '{narration_line}'.")
        else:
            sentences.append(f"Voiceover reference: narration says '{narration_line}'.")
    if sfx_notes:
        sentences.append(f"SFX reference: {sfx_notes}.")
    if must_keep:
        sentences.append(f"Must keep: {_join_constraints(must_keep)}.")
    if negative_constraints:
        sentences.append(f"Avoid: {_join_constraints(negative_constraints)}.")
    sentences.append(f"Constraints: {_join_constraints(constraints)}.")
    return " ".join(sentences)


def _build_extend_prompt(project: Dict[str, Any], shot: Dict[str, Any], explicit_prompt: str) -> str:
    subject = shot.get("subject") or project.get("default_subject") or "the existing subject"
    action = shot.get("action") or "continues naturally from the prior shot"
    setting = shot.get("setting") or project.get("default_setting") or "the same existing environment"
    lighting = shot.get("lighting") or project.get("default_lighting") or "the same established lighting"
    camera_motion = shot.get("camera_motion") or project.get("default_camera_motion") or "the same camera direction and momentum"
    mood = shot.get("mood") or project.get("default_mood") or "consistent with the prior shot"
    style_notes = shot.get("style_notes") or project.get("style_notes")
    continuity_notes = shot.get("consistency_notes") or project.get("consistency_notes")
    format_guidance = shot.get("format_guidance") or project.get("format_guidance")
    start_frame = str(shot.get("start_frame") or "").strip()
    end_frame = str(shot.get("end_frame") or "").strip()
    characters = _selected_character_specs(project, shot)
    constraints = _constraints(project, shot)
    must_keep = _must_keep(project, shot, characters)
    negative_constraints = _negative_constraints(shot)

    sentences = [
        "Continue the existing completed video as a seamless extension of the same scene.",
        "Preserve motion continuity, camera direction, environment continuity, character identity, wardrobe, palette, and emotional tone from the source clip.",
    ]
    if explicit_prompt:
        sentences.append(explicit_prompt)
    else:
        sentences.extend(
            [
                f"Subject continuation: {subject}.",
                f"Continue with action: {action}.",
                f"Setting continuity: {setting}.",
                f"Lighting continuity: {lighting}.",
                f"Camera continuity: {camera_motion}.",
                f"Mood continuity: {mood}.",
            ]
        )
    if characters:
        sentences.append(f"Character continuity: {_character_prompt_block(characters)}.")
    if style_notes:
        sentences.append(f"Style continuity: {style_notes}.")
    if continuity_notes:
        sentences.append(f"Project continuity: {continuity_notes}.")
    if start_frame:
        sentences.append(f"Immediate continuation point: {start_frame}.")
    if end_frame:
        sentences.append(f"Land the extension on: {end_frame}.")
    if format_guidance:
        sentences.append(f"Framing guidance: {format_guidance}.")
    if must_keep:
        sentences.append(f"Must keep: {_join_constraints(must_keep)}.")
    if negative_constraints:
        sentences.append(f"Avoid: {_join_constraints(negative_constraints)}.")
    sentences.append("Do not restart the scene or introduce a new composition unless explicitly requested.")
    sentences.append("Keep the lower center visually safe for optional subtitles and captions.")
    sentences.append(
        "Narration remains external voiceover; do not rely on visible speaking, lip-sync, or character dialogue performance."
    )
    sentences.append(f"Constraints: {_join_constraints(constraints)}.")
    return " ".join(sentences)


def _build_edit_prompt(project: Dict[str, Any], shot: Dict[str, Any], explicit_prompt: str) -> str:
    style_notes = shot.get("style_notes") or project.get("style_notes")
    continuity_notes = shot.get("consistency_notes") or project.get("consistency_notes")
    format_guidance = shot.get("format_guidance") or project.get("format_guidance")
    characters = _selected_character_specs(project, shot)
    constraints = _constraints(project, shot)
    must_keep = _must_keep(project, shot, characters)
    negative_constraints = _negative_constraints(shot)

    edit_request = explicit_prompt or str(shot.get("action") or "").strip() or "apply one targeted corrective change"
    sentences = [
        "Change only the requested details in the existing video. Keep everything else the same.",
        f"Requested change: {edit_request}.",
    ]
    if characters:
        sentences.append(f"Preserve character continuity: {_character_prompt_block(characters)}.")
    if style_notes:
        sentences.append(f"Preserve style: {style_notes}.")
    if continuity_notes:
        sentences.append(f"Preserve project continuity: {continuity_notes}.")
    if format_guidance:
        sentences.append(f"Preserve framing guidance: {format_guidance}.")
    if must_keep:
        sentences.append(f"Keep exactly: {_join_constraints(must_keep)}.")
    if negative_constraints:
        sentences.append(f"Do not introduce: {_join_constraints(negative_constraints)}.")
    sentences.append("Keep the lower center visually safe for optional subtitles and captions.")
    sentences.append(
        "Narration remains external voiceover; do not add visible speaking, lip-sync, or dialogue performance."
    )
    sentences.append(f"Constraints: {_join_constraints(constraints)}.")
    return " ".join(sentences)


def _shot_mode(shot: Dict[str, Any]) -> str:
    return str(shot.get("mode") or "generate").strip().lower()


def _constraints(project: Dict[str, Any], shot: Dict[str, Any]) -> List[str]:
    constraints: List[str] = []
    constraints.extend(project.get("constraints") or [])
    constraints.extend(shot.get("constraints") or [])
    return constraints or list(DEFAULT_CONSTRAINTS)


def _negative_constraints(shot: Dict[str, Any]) -> List[str]:
    return [str(item).strip() for item in shot.get("negative_constraints") or [] if str(item).strip()]


def _must_keep(project: Dict[str, Any], shot: Dict[str, Any], characters: List[Dict[str, Any]]) -> List[str]:
    items = [str(item).strip() for item in shot.get("must_keep") or [] if str(item).strip()]
    for character in characters:
        for rule in character.get("continuity_rules") or []:
            cleaned = str(rule).strip()
            if cleaned:
                items.append(cleaned)
    if project.get("consistency_notes"):
        items.append(str(project["consistency_notes"]).strip())
    return [item for item in items if item]


def _selected_character_specs(project: Dict[str, Any], shot: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for item in project.get("characters") or []:
        if isinstance(item, dict) and item.get("id"):
            by_id[str(item["id"]).strip()] = dict(item)

    specs: List[Dict[str, Any]] = []
    for item in shot.get("characters") or []:
        if isinstance(item, dict) and item.get("id"):
            character_id = str(item["id"]).strip()
            merged = dict(by_id.get(character_id) or {})
            merged.update({key: value for key, value in item.items() if value})
            merged["id"] = character_id
            specs.append(merged)
        elif isinstance(item, str) and item.strip():
            character_id = item.strip()
            specs.append(dict(by_id.get(character_id) or {"id": character_id}))
    return specs


def _character_prompt_block(characters: List[Dict[str, Any]]) -> str:
    blocks: List[str] = []
    for character in characters:
        name = str(character.get("name") or character.get("id") or "character").strip()
        description = str(character.get("description") or "").strip()
        rules = [str(item).strip() for item in character.get("continuity_rules") or [] if str(item).strip()]
        parts = [name]
        if description:
            parts.append(description)
        if rules:
            parts.append(f"keep consistent: {_join_constraints(rules)}")
        blocks.append(" — ".join(parts))
    return " | ".join(blocks)
