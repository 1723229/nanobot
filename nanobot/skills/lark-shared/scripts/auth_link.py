#!/usr/bin/env python3
"""Start Lark auth/config flows and return the extracted authorization URL as JSON."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Any

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_AUTH_KEYWORDS = ("auth", "oauth", "login", "authorize", "consent", "verify")
_LARK_HOST_KEYWORDS = ("feishu", "larksuite", "larkoffice")


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


def extract_candidate_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for url in _URL_RE.findall(text or ""):
        cleaned = url.rstrip(".,);]")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
    return urls


def _collect_urls(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, str):
        return extract_candidate_urls(value)
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and "url" in key.lower() and isinstance(item, str):
                urls.extend(extract_candidate_urls(item) or ([item] if item.startswith("http") else []))
            else:
                urls.extend(_collect_urls(item))
        return urls
    if isinstance(value, list):
        for item in value:
            urls.extend(_collect_urls(item))
    return urls


def choose_auth_url(urls: list[str]) -> str:
    if not urls:
        return ""

    def _score(url: str) -> tuple[int, int]:
        lower = url.lower()
        score = 0
        if any(host in lower for host in _LARK_HOST_KEYWORDS):
            score += 20
        if any(keyword in lower for keyword in _AUTH_KEYWORDS):
            score += 20
        if "open.feishu.cn" in lower or "open.larksuite.com" in lower:
            score += 10
        if "passport.feishu.cn" in lower or "passport.larksuite.com" in lower:
            score += 10
        if "/document/" in lower or "/docs/" in lower or "llms.txt" in lower:
            score -= 15
        return score, -urls.index(url)

    return max(urls, key=_score)


def extract_auth_url(raw_output: str) -> str:
    payload = parse_json_output(raw_output)
    urls = _collect_urls(payload)
    urls.extend(extract_candidate_urls(raw_output))

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return choose_auth_url(deduped)


def tail_text(text: str, limit: int = 1200) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def decode_output(raw: bytes | str | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    return raw.decode("utf-8", errors="replace")


def read_text_file(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            return decode_output(fh.read())
    except FileNotFoundError:
        return ""


def cleanup_temp_file(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def build_cli_command(*args: str) -> list[str]:
    lark_cli = shutil.which("lark-cli")
    if lark_cli:
        return [lark_cli, *args]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "@larksuite/cli", *args]
    return ["lark-cli", *args]


def build_auth_login_command(*, scope: str = "", domain: str = "") -> list[str]:
    if scope and domain:
        raise ValueError("scope_and_domain_mutually_exclusive")
    command = build_cli_command("auth", "login", "--no-wait")
    if scope:
        command.extend(["--scope", scope])
    elif domain:
        command.extend(["--domain", domain])
    else:
        raise ValueError("scope_or_domain_required")
    return command


def build_config_init_command() -> list[str]:
    return build_cli_command("config", "init", "--new")


def run_lark_cli(command: list[str], *, timeout: int = 30) -> dict[str, Any]:
    executable = command[0] if command else ""
    if not executable or (not shutil.which(executable) and not shutil.which("lark-cli") and not shutil.which("npx")):
        return {
            "success": False,
            "error": "lark_cli_not_found",
            "message": "lark-cli or npx not found",
            "command": command,
            "exit_code": None,
            "auth_url": "",
            "stdout": "",
            "stderr": "",
        }
    try:
        run_command: list[str] = command
        if sys.platform == "win32" and executable.lower().endswith((".cmd", ".bat")):
            comspec = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
            run_command = [comspec, "/c", *command]
        stdout_fd, stdout_path = tempfile.mkstemp()
        stderr_fd, stderr_path = tempfile.mkstemp()
        os.close(stdout_fd)
        os.close(stderr_fd)
        with open(stdout_path, "ab") as stdout_fh, open(stderr_path, "ab") as stderr_fh:
            process = subprocess.Popen(
                run_command,
                stdout=stdout_fh,
                stderr=stderr_fh,
                text=False,
                start_new_session=sys.platform != "win32",
            )
            try:
                return_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        text=False,
                        check=False,
                    )
                else:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except OSError:
                        process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                stdout_fh.flush()
                stderr_fh.flush()
                stdout_fh.close()
                stderr_fh.close()
                stdout = read_text_file(stdout_path)
                stderr = read_text_file(stderr_path)
                cleanup_temp_file(stdout_path)
                cleanup_temp_file(stderr_path)
                combined = f"{stdout}\n{stderr}".strip()
                auth_url = extract_auth_url(combined)
                return {
                    "success": bool(auth_url),
                    "error": "timeout",
                    "message": f"command timed out after {timeout}s",
                    "command": command,
                    "exit_code": None,
                    "auth_url": auth_url,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_tail": tail_text(stdout),
                    "stderr_tail": tail_text(stderr),
                }
        stdout = read_text_file(stdout_path)
        stderr = read_text_file(stderr_path)
        cleanup_temp_file(stdout_path)
        cleanup_temp_file(stderr_path)
    except Exception as exc:
        return {
            "success": False,
            "error": "spawn_failed",
            "message": str(exc),
            "command": command,
            "exit_code": None,
            "auth_url": "",
            "stdout": "",
            "stderr": "",
            "stdout_tail": "",
            "stderr_tail": "",
        }
    combined = "\n".join(part for part in [stdout, stderr] if part)
    auth_url = extract_auth_url(combined)
    return {
        "success": bool(auth_url) or return_code == 0,
        "error": "" if (auth_url or return_code == 0) else "command_failed",
        "message": "auth_url_extracted" if auth_url else f"exit_code={return_code}",
        "command": command,
        "exit_code": return_code,
        "auth_url": auth_url,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_tail": tail_text(stdout),
        "stderr_tail": tail_text(stderr),
    }


def start_auth_login(*, scope: str = "", domain: str = "", timeout: int = 30) -> dict[str, Any]:
    result = run_lark_cli(build_auth_login_command(scope=scope, domain=domain), timeout=timeout)
    result["action"] = "auth_login"
    result["scope"] = scope
    result["domain"] = domain
    return result


def start_config_init(*, timeout: int = 30) -> dict[str, Any]:
    result = run_lark_cli(build_config_init_command(), timeout=timeout)
    result["action"] = "config_init"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch Lark auth flow and extract auth URL")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login")
    login.add_argument("--scope", default="")
    login.add_argument("--domain", default="")
    login.add_argument("--timeout", type=int, default=30)

    config_init = subparsers.add_parser("config-init")
    config_init.add_argument("--timeout", type=int, default=30)

    args = parser.parse_args(argv)

    try:
        if args.command == "login":
            result = start_auth_login(scope=args.scope, domain=args.domain, timeout=args.timeout)
        else:
            result = start_config_init(timeout=args.timeout)
    except ValueError as exc:
        error = str(exc)
        message = "login requires --scope or --domain"
        if error == "scope_and_domain_mutually_exclusive":
            message = "login accepts only one of --scope or --domain"
        result = {
            "success": False,
            "error": error,
            "message": message,
            "auth_url": "",
            "action": args.command,
        }

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
