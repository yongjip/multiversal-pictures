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


def _unique_strings(items: Iterable[str]) -> List[str]:
    seen = set()
    values: List[str] = []
    for item in items:
        cleaned = str(item).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        values.append(cleaned)
    return values


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
    subtitle_position = _subtitle_position(project, shot)
    start_frame = str(shot.get("start_frame") or "").strip()
    end_frame = str(shot.get("end_frame") or "").strip()
    characters = _selected_character_specs(project, shot)
    constraints = _constraints(project, shot)
    must_keep = _must_keep(project, shot, characters)
    negative_constraints = _negative_constraints(shot)

    sections: List[str] = []
    if explicit_prompt:
        sections.append(explicit_prompt)
    else:
        sections.append(
            "Shot: "
            f"{shot_type}; subject {subject}; action {action}; setting {setting}; lighting {lighting}; camera {camera_motion}; mood {mood}."
        )

    if characters:
        sections.append(f"Character continuity: {_character_prompt_block(characters)}.")
    if style_notes:
        sections.append(f"Look: {style_notes}.")
    if continuity_notes:
        sections.append(f"Continuity: {continuity_notes}.")
    if start_frame or end_frame:
        frame_notes = []
        if start_frame:
            frame_notes.append(f"opening frame {start_frame}")
        if end_frame:
            frame_notes.append(f"closing beat {end_frame}")
        sections.append(f"Beat lock: {'; '.join(frame_notes)}.")
    framing_bits = _unique_strings(
        [
            str(format_guidance or "").strip(),
            _subject_scale_guidance(shot),
            _subtitle_safe_guidance(subtitle_position),
        ]
    )
    if framing_bits:
        sections.append(f"Framing: {' '.join(framing_bits)}")
    if audio_notes:
        sections.append(f"Audio feel: {audio_notes}.")
    sections.append("Structure: one continuous single shot, no cuts, no montage, no scene reset.")
    sections.append("Dialogue: narration is external voiceover only; no visible speaking or lip-sync dependency.")

    narration_line = str(shot.get("narration_line") or "").strip()
    narration_cue = str(shot.get("narration_cue") or "").strip()
    sfx_notes = str(shot.get("sfx_notes") or "").strip()
    if narration_line:
        if narration_cue:
            sections.append(f"Voiceover reference: {narration_cue}; narration says '{narration_line}'.")
        else:
            sections.append(f"Voiceover reference: narration says '{narration_line}'.")
    if sfx_notes:
        sections.append(f"SFX reference: {sfx_notes}.")
    if must_keep:
        sections.append(f"Preserve: {_join_constraints(must_keep)}.")
    if negative_constraints:
        sections.append(f"Avoid: {_join_constraints(negative_constraints)}.")
    sections.append(f"Constraints: {_join_constraints(constraints)}.")
    return " ".join(section.strip() for section in sections if section.strip())


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
    subtitle_position = _subtitle_position(project, shot)
    start_frame = str(shot.get("start_frame") or "").strip()
    end_frame = str(shot.get("end_frame") or "").strip()
    characters = _selected_character_specs(project, shot)
    constraints = _constraints(project, shot)
    must_keep = _must_keep(project, shot, characters)
    negative_constraints = _negative_constraints(shot)

    sections = [
        "Continue the existing completed video as a seamless extension of the same scene.",
        "Preserve motion continuity, camera direction, environment continuity, character identity, wardrobe, palette, and emotional tone from the source clip.",
    ]
    if explicit_prompt:
        sections.append(explicit_prompt)
    else:
        sections.append(
            "Continuation: "
            f"subject {subject}; action {action}; setting {setting}; lighting {lighting}; camera {camera_motion}; mood {mood}."
        )
    if characters:
        sections.append(f"Character continuity: {_character_prompt_block(characters)}.")
    if style_notes:
        sections.append(f"Look: {style_notes}.")
    if continuity_notes:
        sections.append(f"Continuity: {continuity_notes}.")
    if start_frame:
        sections.append(f"Immediate continuation point: {start_frame}.")
    if end_frame:
        sections.append(f"Land the extension on: {end_frame}.")
    framing_bits = _unique_strings(
        [
            str(format_guidance or "").strip(),
            _subject_scale_guidance(shot),
            _subtitle_safe_guidance(subtitle_position),
        ]
    )
    if framing_bits:
        sections.append(f"Framing: {' '.join(framing_bits)}")
    if must_keep:
        sections.append(f"Preserve: {_join_constraints(must_keep)}.")
    if negative_constraints:
        sections.append(f"Avoid: {_join_constraints(negative_constraints)}.")
    sections.append("Do not restart the scene or introduce a new composition unless explicitly requested.")
    sections.append(
        "Narration remains external voiceover; do not rely on visible speaking, lip-sync, or character dialogue performance."
    )
    sections.append(f"Constraints: {_join_constraints(constraints)}.")
    return " ".join(section.strip() for section in sections if section.strip())


def _build_edit_prompt(project: Dict[str, Any], shot: Dict[str, Any], explicit_prompt: str) -> str:
    style_notes = shot.get("style_notes") or project.get("style_notes")
    continuity_notes = shot.get("consistency_notes") or project.get("consistency_notes")
    format_guidance = shot.get("format_guidance") or project.get("format_guidance")
    subtitle_position = _subtitle_position(project, shot)
    characters = _selected_character_specs(project, shot)
    constraints = _constraints(project, shot)
    must_keep = _must_keep(project, shot, characters)
    negative_constraints = _negative_constraints(shot)

    edit_request = explicit_prompt or str(shot.get("action") or "").strip() or "apply one targeted corrective change"
    sections = [
        "Change only the requested details in the existing video. Keep everything else the same.",
        f"Requested change: {edit_request}.",
    ]
    if characters:
        sections.append(f"Preserve character continuity: {_character_prompt_block(characters)}.")
    if style_notes:
        sections.append(f"Preserve style: {style_notes}.")
    if continuity_notes:
        sections.append(f"Preserve project continuity: {continuity_notes}.")
    framing_bits = _unique_strings(
        [
            str(format_guidance or "").strip(),
            _subject_scale_guidance(shot),
            _subtitle_safe_guidance(subtitle_position),
        ]
    )
    if framing_bits:
        sections.append(f"Preserve framing: {' '.join(framing_bits)}")
    if must_keep:
        sections.append(f"Keep exactly: {_join_constraints(must_keep)}.")
    if negative_constraints:
        sections.append(f"Do not introduce: {_join_constraints(negative_constraints)}.")
    sections.append(
        "Narration remains external voiceover; do not add visible speaking, lip-sync, or dialogue performance."
    )
    sections.append(f"Constraints: {_join_constraints(constraints)}.")
    return " ".join(section.strip() for section in sections if section.strip())


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
    return _unique_strings(item for item in items if item)


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


def _subtitle_position(project: Dict[str, Any], shot: Dict[str, Any]) -> str:
    value = str(shot.get("subtitle_position") or project.get("subtitle_position") or "bottom").strip().lower()
    if value in {"bottom", "bottom_raised", "top"}:
        return value
    return "bottom"


def _subject_scale_guidance(shot: Dict[str, Any]) -> str:
    size_value = str(shot.get("size") or "").strip().lower()
    if "x" in size_value:
        width_text, height_text = size_value.split("x", 1)
        try:
            if int(height_text) > int(width_text):
                return "Keep the main subject large and readable in the middle vertical band, with simple silhouettes and uncluttered edges."
        except ValueError:
            pass
    return "Keep the primary subject readable at a glance and avoid tiny competing details."


def _subtitle_safe_guidance(position: str) -> str:
    if position == "top":
        return "Leave the upper caption band clean with no critical detail in the top center."
    if position == "bottom_raised":
        return "Leave a raised lower caption band clean with no critical detail in the lower middle of the frame."
    return "Leave the lower caption band clean with no critical detail in the lower middle of the frame."
