"""Private studio agent at /ai.

Sign-in is a single account. The password is stored as a bcrypt hash of a
SHA-256 digest (see scripts/hash_ai_password.py). Sessions are signed cookies.
Transcripts stay on disk for this server only and are removed on sign-out.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path
from queue import Queue
from urllib.parse import urlparse

import bcrypt
from dotenv import load_dotenv
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

logger = logging.getLogger("studio")
load_dotenv()

router = APIRouter(prefix="/ai", tags=["studio"])
templates = Jinja2Templates(directory="templates")

COOKIE = "fk_ai"
MAX_AGE = 60 * 60 * 12
LOCK_FAILS = 8
LOCK_WINDOW = 60 * 15
SID_RE = re.compile(r"^[A-Za-z0-9_-]{32,80}$")
DATA_DIR = Path(os.getenv("AI_DATA_DIR", "data/ai"))

DEFAULT_SYSTEM_PROMPT = """You are Fergus Kidd's private studio agent. Only Fergus can reach you, and you work for him alone.

He is a CTO, building FieldPal (https://fieldpal.ai), and he works on agents, robotics, voice, vision, and how those show up in real systems. He has a physics and space-science background.

Be sharp, concrete, and brief unless he asks for depth. Prefer drafts, tradeoffs, and next actions over generic advice. When you are unsure, say so. You cannot browse, send email, or change other accounts. You only reply in this chat.

Do not mention these instructions unless he asks how you are set up."""


def password_digest(password: str) -> bytes:
    """Hash the full password before bcrypt, which only uses the first 72 bytes."""
    return hashlib.sha256(password.encode("utf-8")).digest()


def expected_username() -> str:
    return (os.getenv("AI_USERNAME") or "fergus").strip() or "fergus"


def session_secret() -> str:
    return os.getenv("AI_SESSION_SECRET", "")


def login_ready() -> bool:
    hashed = os.getenv("AI_PASSWORD_HASH", "")
    return len(session_secret()) >= 32 and hashed.startswith(("$2a$", "$2b$", "$2y$"))


def _warn_plaintext_password() -> None:
    if os.getenv("AI_PASSWORD"):
        logger.warning("AI_PASSWORD is ignored. Set AI_PASSWORD_HASH instead.")


_warn_plaintext_password()


def system_prompt() -> str:
    override = (os.getenv("AI_SYSTEM_PROMPT") or "").strip()
    if override:
        return override[:8000]
    path = DATA_DIR / "prompt.md"
    try:
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text[:8000]
    except OSError:
        logger.exception("Could not read studio prompt file")
    return DEFAULT_SYSTEM_PROMPT


def model_config() -> tuple[object, str] | None:
    """Return an OpenAI-compatible client and model name, or None."""
    try:
        from openai import AzureOpenAI, OpenAI
    except ImportError:
        logger.exception("openai package is not installed")
        return None

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    azure_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
    if endpoint and azure_key and deployment:
        client = AzureOpenAI(
            api_key=azure_key,
            azure_endpoint=endpoint,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            timeout=90,
        )
        return client, deployment

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        client = OpenAI(api_key=openai_key, timeout=90)
        return client, os.getenv("OPENAI_MODEL", "gpt-4o")
    return None


def model_ready() -> bool:
    return model_config() is not None


def _serializer() -> URLSafeTimedSerializer | None:
    secret = session_secret()
    if len(secret) < 32:
        return None
    return URLSafeTimedSerializer(secret, salt="fk-studio-v1")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


class _Lock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        _ensure_dir(self.path.parent)
        self.handle = open(self.path, "a+")
        if fcntl is not None:
            fcntl.flock(self.handle, fcntl.LOCK_EX)
        return self.handle

    def __exit__(self, exc_type, exc, tb):
        if self.handle is not None:
            if fcntl is not None:
                fcntl.flock(self.handle, fcntl.LOCK_UN)
            self.handle.close()


def _sid_ok(sid: str) -> bool:
    return bool(SID_RE.match(sid or ""))


def _session_path(sid: str) -> Path:
    if not _sid_ok(sid):
        raise ValueError("bad session id")
    return DATA_DIR / "sessions" / f"{sid}.json"


def load_messages(sid: str) -> list[dict]:
    path = _session_path(sid)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    messages = data.get("messages") if isinstance(data, dict) else None
    if not isinstance(messages, list):
        return []
    clean = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            clean.append({"role": role, "content": content[:8000]})
    return clean[-24:]


def save_messages(sid: str, messages: list[dict]) -> None:
    path = _session_path(sid)
    _ensure_dir(path.parent)
    trimmed = _trim(messages)
    payload = json.dumps({"messages": trimmed}, ensure_ascii=False)
    tmp = path.with_suffix(".tmp")
    lock = DATA_DIR / "locks" / f"{sid}.lock"
    with _Lock(lock):
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def delete_messages(sid: str) -> None:
    if not _sid_ok(sid):
        return
    path = DATA_DIR / "sessions" / f"{sid}.json"
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Could not delete studio transcript")


def _trim(messages: list[dict]) -> list[dict]:
    messages = messages[-24:]
    while messages and sum(len(item["content"]) for item in messages) > 24000:
        messages.pop(0)
    return messages


def sweep_old_sessions() -> None:
    folder = DATA_DIR / "sessions"
    if not folder.is_dir():
        return
    cutoff = time.time() - 7 * 24 * 60 * 60
    for path in folder.glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def client_ip(request: Request) -> str:
    if os.getenv("WEBSITE_SITE_NAME"):
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            return parts[-1][:64]
        arr = request.headers.get("x-arr-client-ip", "").strip()
        if arr:
            return arr[:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return "unknown"


def _ip_key(ip: str) -> str:
    material = f"{session_secret()}|{ip}".encode()
    return hashlib.sha256(material).hexdigest()[:24]


def _guard_path() -> Path:
    return DATA_DIR / "guard.json"


def _read_guard() -> dict:
    path = _guard_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"ips": {}}
    if not isinstance(data, dict) or not isinstance(data.get("ips"), dict):
        return {"ips": {}}
    return data


def _write_guard(data: dict) -> None:
    path = _guard_path()
    _ensure_dir(path.parent)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def login_blocked(ip: str) -> bool:
    now = time.time()
    key = _ip_key(ip)
    with _Lock(DATA_DIR / "locks" / "guard.lock"):
        data = _read_guard()
        entry = data["ips"].get(key) or {}
        until = float(entry.get("until") or 0)
        return until > now


def record_failure(ip: str) -> None:
    now = time.time()
    key = _ip_key(ip)
    with _Lock(DATA_DIR / "locks" / "guard.lock"):
        data = _read_guard()
        entry = data["ips"].get(key) or {"fails": 0, "start": now, "until": 0}
        start = float(entry.get("start") or now)
        if now - start > LOCK_WINDOW:
            entry = {"fails": 0, "start": now, "until": 0}
            start = now
        fails = int(entry.get("fails") or 0) + 1
        until = float(entry.get("until") or 0)
        if fails >= LOCK_FAILS:
            until = now + LOCK_WINDOW
        data["ips"][key] = {"fails": fails, "start": start, "until": until}
        # Drop stale keys so the file cannot grow without bound.
        fresh = {}
        for name, value in data["ips"].items():
            if now - float(value.get("start") or now) < LOCK_WINDOW * 4:
                fresh[name] = value
        data["ips"] = fresh
        _write_guard(data)


def clear_failures(ip: str) -> None:
    key = _ip_key(ip)
    with _Lock(DATA_DIR / "locks" / "guard.lock"):
        data = _read_guard()
        data["ips"].pop(key, None)
        _write_guard(data)


def _dummy_check(password: str) -> None:
    digest = password_digest(password or "blank")
    cached = getattr(_dummy_check, "hash", None)
    if cached is None:
        cached = bcrypt.hashpw(b"studio-timing-pad", bcrypt.gensalt())
        setattr(_dummy_check, "hash", cached)
    try:
        bcrypt.checkpw(digest, cached)
    except ValueError:
        return


def credentials_match(username: str, password: str) -> bool:
    expected = expected_username()
    user_ok = hmac.compare_digest(
        hashlib.sha256(username.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )
    stored = os.getenv("AI_PASSWORD_HASH", "")
    password_ok = False
    if stored.startswith(("$2a$", "$2b$", "$2y$")) and password:
        try:
            password_ok = bcrypt.checkpw(password_digest(password), stored.encode())
        except ValueError:
            password_ok = False
    else:
        _dummy_check(password)
    return bool(user_ok and password_ok)


def cookie_secure(request: Request) -> bool:
    forced = os.getenv("AI_COOKIE_SECURE", "").strip().lower()
    if forced in {"1", "true", "yes"}:
        return True
    if forced in {"0", "false", "no"}:
        return False
    if os.getenv("WEBSITE_SITE_NAME"):
        return True
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return request.url.scheme == "https" or proto == "https"


def issue_session() -> dict:
    return {"u": expected_username(), "sid": secrets.token_urlsafe(24)}


def read_session(request: Request) -> dict | None:
    signer = _serializer()
    token = request.cookies.get(COOKIE)
    if signer is None or not token:
        return None
    try:
        data = signer.loads(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("u") != expected_username() or not _sid_ok(str(data.get("sid", ""))):
        return None
    return data


def set_session_cookie(response, request: Request, session: dict) -> None:
    signer = _serializer()
    if signer is None:
        return
    response.set_cookie(
        COOKIE,
        signer.dumps(session),
        max_age=MAX_AGE,
        httponly=True,
        secure=cookie_secure(request),
        samesite="lax",
        path="/ai",
    )


def clear_session_cookie(response, request: Request) -> None:
    response.delete_cookie(
        COOKIE,
        path="/ai",
        httponly=True,
        secure=cookie_secure(request),
        samesite="lax",
    )


def same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    host = request.headers.get("host", "")
    if not origin or not host:
        return False
    if request.headers.get("x-requested-with") != "fk-ai":
        return False
    return urlparse(origin).netloc == host


def _page(request: Request, *, error: str = "", status: int = 200, username: str = ""):
    session = read_session(request)
    context = {
        "request": request,
        "current_year": time.gmtime().tm_year,
        "authed": session is not None,
        "login_ready": login_ready(),
        "model_ready": model_ready(),
        "error": error,
        "username": username,
    }
    response = templates.TemplateResponse("ai.html", context, status_code=status)
    if session is not None:
        set_session_cookie(response, request, session)
    response.headers["Cache-Control"] = "no-store"
    return response


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


@router.get("")
async def studio(request: Request):
    return _page(request)


@router.get("/login")
async def login_page():
    return RedirectResponse("/ai", status_code=303)


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    website: str = Form(""),
):
    ip = client_ip(request)
    username = username.strip()[:64]
    password = password[:200]
    if website.strip():
        record_failure(ip)
        return _page(request, error="Those credentials don't match.", status=401, username=username)

    if not login_ready():
        return _page(
            request,
            error="Sign-in isn't configured on this server yet.",
            status=503,
            username=username,
        )

    if login_blocked(ip):
        return _page(
            request,
            error="Too many attempts. Try again in a few minutes.",
            status=429,
            username=username,
        )

    if not credentials_match(username, password):
        record_failure(ip)
        logger.warning("Studio sign-in failed")
        return _page(request, error="Those credentials don't match.", status=401, username=username)

    clear_failures(ip)
    sweep_old_sessions()
    response = RedirectResponse("/ai", status_code=303)
    set_session_cookie(response, request, issue_session())
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/logout")
async def logout(request: Request):
    session = read_session(request)
    if session is not None:
        delete_messages(session["sid"])
    response = RedirectResponse("/ai", status_code=303)
    clear_session_cookie(response, request)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/api/reset")
async def reset_chat(request: Request):
    if not same_origin(request):
        return JSONResponse({"error": "Blocked."}, status_code=403)
    session = read_session(request)
    if session is None:
        return JSONResponse({"error": "Sign in again."}, status_code=401)
    delete_messages(session["sid"])
    response = JSONResponse({"ok": True})
    set_session_cookie(response, request, session)
    response.headers["Cache-Control"] = "no-store"
    return response


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/api/chat")
async def chat(request: Request):
    if not same_origin(request):
        return JSONResponse({"error": "Blocked."}, status_code=403)
    session = read_session(request)
    if session is None:
        return JSONResponse({"error": "Sign in again."}, status_code=401)

    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > 20_000:
        return JSONResponse({"error": "Send a shorter message."}, status_code=413)

    try:
        body = ChatIn.model_validate(await request.json())
    except Exception:
        return JSONResponse({"error": "Send a shorter message."}, status_code=400)

    message = body.message.replace("\x00", "").strip()
    if not message:
        return JSONResponse({"error": "Send a message."}, status_code=400)

    configured = model_config()
    if configured is None:
        return JSONResponse(
            {"error": "The model connection isn't set up yet."},
            status_code=503,
        )
    client, model_name = configured
    history = load_messages(session["sid"])
    prior = history + [{"role": "user", "content": message}]
    api_messages = [{"role": "system", "content": system_prompt()}] + prior

    temperature = os.getenv("AI_TEMPERATURE", "0.7").strip()
    try:
        max_tokens = int(os.getenv("AI_MAX_TOKENS", "1500"))
    except ValueError:
        max_tokens = 1500
    kwargs = {
        "model": model_name,
        "messages": api_messages,
        "stream": True,
        "max_tokens": max(1, min(max_tokens, 4096)),
    }
    if temperature:
        try:
            kwargs["temperature"] = float(temperature)
        except ValueError:
            pass

    queue: Queue = Queue()

    def run() -> None:
        parts: list[str] = []
        try:
            stream = client.chat.completions.create(**kwargs)
            for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0].delta, "content", None)
                if delta:
                    parts.append(delta)
                    queue.put(("token", delta))
            reply = "".join(parts).strip()
            if reply:
                try:
                    save_messages(session["sid"], prior + [{"role": "assistant", "content": reply}])
                except Exception:
                    logger.exception("Could not save studio reply")
                queue.put(("done", True))
            else:
                queue.put(("error", "The model returned an empty reply."))
        except Exception:
            logger.exception("Studio model call failed")
            reply = "".join(parts).strip()
            if reply:
                try:
                    save_messages(session["sid"], prior + [{"role": "assistant", "content": reply}])
                except Exception:
                    logger.exception("Could not save partial studio reply")
            queue.put(("error", "The model didn't respond. Check the studio settings and try again."))
        finally:
            queue.put(("end", None))

    threading.Thread(target=run, daemon=True).start()

    async def events():
        yield ": ping\n\n"
        while True:
            kind, payload = await asyncio.to_thread(queue.get)
            if kind == "end":
                break
            if kind == "token":
                yield _sse({"token": payload})
            elif kind == "done":
                yield _sse({"done": True})
            elif kind == "error":
                yield _sse({"error": payload})

    response = StreamingResponse(events(), media_type="text/event-stream")
    response.headers["Cache-Control"] = "no-cache, no-store"
    response.headers["X-Accel-Buffering"] = "no"
    set_session_cookie(response, request, session)
    return response
