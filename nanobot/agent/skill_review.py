"""Background review service for generated skill evolution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.agent.skill_store import SkillMutationResult, SkillStore
from nanobot.agent.skills import SkillsLoader
from nanobot.utils.helpers import current_time_str, truncate_text
from nanobot.utils.prompt_templates import render_template

if TYPE_CHECKING:
    from nanobot.config.schema import SkillsConfig
    from nanobot.providers.base import LLMProvider


@dataclass(slots=True)
class SkillReviewProposal:
    """Parsed structured review decision from the model."""

    action: str
    skill_name: str | None
    reason: str
    content: str | None = None
    supporting_files: dict[str, str] | None = None


class SkillReviewService:
    """Review completed turns and evolve generated skills asynchronously."""

    _MAX_BLOCK_CHARS = 4000

    def __init__(
        self,
        provider: "LLMProvider",
        workspace: Path,
        model: str,
        *,
        config: "SkillsConfig",
        provider_retry_mode: str = "standard",
        builtin_skills_dir: Path | None = None,
    ) -> None:
        self.provider = provider
        self.workspace = workspace
        self.model = model
        self.config = config
        self.provider_retry_mode = provider_retry_mode
        self.loader = SkillsLoader(workspace, builtin_skills_dir=builtin_skills_dir)
        self.store = SkillStore(
            workspace,
            builtin_skills_dir=builtin_skills_dir,
            allow_create=config.allow_create,
            allow_patch=config.allow_patch,
            allow_delete=config.allow_delete,
        )

    def should_review(self, recent_messages: list[dict[str, Any]]) -> bool:
        if not self.config.enabled or not self.config.review_enabled:
            return False
        if self.config.review_mode == "off":
            return False
        if self._agent_already_managed_skills(recent_messages):
            return False

        tool_calls = self._count_tool_calls(recent_messages)
        iterations = sum(1 for msg in recent_messages if msg.get("role") == "assistant")
        used_skills = self._extract_used_skill_names(recent_messages)
        return (
            tool_calls >= self.config.review_min_tool_calls
            or iterations >= self.config.review_trigger_iterations
            or bool(used_skills)
        )

    async def review_turn(
        self,
        *,
        session_key: str,
        recent_messages: list[dict[str, Any]],
        final_content: str,
        stop_reason: str,
        user_message: str,
    ) -> SkillMutationResult | None:
        if stop_reason == "error" or not recent_messages or not self.should_review(recent_messages):
            return None

        try:
            proposal = await self._propose(
                session_key=session_key,
                recent_messages=recent_messages,
                final_content=final_content,
                user_message=user_message,
            )
            if proposal is None or proposal.action == "ignore":
                return None
            return self._apply_proposal(proposal)
        except Exception:
            logger.exception("SkillReview failed for session {}", session_key)
            return None

    async def _propose(
        self,
        *,
        session_key: str,
        recent_messages: list[dict[str, Any]],
        final_content: str,
        user_message: str,
    ) -> SkillReviewProposal | None:
        used_skill_names = self._extract_used_skill_names(recent_messages)
        used_skills_context = self._build_used_skills_context(used_skill_names)
        transcript = self._render_recent_messages(recent_messages)
        existing_skills_summary = self._build_existing_skills_summary()
        prompt = render_template(
            "agent/skill_review.md",
            current_time=current_time_str(),
            session_key=session_key,
            review_mode=self.config.review_mode,
            user_message=user_message,
            final_content=truncate_text(final_content, self._MAX_BLOCK_CHARS),
            recent_messages=transcript,
            used_skills_context=used_skills_context,
            existing_skills_summary=existing_skills_summary,
        )
        response = await self.provider.chat_with_retry(
            messages=[{"role": "system", "content": prompt}],
            tools=None,
            model=self.config.review_model_override or self.model,
            retry_mode=self.provider_retry_mode,
        )
        if response.finish_reason == "error" or not response.content:
            logger.warning(
                "SkillReview model call returned no usable content for session {}: {}",
                session_key,
                (response.content or "")[:200],
            )
            return None
        return self._parse_proposal(response.content)

    def _apply_proposal(self, proposal: SkillReviewProposal) -> SkillMutationResult | None:
        if proposal.content is None or not proposal.skill_name:
            return None
        if self.config.review_mode == "suggest":
            logger.info(
                "SkillReview suggestion ignored by config: action={} skill={} reason={}",
                proposal.action,
                proposal.skill_name,
                proposal.reason,
            )
            return None

        target_name = proposal.skill_name
        existing = self.loader.get_skill_entry(target_name)

        if proposal.action == "create":
            if self.config.review_mode != "auto_create":
                return None
            if existing and existing["source"] == "generated":
                result = self.store.edit_skill(
                    target_name,
                    proposal.content,
                    reason=proposal.reason,
                    session_key="skill-review",
                )
            elif existing and existing["source"] == "workspace":
                target_name = self._derive_generated_name(target_name)
                result = self.store.create_skill(
                    target_name,
                    proposal.content,
                    reason=proposal.reason,
                    session_key="skill-review",
                    origin_skill=None if existing is None else existing["name"],
                    origin_source=None if existing is None else existing["source"],
                )
            else:
                result = self.store.create_skill(
                    target_name,
                    proposal.content,
                    reason=proposal.reason,
                    session_key="skill-review",
                    origin_skill=None if existing is None else existing["name"],
                    origin_source=None if existing is None else existing["source"],
                )
        else:
            if existing is None and self.config.review_mode != "auto_create":
                return None
            if existing and existing["source"] == "generated":
                result = self.store.edit_skill(
                    target_name,
                    proposal.content,
                    reason=proposal.reason,
                    session_key="skill-review",
                )
            elif existing and existing["source"] == "builtin":
                result = self.store.create_skill(
                    target_name,
                    proposal.content,
                    reason=proposal.reason,
                    session_key="skill-review",
                    origin_skill=existing["name"],
                    origin_source=existing["source"],
                )
            elif existing and existing["source"] == "workspace":
                target_name = self._derive_generated_name(target_name)
                result = self.store.create_skill(
                    target_name,
                    proposal.content,
                    reason=proposal.reason,
                    session_key="skill-review",
                    origin_skill=existing["name"],
                    origin_source=existing["source"],
                )
            else:
                if self.config.review_mode != "auto_create":
                    return None
                result = self.store.create_skill(
                    target_name,
                    proposal.content,
                    reason=proposal.reason,
                    session_key="skill-review",
                )

        if proposal.supporting_files:
            for file_path, content in proposal.supporting_files.items():
                self.store.write_file(
                    target_name,
                    file_path,
                    content,
                    reason=proposal.reason,
                    session_key="skill-review",
                )
        return result

    def _derive_generated_name(self, base_name: str) -> str:
        candidate = f"{base_name}-generated"
        index = 2
        while self.loader.get_skill_entry(candidate):
            candidate = f"{base_name}-generated-{index}"
            index += 1
        return candidate

    @staticmethod
    def _count_tool_calls(recent_messages: list[dict[str, Any]]) -> int:
        count = 0
        for msg in recent_messages:
            if msg.get("role") != "assistant":
                continue
            count += len(msg.get("tool_calls") or [])
        return count

    @staticmethod
    def _agent_already_managed_skills(recent_messages: list[dict[str, Any]]) -> bool:
        """Return True if the agent called ``skill_manage`` during this turn."""
        for msg in recent_messages:
            if msg.get("role") != "assistant":
                continue
            for call in msg.get("tool_calls") or []:
                fn = (call.get("function") or {}).get("name")
                if fn == "skill_manage":
                    return True
        return False

    @staticmethod
    def _extract_json_blob(text: str) -> str | None:
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return stripped[start:end + 1]

    def _parse_proposal(self, raw: str) -> SkillReviewProposal | None:
        blob = self._extract_json_blob(raw)
        if not blob:
            logger.warning("SkillReview returned non-JSON payload: {}", raw[:300])
            return None
        try:
            payload = json.loads(blob)
        except json.JSONDecodeError:
            logger.warning("SkillReview returned invalid JSON: {}", raw[:300])
            return None
        if not isinstance(payload, dict):
            return None

        action = str(payload.get("action") or "ignore").strip().lower()
        if action not in {"ignore", "create", "update"}:
            action = "ignore"
        skill_name = payload.get("skill_name")
        if skill_name is not None:
            skill_name = str(skill_name).strip()
        reason = str(payload.get("reason") or "").strip()
        content = payload.get("content")
        if content is not None:
            content = str(content)
        supporting_files = payload.get("supporting_files")
        if not isinstance(supporting_files, dict):
            supporting_files = None
        else:
            supporting_files = {str(k): str(v) for k, v in supporting_files.items()}
        return SkillReviewProposal(
            action=action,
            skill_name=skill_name or None,
            reason=reason,
            content=content,
            supporting_files=supporting_files,
        )

    def _build_existing_skills_summary(self) -> str:
        entries = self.loader.list_skills(filter_unavailable=False)
        if not entries:
            return "None"
        lines: list[str] = []
        for entry in entries:
            meta = self.loader.get_skill_metadata(entry["name"]) or {}
            desc = meta.get("description", entry["name"])
            lines.append(f"- {entry['name']} ({entry['source']}): {desc}")
        return "\n".join(lines)

    def _build_used_skills_context(self, skill_names: list[str]) -> str:
        if not skill_names:
            return "None"
        parts: list[str] = []
        for name in skill_names[:3]:
            entry = self.loader.get_skill_entry(name)
            if not entry:
                continue
            body = self.loader.load_skill(name) or ""
            parts.append(
                f"## Skill: {name}\n"
                f"source: {entry['source']}\n"
                f"mutable: {str(self.loader.is_mutable(name)).lower()}\n\n"
                f"{truncate_text(body, self._MAX_BLOCK_CHARS)}"
            )
        return "\n\n".join(parts) if parts else "None"

    def _render_recent_messages(self, recent_messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for msg in recent_messages[-self.config.review_max_messages:]:
            role = msg.get("role", "unknown")
            if role == "assistant" and msg.get("tool_calls"):
                lines.append(f"[assistant.tool_calls] {self._render_tool_calls(msg.get('tool_calls') or [])}")
                content = (msg.get("content") or "").strip()
                if content:
                    lines.append(f"[assistant] {truncate_text(content, self._MAX_BLOCK_CHARS)}")
                continue
            if role == "tool":
                name = msg.get("name", "tool")
                content = str(msg.get("content") or "")
                lines.append(f"[tool:{name}] {truncate_text(content, self._MAX_BLOCK_CHARS)}")
                continue
            content = msg.get("content")
            if isinstance(content, list):
                content = json.dumps(content, ensure_ascii=False)
            lines.append(f"[{role}] {truncate_text(str(content or ''), self._MAX_BLOCK_CHARS)}")
        return "\n".join(lines)

    @staticmethod
    def _render_tool_calls(tool_calls: list[dict[str, Any]]) -> str:
        rendered: list[str] = []
        for call in tool_calls:
            function = call.get("function") or {}
            name = function.get("name") or "tool"
            arguments = function.get("arguments") or "{}"
            rendered.append(f"{name}({arguments})")
        return "; ".join(rendered)

    @staticmethod
    def _extract_used_skill_names(recent_messages: list[dict[str, Any]]) -> list[str]:
        names: list[str] = []
        pending: dict[str, str] = {}
        for msg in recent_messages:
            if msg.get("role") == "assistant":
                for call in msg.get("tool_calls") or []:
                    function = call.get("function") or {}
                    if function.get("name") != "skill_view":
                        continue
                    try:
                        args = json.loads(function.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        continue
                    skill_name = args.get("name")
                    if isinstance(skill_name, str):
                        pending[str(call.get("id"))] = skill_name
            elif msg.get("role") == "tool" and msg.get("name") == "skill_view":
                skill_name = pending.get(str(msg.get("tool_call_id")))
                if skill_name and skill_name not in names:
                    names.append(skill_name)
        return names
