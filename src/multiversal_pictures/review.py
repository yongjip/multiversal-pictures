from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .files import ensure_dir, image_path_to_data_url, read_json, slugify, utc_timestamp, write_bytes, write_json
from .openai_responses import OpenAIResponsesClient, extract_response_json
from .openai_videos import OpenAIVideosClient
from .prompting import build_shot_prompt
from .shotlist import build_shot_request, load_shotlist, preferred_variants, resolve_shot_order


REVIEW_VARIANTS = ("thumbnail", "spritesheet")


def review_rendered_shots(
    *,
    run_dir: Path,
    response_client: OpenAIResponsesClient,
    video_client: OpenAIVideosClient,
    model: str,
    mode: str,
    threshold: float,
    best_of: int,
    poll_interval: int,
    timeout_seconds: int,
    selected_ids: Optional[Set[str]] = None,
    reasoning_effort: Optional[str] = None,
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
    ordered_shots = resolve_shot_order(shotlist.get("shots") or [])
    shot_by_id = {shot["id"]: shot for shot in ordered_shots}
    selected_ids = selected_ids or set()
    review_mode = _review_mode(mode)
    best_of = 1 if review_mode == "score_only" else max(1, int(best_of))
    threshold = max(0.0, min(float(threshold), 1.0))
    required_variants = ("thumbnail",) if review_mode == "score_only" else REVIEW_VARIANTS

    dependents = _dependent_ids_by_source(ordered_shots)
    run_shots = {str(item.get("id")): _normalize_shot_manifest(dict(item), shot_by_id.get(str(item.get("id")))) for item in run_manifest.get("shots") or []}
    for shot in ordered_shots:
        run_shots.setdefault(shot["id"], _empty_shot_manifest(shot))

    known_videos = {
        shot_id: selected["video_id"]
        for shot_id, manifest in run_shots.items()
        if (selected := _selected_candidate_manifest(manifest)) and selected.get("video_id")
    }

    review_manifest: Dict[str, Any] = {
        "run_dir": str(run_dir),
        "shotlist_path": str(shotlist_path),
        "model": model,
        "mode": review_mode,
        "threshold": threshold,
        "best_of": best_of,
        "reviewed_at": utc_timestamp(),
        "shots": [],
    }

    updated_run_shots: List[Dict[str, Any]] = []
    for shot in ordered_shots:
        manifest = run_shots[shot["id"]]
        if selected_ids and shot["id"] not in selected_ids:
            updated_run_shots.append(manifest)
            review_manifest["shots"].append(
                {
                    "shot_id": shot["id"],
                    "status": "skipped_unselected",
                }
            )
            continue

        shot_dir = _shot_dir(run_dir, shot)
        candidate = _selected_candidate_manifest(manifest)
        if candidate and candidate.get("status") == "completed":
            _ensure_review_variants(candidate, shot_dir=shot_dir, video_client=video_client, variants=required_variants)
            candidate["review"] = _review_candidate(
                project=project,
                shot=shot,
                candidate=candidate,
                response_client=response_client,
                model=model,
                review_variants=required_variants,
                reasoning_effort=reasoning_effort,
            )
        else:
            manifest["status"] = manifest.get("status") or "failed"

        locked_chain = _has_descendants(shot["id"], dependents)
        eligible_for_extra_candidates = (
            str(shot.get("mode") or "generate").strip().lower() == "generate"
            and not locked_chain
        )

        if review_mode == "repair" and _should_generate_more_candidates(manifest, threshold=threshold, best_of=best_of) and eligible_for_extra_candidates:
            while len(manifest.get("candidates") or []) < best_of:
                new_candidate = _render_candidate(
                    run_dir=run_dir,
                    shotlist_path=shotlist_path,
                    project=project,
                    shot=shot,
                    known_videos=known_videos,
                    video_client=video_client,
                    poll_interval=poll_interval,
                    timeout_seconds=timeout_seconds,
                )
                if new_candidate.get("status") == "completed":
                    _ensure_review_variants(new_candidate, shot_dir=shot_dir, video_client=video_client, variants=required_variants)
                    new_candidate["review"] = _review_candidate(
                        project=project,
                        shot=shot,
                        candidate=new_candidate,
                        response_client=response_client,
                        model=model,
                        review_variants=required_variants,
                        reasoning_effort=reasoning_effort,
                    )
                manifest.setdefault("candidates", []).append(new_candidate)

        best_candidate = _best_candidate(manifest.get("candidates") or [])
        if best_candidate:
            manifest["selected_candidate"] = best_candidate["candidate_id"]
            manifest["review"] = best_candidate.get("review")
            manifest["selected_score"] = _candidate_score(best_candidate)
        if locked_chain:
            manifest["selection_locked"] = True
            manifest["selection_lock_reason"] = "Shot has downstream dependent shots, so extra candidate selection is disabled."
        else:
            manifest.pop("selection_locked", None)
            manifest.pop("selection_lock_reason", None)

        manifest["recommended_action"] = _recommended_action(
            manifest=manifest,
            threshold=threshold,
            best_of=best_of,
            locked_chain=locked_chain,
        )
        _sync_selected_candidate_summary(manifest)
        write_json(shot_dir / "shot-manifest.json", manifest)

        selected_candidate = _selected_candidate_manifest(manifest)
        if selected_candidate and selected_candidate.get("video_id"):
            known_videos[shot["id"]] = str(selected_candidate["video_id"])

        updated_run_shots.append(manifest)
        review_manifest["shots"].append(
            {
                "shot_id": shot["id"],
                "selected_candidate": manifest.get("selected_candidate"),
                "candidate_count": len(manifest.get("candidates") or []),
                "selected_score": manifest.get("selected_score"),
                "recommended_action": manifest.get("recommended_action"),
                "selection_locked": bool(manifest.get("selection_locked")),
            }
        )

    run_manifest["shots"] = updated_run_shots
    write_json(run_manifest_path, run_manifest)
    write_json(run_dir / "review-manifest.json", review_manifest)
    return review_manifest


def _review_candidate(
    *,
    project: Dict[str, Any],
    shot: Dict[str, Any],
    candidate: Dict[str, Any],
    response_client: OpenAIResponsesClient,
    model: str,
    review_variants: tuple[str, ...],
    reasoning_effort: Optional[str],
) -> Dict[str, Any]:
    image_paths = _candidate_image_paths(candidate, review_variants=review_variants)
    if not image_paths:
        return {
            "overall_score": 0.0,
            "continuity": {"score": 0.0, "notes": "No thumbnail or spritesheet available."},
            "composition": {"score": 0.0, "notes": "No visual review assets available."},
            "anatomy_motion": {"score": 0.0, "notes": "No visual review assets available."},
            "prop_completeness": {"score": 0.0, "notes": "No visual review assets available."},
            "action_match": {"score": 0.0, "notes": "No visual review assets available."},
            "subtitle_safe_area": {"score": 0.0, "notes": "No visual review assets available."},
            "strengths": [],
            "issues": ["No thumbnail or spritesheet available for review."],
            "recommended_action": "edit",
            "edit_prompt": "Regenerate or edit this shot so it matches the planned composition, action, and continuity.",
        }

    content: List[Dict[str, Any]] = [
        {
            "type": "input_text",
            "text": (
                "Review this rendered shot candidate for a narration-led storybook video. "
                "Score each metric from 0.0 to 1.0. "
                "Be strict about character continuity, composition clarity, anatomy, prop completeness, action match, and lower-center subtitle safe area.\n\n"
                f"Shot title: {shot['title']}\n"
                f"Shot id: {shot['id']}\n"
                f"Mode: {shot.get('mode', 'generate')}\n"
                f"Priority: {shot.get('priority', 'normal')}\n"
                f"Target prompt: {build_shot_prompt(project, shot)}\n"
                f"Must keep: {shot.get('must_keep') or []}\n"
                f"Negative constraints: {shot.get('negative_constraints') or []}\n"
                "Return keep only when the candidate is clean and production-ready. "
                "Use edit when one focused correction is enough. Use rerender when the shot misses the brief fundamentally."
            ),
        }
    ]
    for image_path in image_paths:
        content.append(
            {
                "type": "input_image",
                "image_url": image_path_to_data_url(image_path),
            }
        )

    response = response_client.create_structured_response(
        model=model,
        instructions=(
            "You are the Review Agent for Multiversal Pictures. "
            "Evaluate the rendered candidate against the planned shot. "
            "Use concise notes, numeric scores between 0.0 and 1.0, and produce one clear recommended action."
        ),
        input_messages=[{"role": "user", "content": content}],
        schema_name="shot_review",
        schema=_shot_review_schema(),
        reasoning_effort=reasoning_effort,
    )
    return extract_response_json(response)


def _render_candidate(
    *,
    run_dir: Path,
    shotlist_path: Path,
    project: Dict[str, Any],
    shot: Dict[str, Any],
    known_videos: Dict[str, str],
    video_client: OpenAIVideosClient,
    poll_interval: int,
    timeout_seconds: int,
) -> Dict[str, Any]:
    manifest_path = _shot_dir(run_dir, shot) / "shot-manifest.json"
    existing_manifest = _normalize_shot_manifest(read_json(manifest_path), shot) if manifest_path.exists() else _empty_shot_manifest(shot)
    candidate_index = len(existing_manifest.get("candidates") or []) + 1
    candidate_id = f"candidate-{candidate_index:02d}"
    candidate_dir = ensure_dir(_shot_dir(run_dir, shot) / "candidates" / candidate_id)
    request_payload = build_shot_request(
        project=project,
        shot=shot,
        shotlist_dir=shotlist_path.parent,
        known_videos=known_videos,
    )
    request_path = candidate_dir / "request.json"
    write_json(request_path, request_payload)

    candidate_manifest: Dict[str, Any] = {
        "candidate_id": candidate_id,
        "generated_at": utc_timestamp(),
        "request_path": str(request_path),
        "status": "queued",
        "downloads": [],
    }

    try:
        creation_method = str(shot.get("mode") or "generate").strip().lower()
        if creation_method == "generate":
            job = video_client.create_video(request_payload)
        elif creation_method == "extend":
            job = video_client.create_extension(request_payload)
        elif creation_method == "edit":
            job = video_client.create_edit(request_payload)
        else:
            raise ValueError(f"Unsupported shot mode: {creation_method}")

        candidate_manifest["video_id"] = job["id"]
        job_path = candidate_dir / "job.json"
        candidate_manifest["job_path"] = str(job_path)
        write_json(job_path, job)

        final_job = video_client.wait_for_video(
            job["id"],
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
        )
        write_json(job_path, final_job)
        candidate_manifest["status"] = str(final_job.get("status"))

        if final_job.get("status") != "completed":
            candidate_manifest["error"] = final_job.get("error")
            return candidate_manifest

        download_variants = set(preferred_variants(project, shot, None))
        download_variants.update({"video", "thumbnail", "spritesheet"})
        for variant in sorted(download_variants):
            output_path = candidate_dir / f"{variant}{_variant_extension(variant)}"
            content = video_client.download_content(final_job["id"], variant=variant)
            write_bytes(output_path, content)
            candidate_manifest["downloads"].append({"variant": variant, "path": str(output_path)})

        return candidate_manifest
    except Exception as error:
        candidate_manifest["status"] = "failed"
        candidate_manifest["error"] = str(error)
        return candidate_manifest


def _ensure_review_variants(
    candidate: Dict[str, Any],
    *,
    shot_dir: Path,
    video_client: OpenAIVideosClient,
    variants: tuple[str, ...],
) -> None:
    if candidate.get("status") != "completed" or not candidate.get("video_id"):
        return

    downloads = candidate.setdefault("downloads", [])
    existing = {str(item.get("variant")) for item in downloads}
    if all(variant in existing for variant in variants):
        return

    if candidate.get("candidate_id"):
        candidate_dir = ensure_dir(shot_dir / "candidates" / str(candidate["candidate_id"]))
    else:
        candidate_dir = ensure_dir(shot_dir)

    for variant in variants:
        if variant in existing:
            continue
        output_path = candidate_dir / f"{variant}{_variant_extension(variant)}"
        content = video_client.download_content(str(candidate["video_id"]), variant=variant)
        write_bytes(output_path, content)
        downloads.append({"variant": variant, "path": str(output_path)})


def _candidate_image_paths(candidate: Dict[str, Any], *, review_variants: tuple[str, ...]) -> List[Path]:
    preferred_order = {"thumbnail": 0, "spritesheet": 1}
    paths: List[tuple[int, Path]] = []
    for download in candidate.get("downloads") or []:
        variant = str(download.get("variant") or "")
        path_value = download.get("path")
        if variant not in preferred_order or variant not in review_variants or not path_value:
            continue
        path = Path(str(path_value))
        if path.exists():
            paths.append((preferred_order[variant], path))
    return [path for _, path in sorted(paths, key=lambda item: item[0])]


def _best_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    completed = [candidate for candidate in candidates if candidate.get("status") == "completed"]
    if not completed:
        return None
    reviewed = [candidate for candidate in completed if isinstance(candidate.get("review"), dict)]
    if reviewed:
        return max(reviewed, key=_candidate_score)
    return completed[0]


def _candidate_score(candidate: Dict[str, Any]) -> float:
    review = candidate.get("review") or {}
    try:
        return float(review.get("overall_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _should_generate_more_candidates(manifest: Dict[str, Any], *, threshold: float, best_of: int) -> bool:
    candidates = manifest.get("candidates") or []
    if len(candidates) >= best_of:
        return False
    selected = _selected_candidate_manifest(manifest)
    if not selected:
        return True
    if selected.get("status") != "completed":
        return True
    return _candidate_score(selected) < threshold


def _recommended_action(*, manifest: Dict[str, Any], threshold: float, best_of: int, locked_chain: bool) -> str:
    selected = _selected_candidate_manifest(manifest)
    if not selected:
        return "rerender"
    score = _candidate_score(selected)
    if score >= threshold:
        return "keep"
    review = selected.get("review") or {}
    if review.get("edit_prompt"):
        return "edit"
    if locked_chain:
        return "edit"
    if len(manifest.get("candidates") or []) < best_of:
        return "rerender"
    return str(review.get("recommended_action") or "edit")


def _selected_candidate_manifest(manifest: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    selected_id = str(manifest.get("selected_candidate") or "").strip()
    for candidate in manifest.get("candidates") or []:
        if str(candidate.get("candidate_id")) == selected_id:
            return candidate
    candidates = manifest.get("candidates") or []
    return candidates[0] if candidates else None


def _sync_selected_candidate_summary(manifest: Dict[str, Any]) -> None:
    selected = _selected_candidate_manifest(manifest)
    if not selected:
        manifest.setdefault("status", "failed")
        return
    manifest["status"] = selected.get("status")
    manifest["video_id"] = selected.get("video_id")
    manifest["request_path"] = selected.get("request_path")
    manifest["downloads"] = list(selected.get("downloads") or [])
    if selected.get("job_path"):
        manifest["job_path"] = selected.get("job_path")
    if selected.get("error"):
        manifest["error"] = selected.get("error")
    else:
        manifest.pop("error", None)


def _normalize_shot_manifest(manifest: Dict[str, Any], shot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if manifest.get("candidates"):
        normalized = dict(manifest)
        normalized["candidates"] = [dict(candidate) for candidate in manifest.get("candidates") or []]
        if normalized.get("selected_candidate"):
            _sync_selected_candidate_summary(normalized)
        return normalized

    candidate_manifest = {
        "candidate_id": "candidate-01",
        "generated_at": manifest.get("generated_at") or utc_timestamp(),
        "request_path": manifest.get("request_path"),
        "job_path": manifest.get("job_path"),
        "status": manifest.get("status"),
        "video_id": manifest.get("video_id"),
        "downloads": list(manifest.get("downloads") or []),
    }
    if manifest.get("review"):
        candidate_manifest["review"] = manifest.get("review")
    if manifest.get("error"):
        candidate_manifest["error"] = manifest.get("error")

    normalized = {
        "id": manifest.get("id") or (shot["id"] if shot else None),
        "title": manifest.get("title") or (shot["title"] if shot else None),
        "mode": manifest.get("mode") or (shot.get("mode", "generate") if shot else "generate"),
        "generated_at": manifest.get("generated_at") or utc_timestamp(),
        "status": manifest.get("status"),
        "selected_candidate": "candidate-01",
        "candidates": [candidate_manifest],
    }
    if manifest.get("review"):
        normalized["review"] = manifest.get("review")
    if manifest.get("recommended_action"):
        normalized["recommended_action"] = manifest.get("recommended_action")
    if manifest.get("selected_score") is not None:
        normalized["selected_score"] = manifest.get("selected_score")
    _sync_selected_candidate_summary(normalized)
    return normalized


def _empty_shot_manifest(shot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": shot["id"],
        "title": shot["title"],
        "mode": shot.get("mode", "generate"),
        "generated_at": utc_timestamp(),
        "status": "missing",
        "selected_candidate": None,
        "candidates": [],
        "downloads": [],
    }


def _shot_dir(run_dir: Path, shot: Dict[str, Any]) -> Path:
    return ensure_dir(run_dir / "shots" / f"{shot['order']:02d}-{slugify(shot['id'])}")


def _dependent_ids_by_source(shots: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
    mapping: Dict[str, Set[str]] = {}
    for shot in shots:
        source_shot_id = shot.get("source_shot_id")
        if source_shot_id:
            mapping.setdefault(str(source_shot_id), set()).add(str(shot["id"]))
    return mapping


def _has_descendants(shot_id: str, dependents: Dict[str, Set[str]]) -> bool:
    queue = list(dependents.get(str(shot_id), set()))
    seen: Set[str] = set()
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(dependents.get(current, set()))
    return bool(seen)


def _variant_extension(variant: str) -> str:
    mapping = {
        "video": ".mp4",
        "thumbnail": ".webp",
        "spritesheet": ".jpg",
    }
    return mapping.get(variant, ".bin")


def _review_mode(value: str) -> str:
    normalized = str(value or "score_only").strip().lower()
    if normalized not in {"score_only", "repair"}:
        raise ValueError(f"Unsupported review mode: {value}")
    return normalized


def _shot_review_schema() -> Dict[str, Any]:
    metric_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "score": {"type": "number"},
            "notes": {"type": "string"},
        },
        "required": ["score", "notes"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "overall_score": {"type": "number"},
            "continuity": metric_schema,
            "composition": metric_schema,
            "anatomy_motion": metric_schema,
            "prop_completeness": metric_schema,
            "action_match": metric_schema,
            "subtitle_safe_area": metric_schema,
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
            },
            "issues": {
                "type": "array",
                "items": {"type": "string"},
            },
            "recommended_action": {
                "type": "string",
                "enum": ["keep", "rerender", "edit"],
            },
            "edit_prompt": {"type": "string"},
        },
        "required": [
            "overall_score",
            "continuity",
            "composition",
            "anatomy_motion",
            "prop_completeness",
            "action_match",
            "subtitle_safe_area",
            "strengths",
            "issues",
            "recommended_action",
            "edit_prompt",
        ],
    }
