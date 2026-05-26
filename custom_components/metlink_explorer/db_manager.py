"""Local JSON database file helpers for Metlink Explorer."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    DB_META_FILENAME,
    DB_MODE_SLUG_BY_TYPE,
    DB_SUBDIR,
)


def _db_dir(hass: HomeAssistant) -> Path:
    """Return the local DB output directory under /config/www."""
    return Path(hass.config.path("www", "metlink_explorer", DB_SUBDIR))


def _db_file_path(hass: HomeAssistant, filename: str) -> Path:
    """Return absolute output path for a DB file."""
    return _db_dir(hass) / str(filename)


def _json_now() -> str:
    """Return current UTC timestamp string for JSON payloads."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def db_url(filename: str) -> str:
    """Return public URL for a DB file served via /local/."""
    return f"/local/metlink_explorer/{DB_SUBDIR}/{filename}"


def mode_slug_for_type(transportation_type: int | str | None) -> str:
    """Map a GTFS route_type id to a DB file slug."""
    try:
        type_id = int(transportation_type) if transportation_type is not None else -1
    except (TypeError, ValueError):
        type_id = -1
    return DB_MODE_SLUG_BY_TYPE.get(type_id, "unknown")


async def async_write_db_file(
    hass: HomeAssistant,
    filename: str,
    payload: dict[str, Any] | list[Any],
) -> str:
    """Atomically write a JSON payload to /config/www/metlink_explorer/db/.

    Returns the public /local URL for the file.
    """
    out_path = _db_file_path(hass, filename)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    content = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str)

    def _write() -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(out_path)

    await hass.async_add_executor_job(_write)
    return db_url(filename)


async def async_read_db_file(hass: HomeAssistant, filename: str) -> dict[str, Any]:
    """Read a DB JSON file and return an object, or {} when missing/invalid."""
    in_path = _db_file_path(hass, filename)

    def _read() -> dict[str, Any]:
        try:
            raw = in_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    return await hass.async_add_executor_job(_read)


async def async_read_meta(hass: HomeAssistant) -> dict[str, Any]:
    """Read current DB metadata from meta.json."""
    return await async_read_db_file(hass, DB_META_FILENAME)


async def async_update_meta(hass: HomeAssistant, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge updates into meta.json and write back atomically."""
    current = await async_read_meta(hass)
    merged: dict[str, Any] = dict(current)
    merged.update(updates)
    merged["updated_at"] = _json_now()
    await async_write_db_file(hass, DB_META_FILENAME, merged)
    return merged


__all__ = [
    "async_read_db_file",
    "async_read_meta",
    "async_update_meta",
    "async_write_db_file",
    "db_url",
    "mode_slug_for_type",
]
