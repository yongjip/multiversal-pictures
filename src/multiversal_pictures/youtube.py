from __future__ import annotations

import mimetypes
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .files import ensure_dir, utc_timestamp

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
VALID_PRIVACY_STATUSES = {"public", "private", "unlisted"}
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}
MAX_UPLOAD_RETRIES = 10


class YouTubeUploadError(ValueError):
    pass


@dataclass
class YouTubeUploadConfig:
    video_path: Path
    client_secrets_path: Path
    token_path: Path
    title: str
    description: str = ""
    tags: Optional[List[str]] = None
    category_id: str = "22"
    privacy_status: str = "private"
    chunk_size: int = -1
    open_browser: bool = True
    bind_host: str = "localhost"
    bind_port: int = 0


def upload_youtube_video(config: YouTubeUploadConfig) -> Dict[str, Any]:
    video_path = config.video_path.expanduser().resolve()
    client_secrets_path = config.client_secrets_path.expanduser().resolve()
    token_path = config.token_path.expanduser().resolve()
    title = config.title.strip()
    description = config.description.strip()
    privacy_status = config.privacy_status.strip().lower()
    category_id = str(config.category_id).strip() or "22"
    tags = [tag.strip() for tag in (config.tags or []) if tag and tag.strip()]

    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not client_secrets_path.exists():
        raise FileNotFoundError(client_secrets_path)
    if not title:
        raise YouTubeUploadError("YouTube uploads require a non-empty title.")
    if privacy_status not in VALID_PRIVACY_STATUSES:
        raise YouTubeUploadError(
            f"Unsupported privacy status: {privacy_status}. Choose one of: {', '.join(sorted(VALID_PRIVACY_STATUSES))}."
        )

    modules = _google_modules()
    credentials = _load_credentials(
        client_secrets_path=client_secrets_path,
        token_path=token_path,
        request_cls=modules["Request"],
        credentials_cls=modules["Credentials"],
        installed_app_flow_cls=modules["InstalledAppFlow"],
        open_browser=config.open_browser,
        bind_host=config.bind_host,
        bind_port=config.bind_port,
    )
    youtube = modules["build"](
        YOUTUBE_API_SERVICE_NAME,
        YOUTUBE_API_VERSION,
        credentials=credentials,
        cache_discovery=False,
    )

    body: Dict[str, Any] = {
        "snippet": {
            "title": title,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }
    if description:
        body["snippet"]["description"] = description
    if tags:
        body["snippet"]["tags"] = tags

    content_type, _ = mimetypes.guess_type(video_path.name)
    media = modules["MediaFileUpload"](
        str(video_path),
        chunksize=int(config.chunk_size),
        resumable=True,
        mimetype=content_type or "video/*",
    )
    insert_request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )
    response = _resumable_upload(
        insert_request=insert_request,
        http_error_cls=modules["HttpError"],
        transport_error_cls=modules["HttpLib2Error"],
    )

    if "id" not in response:
        raise YouTubeUploadError(f"The upload completed with an unexpected response: {response}")

    video_id = str(response["id"])
    return {
        "video_id": video_id,
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "video_path": str(video_path),
        "client_secrets_path": str(client_secrets_path),
        "token_path": str(token_path),
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": category_id,
        "privacy_status": privacy_status,
        "uploaded_at": utc_timestamp(),
        "response": response,
    }


def _load_credentials(
    *,
    client_secrets_path: Path,
    token_path: Path,
    request_cls: Any,
    credentials_cls: Any,
    installed_app_flow_cls: Any,
    open_browser: bool,
    bind_host: str,
    bind_port: int,
) -> Any:
    credentials = None
    if token_path.exists():
        credentials = credentials_cls.from_authorized_user_file(
            str(token_path),
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(request_cls())
    else:
        flow = installed_app_flow_cls.from_client_secrets_file(
            str(client_secrets_path),
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )
        credentials = flow.run_local_server(
            host=bind_host,
            port=bind_port,
            open_browser=open_browser,
        )

    ensure_dir(token_path.parent)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def _resumable_upload(
    *,
    insert_request: Any,
    http_error_cls: Any,
    transport_error_cls: Any,
) -> Dict[str, Any]:
    response = None
    retry_count = 0
    last_progress = -1

    while response is None:
        try:
            status, response = insert_request.next_chunk()
            if status is not None:
                progress = int(status.progress() * 100)
                if progress > last_progress:
                    print(f"YouTube upload progress: {progress}%")
                    last_progress = progress
            if response is not None:
                return response
        except http_error_cls as error:
            status_code = getattr(getattr(error, "resp", None), "status", None)
            if status_code not in RETRIABLE_STATUS_CODES:
                detail = getattr(error, "content", b"")
                if isinstance(detail, bytes):
                    detail = detail.decode("utf-8", errors="replace")
                raise YouTubeUploadError(f"YouTube upload failed with HTTP {status_code}: {detail}") from error
            _sleep_before_retry(retry_count, f"HTTP {status_code}")
            retry_count += 1
        except (transport_error_cls, OSError, TimeoutError) as error:
            _sleep_before_retry(retry_count, str(error))
            retry_count += 1

        if retry_count > MAX_UPLOAD_RETRIES:
            raise YouTubeUploadError("YouTube upload failed after repeated retries.")

    raise YouTubeUploadError("YouTube upload did not return a response.")


def _sleep_before_retry(retry_count: int, reason: str) -> None:
    if retry_count >= MAX_UPLOAD_RETRIES:
        raise YouTubeUploadError(f"YouTube upload failed after {MAX_UPLOAD_RETRIES} retries: {reason}")
    sleep_seconds = random.random() * (2 ** retry_count)
    print(f"YouTube upload retry {retry_count + 1}/{MAX_UPLOAD_RETRIES} after error: {reason}")
    time.sleep(sleep_seconds)


def _google_modules() -> Dict[str, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
        from httplib2 import HttpLib2Error
    except ImportError as error:
        raise YouTubeUploadError(
            "YouTube upload support requires google-api-python-client, google-auth-httplib2, and google-auth-oauthlib. "
            "Reinstall the project with `python3 -m pip install -e .`."
        ) from error

    return {
        "Request": Request,
        "Credentials": Credentials,
        "InstalledAppFlow": InstalledAppFlow,
        "build": build,
        "HttpError": HttpError,
        "MediaFileUpload": MediaFileUpload,
        "HttpLib2Error": HttpLib2Error,
    }
