"""Small, versioned on-disk cache for normalized fragments."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .fragment import VectexFragment

_NAMESPACE = "vectex-v1"


def cache_root(cache_dir: str | os.PathLike[str] | None) -> Path | None:
    """Resolve an explicit or environment-configured cache directory."""
    value = cache_dir if cache_dir is not None else os.environ.get("VECTEX_CACHE_DIR")
    return Path(value).expanduser() / _NAMESPACE if value else None


def load(root: Path, key: str) -> VectexFragment | None:
    """Load a valid cache record, treating corruption as a cache miss."""
    path = root / f"{key}.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        payload = record["payload"]
        encoded = _json(payload)
        if record.get("version") != 1 or record.get("checksum") != _digest(encoded):
            raise ValueError("invalid cache record")
        raw_view_box = payload["view_box"]
        if not isinstance(raw_view_box, list) or len(raw_view_box) != 4:
            raise ValueError("invalid cached view box")
        view_box = (
            float(raw_view_box[0]),
            float(raw_view_box[1]),
            float(raw_view_box[2]),
            float(raw_view_box[3]),
        )
        return VectexFragment(
            _serialized=payload["svg"].encode("utf-8"),
            source=payload["source"],
            engine=payload["engine"],
            converter=payload["converter"],
            scale=float(payload["scale"]),
            width=float(payload["width"]),
            height=float(payload["height"]),
            view_box=view_box,
            baseline=(
                None if payload["baseline"] is None else float(payload["baseline"])
            ),
            _metadata_json=payload["metadata"],
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def store(root: Path, key: str, fragment: VectexFragment) -> None:
    """Atomically store one complete fragment record."""
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "baseline": fragment.baseline,
        "converter": fragment.converter,
        "engine": fragment.engine,
        "height": fragment.height,
        "metadata": _json(fragment.metadata),
        "scale": fragment.scale,
        "source": fragment.source,
        "svg": fragment.to_svg(),
        "view_box": list(fragment.view_box),
        "width": fragment.width,
    }
    encoded = _json(payload)
    record = _json({"checksum": _digest(encoded), "payload": payload, "version": 1})
    fd, temporary = tempfile.mkstemp(prefix=".vectex-", suffix=".tmp", dir=root)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(record)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(root / f"{key}.json")
    finally:
        temporary_path.unlink(missing_ok=True)


def clear(cache_dir: str | os.PathLike[str] | None = None) -> int:
    """Remove only Vectex cache records and return the number removed."""
    root = cache_root(cache_dir)
    if root is None or not root.is_dir():
        return 0
    removed = 0
    for path in root.glob("*.json"):
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        removed += 1
    return removed


def _digest(value: str) -> str:
    return hashlib.blake2s(value.encode("utf-8")).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
