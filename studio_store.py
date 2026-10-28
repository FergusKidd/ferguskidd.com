"""Persistent studio chats, settings, and memories.

Uses the same Azure Storage connection as the rest of the site:
- Tables: StudioSettings, StudioChats, StudioMemories
- Blobs: container `studio`, path chats/{sid}.json

Falls back to local files under data/ai when Azure is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("studio.store")

OWNER = "fergus"
SETTINGS_TABLE = "StudioSettings"
CHATS_TABLE = "StudioChats"
MEMORIES_TABLE = "StudioMemories"
BLOB_CONTAINER = "studio"
LOCAL_ROOT = Path(os.getenv("AI_DATA_DIR", "data/ai"))
DEFAULT_SETTINGS = {
    "retention_days": 90,
    "memory_enabled": True,
    "auto_title": True,
}
KINDS = ("preference", "project", "fact", "style", "training", "people")
MAX_MEMORIES = 80
MAX_MEMORY_TEXT = 400
MESSAGE_LIMIT = 60
MESSAGE_CHARS = 120000
MESSAGE_ITEM_CHARS = 100000

_lock = threading.Lock()
_ready = False
_azure_ok = False
_tables: dict[str, Any] = {}
_blob_container = None


def backend() -> str:
    _ensure()
    return "azure" if _azure_ok else "local"


def _ensure() -> None:
    global _ready, _azure_ok, _blob_container
    if _ready:
        return
    with _lock:
        if _ready:
            return
        connection = (os.getenv("AZURE_CONNECTION_STRING") or "").strip()
        if connection:
            try:
                from azure.core.exceptions import ResourceExistsError
                from azure.data.tables import TableServiceClient
                from azure.storage.blob import BlobServiceClient

                table_service = TableServiceClient.from_connection_string(connection)
                for name in (SETTINGS_TABLE, CHATS_TABLE, MEMORIES_TABLE):
                    try:
                        table_service.create_table(name)
                    except ResourceExistsError:
                        pass
                    _tables[name] = table_service.get_table_client(name)

                blobs = BlobServiceClient.from_connection_string(connection)
                try:
                    blobs.create_container(BLOB_CONTAINER)
                except ResourceExistsError:
                    pass
                except Exception as exc:
                    # Container may already exist under a different error shape.
                    if "ContainerAlreadyExists" not in str(exc):
                        raise
                _blob_container = blobs.get_container_client(BLOB_CONTAINER)
                _azure_ok = True
                logger.info("Studio storage using Azure tables and blobs")
            except Exception:
                logger.exception("Azure studio storage unavailable; using local files")
                _azure_ok = False
                _tables.clear()
                _blob_container = None
        else:
            logger.warning("AZURE_CONNECTION_STRING missing; studio history is local only")
        LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
        (LOCAL_ROOT / "chats").mkdir(exist_ok=True)
        (LOCAL_ROOT / "memories").mkdir(exist_ok=True)
        _ready = True


def new_chat_id() -> str:
    return secrets.token_urlsafe(24)


def get_settings() -> dict[str, Any]:
    _ensure()
    raw = _read_settings()
    settings = dict(DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        try:
            days = int(raw.get("retention_days", settings["retention_days"]))
            settings["retention_days"] = max(7, min(days, 730))
        except (TypeError, ValueError):
            pass
        settings["memory_enabled"] = bool(raw.get("memory_enabled", True))
        settings["auto_title"] = bool(raw.get("auto_title", True))
    settings["backend"] = backend()
    return settings


def save_settings(updates: dict[str, Any]) -> dict[str, Any]:
    current = get_settings()
    if "retention_days" in updates:
        try:
            current["retention_days"] = max(7, min(int(updates["retention_days"]), 730))
        except (TypeError, ValueError):
            pass
    if "memory_enabled" in updates:
        current["memory_enabled"] = bool(updates["memory_enabled"])
    if "auto_title" in updates:
        current["auto_title"] = bool(updates["auto_title"])
    payload = {
        "retention_days": current["retention_days"],
        "memory_enabled": current["memory_enabled"],
        "auto_title": current["auto_title"],
    }
    _write_settings(payload)
    return get_settings()


def list_chats(limit: int = 40) -> list[dict[str, Any]]:
    _ensure()
    chats = _list_chat_meta()
    chats.sort(key=lambda item: (not item.get("pinned"), -(item.get("updated") or 0)))
    cutoff = time.time() - get_settings()["retention_days"] * 86400
    kept = []
    for chat in chats:
        if (chat.get("updated") or 0) < cutoff and not chat.get("pinned"):
            delete_chat(chat["id"])
            continue
        kept.append(chat)
        if len(kept) >= limit:
            break
    return kept


def get_chat(sid: str) -> dict[str, Any] | None:
    _ensure()
    for chat in _list_chat_meta():
        if chat.get("id") == sid:
            return chat
    return None


def touch_chat(sid: str, *, title: str | None = None, preview: str | None = None, pinned: bool | None = None) -> dict[str, Any]:
    _ensure()
    now = int(time.time())
    existing = get_chat(sid) or {
        "id": sid,
        "title": "New chat",
        "preview": "",
        "created": now,
        "updated": now,
        "pinned": False,
    }
    if title:
        existing["title"] = title[:80]
    if preview is not None:
        existing["preview"] = preview[:160]
    if pinned is not None:
        existing["pinned"] = bool(pinned)
    existing["updated"] = now
    if "created" not in existing:
        existing["created"] = now
    _write_chat_meta(existing)
    return existing


def delete_chat(sid: str) -> None:
    _ensure()
    _delete_chat_meta(sid)
    _delete_messages(sid)


def load_messages(sid: str) -> list[dict[str, str]]:
    _ensure()
    raw = _read_messages(sid)
    clean = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            clean.append({"role": role, "content": content[:MESSAGE_ITEM_CHARS]})
    return _trim(clean)


def save_messages(sid: str, messages: list[dict[str, str]], *, user_preview: str | None = None) -> None:
    _ensure()
    trimmed = _trim(messages)
    _write_messages(sid, trimmed)
    preview = user_preview
    if preview is None:
        for item in trimmed:
            if item["role"] == "user":
                preview = item["content"]
                break
    title = None
    settings = get_settings()
    existing = get_chat(sid)
    if settings.get("auto_title") and (not existing or existing.get("title") in {None, "", "New chat"}):
        title = _title_from_preview(preview or "New chat")
    touch_chat(sid, title=title, preview=(preview or "")[:160])


def list_memories(limit: int = 40) -> list[dict[str, Any]]:
    _ensure()
    items = _list_memories()
    items.sort(key=lambda item: (not item.get("pinned"), -(item.get("updated") or item.get("created") or 0)))
    return items[:limit]


def add_memory(
    text: str,
    *,
    kind: str = "fact",
    source_sid: str = "",
    pinned: bool = False,
) -> dict[str, Any] | None:
    _ensure()
    cleaned = " ".join((text or "").split())
    if len(cleaned) < 8:
        return None
    kind = kind if kind in KINDS else "fact"
    existing = list_memories(limit=MAX_MEMORIES)
    lowered = cleaned.lower()
    for item in existing:
        if item.get("text", "").lower() == lowered:
            item["updated"] = int(time.time())
            item["source_sid"] = source_sid or item.get("source_sid") or ""
            _write_memory(item)
            return item
        if lowered in item.get("text", "").lower() or item.get("text", "").lower() in lowered:
            if len(cleaned) > len(item.get("text", "")):
                item["text"] = cleaned[:MAX_MEMORY_TEXT]
                item["kind"] = kind
                item["updated"] = int(time.time())
                item["source_sid"] = source_sid or item.get("source_sid") or ""
                _write_memory(item)
                return item
            return item
    memory = {
        "id": secrets.token_urlsafe(12),
        "kind": kind,
        "text": cleaned[:MAX_MEMORY_TEXT],
        "source_sid": source_sid,
        "pinned": bool(pinned),
        "created": int(time.time()),
        "updated": int(time.time()),
    }
    _write_memory(memory)
    # Cap growth by dropping oldest unpinned memories.
    all_items = list_memories(limit=MAX_MEMORIES + 20)
    overflow = [item for item in all_items if not item.get("pinned")][MAX_MEMORIES:]
    for item in overflow:
        delete_memory(item["id"])
    return memory


def update_memory(memory_id: str, *, pinned: bool | None = None, text: str | None = None) -> dict[str, Any] | None:
    _ensure()
    for item in _list_memories():
        if item.get("id") != memory_id:
            continue
        if pinned is not None:
            item["pinned"] = bool(pinned)
        if text is not None:
            cleaned = " ".join(text.split())
            if len(cleaned) >= 8:
                item["text"] = cleaned[:MAX_MEMORY_TEXT]
        item["updated"] = int(time.time())
        _write_memory(item)
        return item
    return None


def delete_memory(memory_id: str) -> None:
    _ensure()
    _delete_memory(memory_id)


def clear_memories() -> int:
    items = list_memories(limit=500)
    for item in items:
        delete_memory(item["id"])
    return len(items)


def memory_prompt_block(limit: int = 18) -> str:
    items = list_memories(limit=limit)
    if not items:
        return ""
    lines = ["What you remember about Fergus:"]
    for item in items:
        kind = item.get("kind") or "fact"
        text = item.get("text") or ""
        pin = " (pinned)" if item.get("pinned") else ""
        lines.append(f"- [{kind}]{pin} {text}")
    return "\n".join(lines)


def _trim(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    messages = messages[-MESSAGE_LIMIT:]
    while messages and sum(len(item["content"]) for item in messages) > MESSAGE_CHARS:
        messages.pop(0)
    return messages


def _title_from_preview(preview: str) -> str:
    text = " ".join(preview.split())
    if len(text) <= 48:
        return text or "New chat"
    return text[:45].rstrip() + "…"


# --- Azure / local adapters -------------------------------------------------

def _read_settings() -> dict[str, Any]:
    if _azure_ok:
        try:
            entity = _tables[SETTINGS_TABLE].get_entity(partition_key=OWNER, row_key="prefs")
            return {
                "retention_days": entity.get("retention_days"),
                "memory_enabled": entity.get("memory_enabled"),
                "auto_title": entity.get("auto_title"),
            }
        except Exception:
            return {}
    path = LOCAL_ROOT / "settings.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_settings(payload: dict[str, Any]) -> None:
    if _azure_ok:
        entity = {
            "PartitionKey": OWNER,
            "RowKey": "prefs",
            "retention_days": payload["retention_days"],
            "memory_enabled": payload["memory_enabled"],
            "auto_title": payload["auto_title"],
        }
        _tables[SETTINGS_TABLE].upsert_entity(entity)
        return
    path = LOCAL_ROOT / "settings.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _list_chat_meta() -> list[dict[str, Any]]:
    if _azure_ok:
        items = []
        for entity in _tables[CHATS_TABLE].query_entities(f"PartitionKey eq '{OWNER}'"):
            items.append(_chat_from_entity(entity))
        return items
    items = []
    for path in (LOCAL_ROOT / "chats").glob("*.meta.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("id"):
            items.append(data)
    return items


def _write_chat_meta(chat: dict[str, Any]) -> None:
    if _azure_ok:
        entity = {
            "PartitionKey": OWNER,
            "RowKey": chat["id"],
            "title": chat.get("title") or "New chat",
            "preview": chat.get("preview") or "",
            "created": int(chat.get("created") or time.time()),
            "updated": int(chat.get("updated") or time.time()),
            "pinned": bool(chat.get("pinned")),
        }
        _tables[CHATS_TABLE].upsert_entity(entity)
        return
    path = LOCAL_ROOT / "chats" / f"{chat['id']}.meta.json"
    path.write_text(json.dumps(chat, ensure_ascii=False), encoding="utf-8")


def _delete_chat_meta(sid: str) -> None:
    if _azure_ok:
        try:
            _tables[CHATS_TABLE].delete_entity(partition_key=OWNER, row_key=sid)
        except Exception:
            pass
        return
    path = LOCAL_ROOT / "chats" / f"{sid}.meta.json"
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _chat_from_entity(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entity.get("RowKey"),
        "title": entity.get("title") or "New chat",
        "preview": entity.get("preview") or "",
        "created": int(entity.get("created") or 0),
        "updated": int(entity.get("updated") or 0),
        "pinned": bool(entity.get("pinned")),
    }


def _read_messages(sid: str) -> list[dict[str, Any]]:
    if _azure_ok:
        try:
            blob = _blob_container.get_blob_client(f"chats/{sid}.json")
            raw = blob.download_blob().readall().decode("utf-8")
            data = json.loads(raw)
            messages = data.get("messages") if isinstance(data, dict) else data
            return messages if isinstance(messages, list) else []
        except Exception:
            return []
    path = LOCAL_ROOT / "chats" / f"{sid}.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    messages = data.get("messages") if isinstance(data, dict) else data
    return messages if isinstance(messages, list) else []


def _write_messages(sid: str, messages: list[dict[str, str]]) -> None:
    payload = json.dumps({"messages": messages, "updated": int(time.time())}, ensure_ascii=False)
    if _azure_ok:
        blob = _blob_container.get_blob_client(f"chats/{sid}.json")
        blob.upload_blob(payload.encode("utf-8"), overwrite=True)
        return
    path = LOCAL_ROOT / "chats" / f"{sid}.json"
    path.write_text(payload, encoding="utf-8")


def _delete_messages(sid: str) -> None:
    if _azure_ok:
        try:
            _blob_container.delete_blob(f"chats/{sid}.json")
        except Exception:
            pass
        return
    path = LOCAL_ROOT / "chats" / f"{sid}.json"
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _list_memories() -> list[dict[str, Any]]:
    if _azure_ok:
        items = []
        for entity in _tables[MEMORIES_TABLE].query_entities(f"PartitionKey eq '{OWNER}'"):
            items.append(_memory_from_entity(entity))
        return items
    items = []
    for path in (LOCAL_ROOT / "memories").glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("id"):
            items.append(data)
    return items


def _write_memory(memory: dict[str, Any]) -> None:
    if _azure_ok:
        entity = {
            "PartitionKey": OWNER,
            "RowKey": memory["id"],
            "kind": memory.get("kind") or "fact",
            "text": memory.get("text") or "",
            "source_sid": memory.get("source_sid") or "",
            "pinned": bool(memory.get("pinned")),
            "created": int(memory.get("created") or time.time()),
            "updated": int(memory.get("updated") or time.time()),
        }
        _tables[MEMORIES_TABLE].upsert_entity(entity)
        return
    path = LOCAL_ROOT / "memories" / f"{memory['id']}.json"
    path.write_text(json.dumps(memory, ensure_ascii=False), encoding="utf-8")


def _delete_memory(memory_id: str) -> None:
    if _azure_ok:
        try:
            _tables[MEMORIES_TABLE].delete_entity(partition_key=OWNER, row_key=memory_id)
        except Exception:
            pass
        return
    path = LOCAL_ROOT / "memories" / f"{memory_id}.json"
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _memory_from_entity(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entity.get("RowKey"),
        "kind": entity.get("kind") or "fact",
        "text": entity.get("text") or "",
        "source_sid": entity.get("source_sid") or "",
        "pinned": bool(entity.get("pinned")),
        "created": int(entity.get("created") or 0),
        "updated": int(entity.get("updated") or 0),
    }
