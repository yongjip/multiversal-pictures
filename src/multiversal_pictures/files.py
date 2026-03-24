from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_bytes(path: Path, value: bytes) -> None:
    ensure_dir(path.parent)
    path.write_bytes(value)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", str(value).strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "item"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def image_path_to_data_url(path: Path) -> str:
    content_type, _ = mimetypes.guess_type(path.name)
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError(f"Unsupported input_reference image type: {path}")

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"
