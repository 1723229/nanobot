#!/usr/bin/env python3
"""
Manage a background DingTalk device-flow auth session for dws.

This helper solves two problems:
1. Start `dws auth login --device` in the background and keep it alive while
   the user completes authorization in the browser.
2. Read the authorization URL from the session log and return it as JSON so
   the agent can send only the link to the user.

Usage:
    # Unified entrypoint: authenticated => no link; unauthenticated => auth_url
    python auth_device_session.py status --session dingtalk:4321

    # Probe only: inspect the current background auth session without auto-start
    python auth_device_session.py probe --session dingtalk:4321

    # Compatibility commands
    python auth_device_session.py start --session dingtalk:4321
    python auth_device_session.py cleanup --session dingtalk:4321
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


AUTH_URL_RE = re.compile(
    r"https://login\.dingtalk\.com/oauth2/device/verify\.htm\?[^\s\"'>]+"
)
SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def dws_config_dir() -> Path:
    raw = os.environ.get("DWS_CONFIG_DIR")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".dws"


def session_store_dir() -> Path:
    path = dws_config_dir() / "logs" / "device-auth"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_name(value: str) -> str:
    cleaned = SAFE_NAME_RE.sub("_", (value or "").strip())
    return cleaned or "default"


def state_path(session: str) -> Path:
    return session_store_dir() / f"{safe_name(session)}.json"


def log_path(session: str) -> Path:
    return session_store_dir() / f"{safe_name(session)}.log"


def load_state(session: str) -> dict[str, Any]:
    path = state_path(session)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_state(session: str, payload: dict[str, Any]) -> None:
    state_path(session).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def remove_session_files(session: str, state: dict[str, Any] | None = None) -> None:
    current = state or load_state(session)
    paths = [state_path(session)]
    custom_log = current.get("log_path")
    if custom_log:
        paths.append(Path(str(custom_log)))
    else:
        paths.append(log_path(session))
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def merge_state(session: str, **updates: Any) -> dict[str, Any]:
    state = load_state(session)
    state.update({k: v for k, v in updates.items() if v is not None})
    save_state(session, state)
    return state


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def kill_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.killpg(pid, signal.SIGTERM)
        return True
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False


def read_log_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def extract_auth_url(text: str) -> str:
    matches = AUTH_URL_RE.findall(text or "")
    return matches[-1] if matches else ""


def tail_text(text: str, limit: int = 1200) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def parse_json_output(raw_output: str) -> dict[str, Any]:
    text = (raw_output or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        return data
    for line in reversed([item.strip() for item in text.splitlines() if item.strip()]):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def run_dws_status() -> dict[str, Any]:
    if not shutil.which("dws"):
        return {
            "ok": False,
            "authenticated": False,
            "error": "dws_not_installed",
            "message": "dws not found",
        }
    env = dict(os.environ)
    env["DWS_CONFIG_DIR"] = str(dws_config_dir())
    try:
        result = subprocess.run(
            ["dws", "auth", "status", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=20,
            env=env,
            check=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "authenticated": False,
            "error": f"status_failed:{exc}",
            "message": str(exc),
        }
    payload = parse_json_output(result.stdout)
    authenticated = bool(payload.get("authenticated"))
    return {
        "ok": bool(payload),
        "authenticated": authenticated,
        "payload": payload,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "message": str(payload.get("message") or "").strip(),
    }


def poll_for_auth_url(path: Path, wait_seconds: int) -> str:
    deadline = time.monotonic() + max(wait_seconds, 0)
    while True:
        auth_url = extract_auth_url(read_log_text(path))
        if auth_url:
            return auth_url
        if time.monotonic() >= deadline:
            return ""
        time.sleep(0.5)


def start_auth_session(session: str, wait_seconds: int) -> dict[str, Any]:
    status = run_dws_status()
    if status.get("authenticated"):
        return {
            "success": True,
            "session": session,
            "action": "already_authenticated",
            "authenticated": True,
            "running": False,
            "auth_url": "",
            "pid": None,
            "log_path": str(log_path(session)),
            "state_path": str(state_path(session)),
            "message": "already authenticated",
            "status": status.get("payload") or {},
        }

    state = load_state(session)
    pid = int(state.get("pid") or 0)
    current_log = Path(state.get("log_path") or log_path(session))
    if pid and is_pid_running(pid):
        auth_url = poll_for_auth_url(current_log, wait_seconds) or str(
            state.get("auth_url") or state.get("last_auth_url") or ""
        )
        if auth_url:
            state = merge_state(session, auth_url=auth_url, last_auth_url=auth_url)
        return {
            "success": True,
            "session": session,
            "action": "reused",
            "authenticated": False,
            "running": True,
            "auth_url": auth_url,
            "pid": pid,
            "log_path": str(current_log),
            "state_path": str(state_path(session)),
            "message": "existing auth session reused",
            "log_tail": tail_text(read_log_text(current_log)),
        }

    current_log = log_path(session)
    current_log.write_text("", encoding="utf-8")
    env = dict(os.environ)
    env["DWS_CONFIG_DIR"] = str(dws_config_dir())

    with current_log.open("ab") as log_fp:
        process = subprocess.Popen(
            ["dws", "auth", "login", "--device"],
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=str(Path.home()),
            env=env,
            start_new_session=True,
        )

    payload = {
        "session": session,
        "pid": process.pid,
        "log_path": str(current_log),
        "started_at": int(time.time()),
        "command": ["dws", "auth", "login", "--device"],
        "auth_url": "",
    }
    save_state(session, payload)
    auth_url = poll_for_auth_url(current_log, wait_seconds)
    if auth_url:
        payload = merge_state(session, auth_url=auth_url, last_auth_url=auth_url)
    log_text = read_log_text(current_log)
    return {
        "success": True,
        "session": session,
        "action": "started",
        "authenticated": False,
        "running": is_pid_running(process.pid),
        "auth_url": auth_url,
        "pid": process.pid,
        "log_path": str(current_log),
        "state_path": str(state_path(session)),
        "message": "background auth session started",
        "log_tail": tail_text(log_text),
    }


def auth_session_status(session: str, wait_seconds: int) -> dict[str, Any]:
    dws_status = run_dws_status()
    if dws_status.get("authenticated"):
        state = load_state(session)
        running = is_pid_running(int(state.get("pid") or 0))
        result = {
            "success": True,
            "session": session,
            "action": "already_authenticated",
            "authenticated": True,
            "running": running,
            "pid": int(state.get("pid") or 0) or None,
            "auth_url": "",
            "auth_url_available": False,
            "log_path": str(Path(state.get("log_path") or log_path(session))),
            "state_path": str(state_path(session)),
            "status": dws_status.get("payload") or {},
            "message": dws_status.get("message") or "",
            "log_tail": "",
        }
        if not running:
            remove_session_files(session, state)
            result["state_cleaned"] = True
        return result

    # Unified entrypoint: unauthenticated status requests automatically
    # reuse an existing device-flow session or start a new one and return
    # the resulting authorization link when available.
    result = start_auth_session(session, wait_seconds)
    result["entrypoint"] = "status"
    return result


def auth_session_probe(session: str) -> dict[str, Any]:
    state = load_state(session)
    current_log = Path(state.get("log_path") or log_path(session))
    pid = int(state.get("pid") or 0)
    running = is_pid_running(pid)
    dws_status = run_dws_status()
    log_text = read_log_text(current_log)
    fresh_auth_url = extract_auth_url(log_text)
    stored_auth_url = str(state.get("auth_url") or state.get("last_auth_url") or "")
    auth_url = fresh_auth_url or (stored_auth_url if running else "")
    if fresh_auth_url and fresh_auth_url != state.get("auth_url"):
        state = merge_state(session, auth_url=auth_url, last_auth_url=auth_url)
    result = {
        "success": True,
        "session": session,
        "authenticated": bool(dws_status.get("authenticated")),
        "running": running,
        "pid": pid or None,
        "auth_url": auth_url,
        "auth_url_available": bool(auth_url),
        "log_path": str(current_log),
        "state_path": str(state_path(session)),
        "status": dws_status.get("payload") or {},
        "message": dws_status.get("message") or "",
        "log_tail": tail_text(log_text),
    }
    if not result["authenticated"] and not result["running"]:
        result["needs_restart"] = True
        result["auth_url"] = ""
        result["auth_url_available"] = False
        result["message"] = (
            result["message"]
            or "auth session is no longer running; cleanup and restart the device flow instead of reusing an old link"
        )
    elif not result["authenticated"] and not result["auth_url"]:
        result["needs_restart"] = True
        result["message"] = (
            result["message"]
            or "auth session has no reusable authorization URL; restart the device flow instead of inventing a link"
        )
    if result["authenticated"] and not running:
        remove_session_files(session, state)
        result["state_cleaned"] = True
    return result


def cleanup_auth_session(session: str) -> dict[str, Any]:
    state = load_state(session)
    pid = int(state.get("pid") or 0)
    killed = kill_pid(pid) if pid else False
    remove_session_files(session, state)
    return {
        "success": True,
        "session": session,
        "pid": pid or None,
        "killed": killed,
        "log_path": str(Path(state.get("log_path") or log_path(session))),
        "state_path": str(state_path(session)),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage background dws device auth")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--session", default="default")
    start.add_argument("--wait-seconds", type=int, default=10)

    status = sub.add_parser("status")
    status.add_argument("--session", default="default")
    status.add_argument("--wait-seconds", type=int, default=10)

    probe = sub.add_parser("probe")
    probe.add_argument("--session", default="default")

    cleanup = sub.add_parser("cleanup")
    cleanup.add_argument("--session", default="default")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "start":
            result = start_auth_session(args.session, args.wait_seconds)
        elif args.command == "status":
            result = auth_session_status(args.session, args.wait_seconds)
        elif args.command == "probe":
            result = auth_session_probe(args.session)
        else:
            result = cleanup_auth_session(args.session)
    except FileNotFoundError as exc:
        result = {
            "success": False,
            "error": "file_not_found",
            "message": str(exc),
        }
    except Exception as exc:
        result = {
            "success": False,
            "error": exc.__class__.__name__,
            "message": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
