from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .files import ensure_dir, read_json, slugify, utc_timestamp, write_bytes, write_json
from .openai_videos import OpenAIAPIError, OpenAIVideosClient
from .shotlist import build_shot_request, preferred_variants


ACTIVE_VIDEO_STATUSES = {"queued", "in_progress"}
RECOVERABLE_TERMINAL_STATUSES = {"failed", "expired", "cancelled", "canceled"}


def render_shots(
    *,
    shotlist_path: Path,
    project: Dict[str, Any],
    ordered_shots: Iterable[Dict[str, Any]],
    output_dir: Path,
    selected_ids: Set[str],
    download_variants_override: Optional[str],
    dry_run: bool,
    skip_existing: bool,
    poll_interval: int,
    timeout_seconds: int,
    jobs: int,
    client: Optional[OpenAIVideosClient],
) -> Dict[str, Any]:
    run_dir = ensure_dir(output_dir)
    requests_dir = ensure_dir(run_dir / "requests")
    shots_dir = ensure_dir(run_dir / "shots")
    ordered = [shot for shot in ordered_shots if not selected_ids or shot["id"] in selected_ids]

    run_manifest: Dict[str, Any] = {
        "project_title": project.get("title") or shotlist_path.stem,
        "shotlist_path": str(shotlist_path),
        "generated_at": utc_timestamp(),
        "dry_run": bool(dry_run),
        "jobs": max(1, jobs),
        "shots": [],
    }
    write_json(run_dir / "shotlist.json", {"project": project, "shots": ordered})

    known_videos: Dict[str, str] = {}
    results: Dict[str, Dict[str, Any]] = {}

    for shot in ordered:
        previous = _existing_manifest(shot=shot, shots_dir=shots_dir) if skip_existing else None
        variants = preferred_variants(project, shot, download_variants_override)
        if previous and previous.get("status") == "completed" and previous.get("video_id") and _manifest_downloads_ready(previous, variants):
            known_videos[shot["id"]] = str(previous["video_id"])
            results[shot["id"]] = previous
            print(f"Skipping existing shot: {shot['id']}")

    pending = [shot for shot in ordered if shot["id"] not in results]
    if dry_run:
        for shot in pending:
            manifest = _prepare_dry_run_shot(
                shot=shot,
                project=project,
                shotlist_path=shotlist_path,
                requests_dir=requests_dir,
                shots_dir=shots_dir,
                known_videos=known_videos,
            )
            results[shot["id"]] = manifest
            print(f"Prepared request: {shot['id']}")
        run_manifest["shots"] = _ordered_results(ordered, results)
        write_json(run_dir / "run-manifest.json", run_manifest)
        return run_manifest

    if client is None:
        raise ValueError("OpenAI client is required for real renders.")

    print_lock = Lock()
    running: Dict[Future[Dict[str, Any]], Dict[str, Any]] = {}
    failed_ids: Set[str] = set()
    jobs = max(1, jobs)

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        while pending or running:
            blocked, ready = _partition_pending_shots(pending, known_videos, failed_ids)
            for shot in blocked:
                manifest = _blocked_manifest(shot=shot, shots_dir=shots_dir)
                results[shot["id"]] = manifest
                failed_ids.add(shot["id"])
                with print_lock:
                    print(f"Blocked {shot['id']}: dependency did not complete")
            pending = [shot for shot in pending if shot["id"] not in results]

            available_slots = jobs - len(running)
            while ready and available_slots > 0:
                shot = ready.pop(0)
                pending = [item for item in pending if item["id"] != shot["id"]]
                future = executor.submit(
                    _render_one_shot,
                    shot=shot,
                    project=project,
                    shotlist_path=shotlist_path,
                    requests_dir=requests_dir,
                    shots_dir=shots_dir,
                    known_videos=dict(known_videos),
                    client=client,
                    poll_interval=poll_interval,
                    timeout_seconds=timeout_seconds,
                    download_variants_override=download_variants_override,
                    print_lock=print_lock,
                )
                running[future] = shot
                available_slots -= 1

            if running:
                done, _ = wait(running.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    shot = running.pop(future)
                    manifest = future.result()
                    results[shot["id"]] = manifest
                    if manifest.get("status") == "completed" and manifest.get("video_id"):
                        known_videos[shot["id"]] = str(manifest["video_id"])
                    else:
                        failed_ids.add(shot["id"])
            elif pending:
                for shot in pending:
                    manifest = _blocked_manifest(
                        shot=shot,
                        shots_dir=shots_dir,
                        error=f"Unresolved dependency chain for shot {shot['id']}.",
                    )
                    results[shot["id"]] = manifest
                    failed_ids.add(shot["id"])
                break

    run_manifest["shots"] = _ordered_results(ordered, results)
    write_json(run_dir / "run-manifest.json", run_manifest)
    return run_manifest


def _render_one_shot(
    *,
    shot: Dict[str, Any],
    project: Dict[str, Any],
    shotlist_path: Path,
    requests_dir: Path,
    shots_dir: Path,
    known_videos: Dict[str, str],
    client: OpenAIVideosClient,
    poll_interval: int,
    timeout_seconds: int,
    download_variants_override: Optional[str],
    print_lock: Lock,
) -> Dict[str, Any]:
    shot_dir = ensure_dir(shots_dir / f"{shot['order']:02d}-{slugify(shot['id'])}")
    request_payload = build_shot_request(
        project=project,
        shot=shot,
        shotlist_dir=shotlist_path.parent,
        known_videos=known_videos,
    )
    request_path = requests_dir / f"{shot['order']:02d}-{slugify(shot['id'])}.json"
    write_json(request_path, request_payload)

    existing_manifest = _existing_manifest(shot=shot, shots_dir=shots_dir)
    if existing_manifest:
        resumed = _resume_existing_shot(
            shot=shot,
            project=project,
            request_payload=request_payload,
            request_path=request_path,
            existing_manifest=existing_manifest,
            shot_dir=shot_dir,
            client=client,
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
            download_variants_override=download_variants_override,
            print_lock=print_lock,
        )
        if resumed is not None:
            return resumed

    shot_manifest = _base_shot_manifest(shot=shot, request_path=request_path)
    variants = preferred_variants(project, shot, download_variants_override)
    job_path = shot_dir / "job.json"

    try:
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
        shot_manifest["job_path"] = str(job_path)
        shot_manifest["status"] = "submitted"
        write_json(job_path, job)
        write_json(shot_dir / "shot-manifest.json", shot_manifest)
        with print_lock:
            print(f"Started {shot['id']}: {job['id']} ({job.get('status')})")

        def _on_update(video: Dict[str, Any]) -> None:
            write_json(job_path, video)
            if str(video.get("status")) in ACTIVE_VIDEO_STATUSES and shot_manifest.get("status") != "rendering":
                shot_manifest["status"] = "rendering"
                write_json(shot_dir / "shot-manifest.json", shot_manifest)

        final_job = client.wait_for_video(
            job["id"],
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
            on_update=_on_update,
        )
        write_json(job_path, final_job)
        return _finalize_rendered_shot(
            shot=shot,
            project=project,
            shot_dir=shot_dir,
            shot_manifest=shot_manifest,
            final_job=final_job,
            variants=variants,
            client=client,
            print_lock=print_lock,
        )
    except Exception as error:
        shot_manifest["status"] = "failed"
        shot_manifest["error"] = str(error)
        write_json(shot_dir / "shot-manifest.json", shot_manifest)
        with print_lock:
            print(f"Failed {shot['id']}: {error}")
        return shot_manifest


def _resume_existing_shot(
    *,
    shot: Dict[str, Any],
    project: Dict[str, Any],
    request_payload: Dict[str, Any],
    request_path: Path,
    existing_manifest: Dict[str, Any],
    shot_dir: Path,
    client: OpenAIVideosClient,
    poll_interval: int,
    timeout_seconds: int,
    download_variants_override: Optional[str],
    print_lock: Lock,
) -> Optional[Dict[str, Any]]:
    variants = preferred_variants(project, shot, download_variants_override)
    if existing_manifest.get("status") == "completed" and _manifest_downloads_ready(existing_manifest, variants):
        return existing_manifest

    video_id = existing_manifest.get("video_id")
    if not video_id:
        return None

    job_path = Path(str(existing_manifest.get("job_path") or (shot_dir / "job.json")))
    manifest = _base_shot_manifest(shot=shot, request_path=request_path)
    manifest["video_id"] = str(video_id)
    manifest["job_path"] = str(job_path)
    manifest["downloads"] = list(existing_manifest.get("downloads") or [])
    if existing_manifest.get("generated_at"):
        manifest["generated_at"] = existing_manifest["generated_at"]

    try:
        current_job = client.retrieve_video(str(video_id))
    except OpenAIAPIError as error:
        if _job_missing_or_expired(error):
            return None
        raise

    write_json(job_path, current_job)
    status = str(current_job.get("status") or "")
    if status in ACTIVE_VIDEO_STATUSES:
        manifest["status"] = "rendering"
        write_json(shot_dir / "shot-manifest.json", manifest)
        final_job = client.wait_for_video(
            str(video_id),
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
            on_update=lambda video: write_json(job_path, video),
        )
        write_json(job_path, final_job)
        return _finalize_rendered_shot(
            shot=shot,
            project=project,
            shot_dir=shot_dir,
            shot_manifest=manifest,
            final_job=final_job,
            variants=variants,
            client=client,
            print_lock=print_lock,
        )

    if status == "completed":
        return _finalize_rendered_shot(
            shot=shot,
            project=project,
            shot_dir=shot_dir,
            shot_manifest=manifest,
            final_job=current_job,
            variants=variants,
            client=client,
            print_lock=print_lock,
        )

    if status in RECOVERABLE_TERMINAL_STATUSES:
        return None

    manifest["status"] = "failed"
    manifest["error"] = str(current_job.get("error") or f"Shot {shot['id']} ended with status {status or 'unknown'}.")
    write_json(shot_dir / "shot-manifest.json", manifest)
    with print_lock:
        print(f"Failed {shot['id']}: {manifest['error']}")
    return manifest


def _finalize_rendered_shot(
    *,
    shot: Dict[str, Any],
    project: Dict[str, Any],
    shot_dir: Path,
    shot_manifest: Dict[str, Any],
    final_job: Dict[str, Any],
    variants: List[str],
    client: OpenAIVideosClient,
    print_lock: Lock,
) -> Dict[str, Any]:
    if str(final_job.get("status")) != "completed":
        shot_manifest["status"] = "failed"
        shot_manifest["error"] = final_job.get("error")
        write_json(shot_dir / "shot-manifest.json", shot_manifest)
        with print_lock:
            print(f"Failed {shot['id']}: {final_job.get('error')}")
        return shot_manifest

    downloads: List[Dict[str, Any]] = []
    existing_by_variant = {
        str(item.get("variant")): dict(item) for item in shot_manifest.get("downloads") or [] if item.get("variant")
    }

    try:
        for variant in variants:
            extension = _variant_extension(variant)
            output_path = shot_dir / f"{variant}{extension}"
            if output_path.exists():
                downloads.append({"variant": variant, "path": str(output_path)})
                continue
            if variant in existing_by_variant:
                candidate_path = Path(str(existing_by_variant[variant].get("path") or output_path))
                if candidate_path.exists():
                    downloads.append({"variant": variant, "path": str(candidate_path)})
                    continue
            content = client.download_content(str(final_job["id"]), variant=variant)
            write_bytes(output_path, content)
            downloads.append({"variant": variant, "path": str(output_path)})
    except Exception as error:
        shot_manifest["downloads"] = downloads
        shot_manifest["status"] = "download_failed"
        shot_manifest["error"] = str(error)
        write_json(shot_dir / "shot-manifest.json", shot_manifest)
        with print_lock:
            print(f"Failed {shot['id']}: {error}")
        return shot_manifest

    shot_manifest["downloads"] = downloads
    shot_manifest["status"] = "completed"
    shot_manifest["video_id"] = str(final_job["id"])
    shot_manifest.pop("error", None)
    write_json(shot_dir / "shot-manifest.json", shot_manifest)
    with print_lock:
        print(f"Completed {shot['id']}: {final_job['id']}")
    return shot_manifest


def _partition_pending_shots(
    pending: List[Dict[str, Any]],
    known_videos: Dict[str, str],
    failed_ids: Set[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    blocked: List[Dict[str, Any]] = []
    ready: List[Dict[str, Any]] = []
    for shot in pending:
        dependency_ids = _dependency_ids(shot)
        if any(dep in failed_ids for dep in dependency_ids):
            blocked.append(shot)
        elif all(dep in known_videos for dep in dependency_ids):
            ready.append(shot)
    return blocked, ready


def _dependency_ids(shot: Dict[str, Any]) -> List[str]:
    mode = str(shot.get("mode") or "generate").strip().lower()
    if mode in {"extend", "edit"} and shot.get("source_shot_id") and not shot.get("source_video_id"):
        return [str(shot["source_shot_id"])]
    return []


def _prepare_dry_run_shot(
    *,
    shot: Dict[str, Any],
    project: Dict[str, Any],
    shotlist_path: Path,
    requests_dir: Path,
    shots_dir: Path,
    known_videos: Dict[str, str],
) -> Dict[str, Any]:
    request_payload = build_shot_request(
        project=project,
        shot=shot,
        shotlist_dir=shotlist_path.parent,
        known_videos=known_videos,
    )
    request_path = requests_dir / f"{shot['order']:02d}-{slugify(shot['id'])}.json"
    write_json(request_path, request_payload)
    shot_dir = ensure_dir(shots_dir / f"{shot['order']:02d}-{slugify(shot['id'])}")
    shot_manifest = {
        "id": shot["id"],
        "title": shot["title"],
        "mode": shot.get("mode", "generate"),
        "request_path": str(request_path),
        "generated_at": utc_timestamp(),
        "status": "dry_run",
        "downloads": [],
    }
    write_json(shot_dir / "shot-manifest.json", shot_manifest)
    return shot_manifest


def _existing_manifest(*, shot: Dict[str, Any], shots_dir: Path) -> Optional[Dict[str, Any]]:
    shot_manifest_path = shots_dir / f"{shot['order']:02d}-{slugify(shot['id'])}" / "shot-manifest.json"
    if not shot_manifest_path.exists():
        return None
    return read_json(shot_manifest_path)


def _blocked_manifest(*, shot: Dict[str, Any], shots_dir: Path, error: Optional[str] = None) -> Dict[str, Any]:
    shot_dir = ensure_dir(shots_dir / f"{shot['order']:02d}-{slugify(shot['id'])}")
    manifest = {
        "id": shot["id"],
        "title": shot["title"],
        "mode": shot.get("mode", "generate"),
        "generated_at": utc_timestamp(),
        "status": "blocked_dependency",
        "downloads": [],
        "error": error or f"Upstream dependency for {shot['id']} did not complete.",
    }
    write_json(shot_dir / "shot-manifest.json", manifest)
    return manifest


def _ordered_results(ordered_shots: Iterable[Dict[str, Any]], results: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [results[shot["id"]] for shot in ordered_shots if shot["id"] in results]


def _variant_extension(variant: str) -> str:
    mapping = {
        "video": ".mp4",
        "thumbnail": ".webp",
        "spritesheet": ".jpg",
    }
    return mapping.get(variant, ".bin")


def _base_shot_manifest(*, shot: Dict[str, Any], request_path: Path) -> Dict[str, Any]:
    return {
        "id": shot["id"],
        "title": shot["title"],
        "mode": shot.get("mode", "generate"),
        "request_path": str(request_path),
        "generated_at": utc_timestamp(),
        "status": "queued",
        "downloads": [],
    }


def _manifest_downloads_ready(manifest: Dict[str, Any], variants: List[str]) -> bool:
    downloads = {str(item.get("variant")): str(item.get("path")) for item in manifest.get("downloads") or [] if item.get("variant")}
    for variant in variants:
        if variant not in downloads:
            return False
        if not Path(downloads[variant]).exists():
            return False
    return True


def _job_missing_or_expired(error: OpenAIAPIError) -> bool:
    message = str(error).lower()
    return "(404)" in message or "not found" in message or "expired" in message
