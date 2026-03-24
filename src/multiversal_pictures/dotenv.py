from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class DotEnvResult:
    path: Path
    loaded: bool
    keys: List[str]


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_line(line: str):
    trimmed = line.strip()
    if not trimmed or trimmed.startswith("#"):
        return None

    if trimmed.startswith("export "):
        trimmed = trimmed[len("export ") :]

    if "=" not in trimmed:
        return None

    key, raw_value = trimmed.split("=", 1)
    key = key.strip()
    if not key or not key.replace("_", "a").isalnum() or key[0].isdigit():
        return None

    return key, _strip_quotes(raw_value.strip())


def load_dotenv(base_dir: Path, filename: str = ".env") -> DotEnvResult:
    env_path = (base_dir / filename).resolve()
    if not env_path.exists():
        return DotEnvResult(path=env_path, loaded=False, keys=[])

    keys: List[str] = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_line(line)
        if not parsed:
            continue
        key, value = parsed
        keys.append(key)
        if key not in __import__("os").environ:
            __import__("os").environ[key] = value

    return DotEnvResult(path=env_path, loaded=True, keys=keys)
