"""Self-improvement hook — detect errors and remind agent to log learnings."""

from __future__ import annotations

import re
from typing import Any

from loguru import logger

from nanobot.hooks.base import Hook, HookContext


_ERROR_PATTERNS = re.compile(
    r"error|exception|traceback|failed|errno|permission denied|not found"
    r"|command not found|no such file|segfault|segmentation fault|panic|fatal"
    r"|npm ERR!|SyntaxError|TypeError|ModuleNotFoundError"
    r"|exit code|non-zero",
    re.IGNORECASE,
)

_REMINDER = (
    "\n\n---\n[self-improvement] A command error was detected. "
    "Consider logging to `.learnings/ERRORS.md` if:\n"
    "- The error was unexpected or non-obvious\n"
    "- It required investigation to resolve\n"
    "- It might recur in similar contexts\n"
    "- The solution could benefit future sessions\n"
    "Use the self-improvement skill format: [ERR-YYYYMMDD-XXX]"
)


class SelfImprovementHook(Hook):
    """On tool.post_call for exec/shell: detect errors and append a reminder."""

    name = "self_improvement"

    async def execute(self, context: HookContext, **kwargs: Any) -> Any:
        tool_name = kwargs.get("tool_name", "")
        result = kwargs.get("result", "")

        if tool_name not in ("exec", "shell"):
            return {"tool_name": tool_name, "result": result}

        result_str = str(result) if result else ""
        if not result_str:
            return {"tool_name": tool_name, "result": result}

        if _ERROR_PATTERNS.search(result_str):
            logger.debug("Self-improvement hook detected potential error in {} output", tool_name)
            return {"tool_name": tool_name, "result": result_str + _REMINDER}

        return {"tool_name": tool_name, "result": result}


def register_self_improvement_hooks(hook_manager: Any) -> None:
    """Register self-improvement hooks."""
    hook_manager.register("tool.post_call", SelfImprovementHook())
    logger.info("Registered self-improvement hook (tool.post_call)")
