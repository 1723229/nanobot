"""Dedicated tools for skill discovery and viewing."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.agent.skill_store import SkillStore
from nanobot.agent.skills import SkillsLoader
from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import BooleanSchema, StringSchema, tool_parameters_schema
from nanobot.utils.helpers import build_image_content_blocks, detect_image_mime

if TYPE_CHECKING:
    from nanobot.config.schema import SkillsConfig


def _serialize_skill(loader: SkillsLoader, entry: dict[str, str]) -> dict[str, Any]:
    meta = loader.get_skill_metadata(entry["name"]) or {}
    return {
        "name": entry["name"],
        "description": meta.get("description", entry["name"]),
        "source": entry["source"],
        "available": loader._check_requirements(loader._get_skill_meta(entry["name"])),
        "mutable": loader.is_mutable(entry["name"]),
        "path": entry["path"],
        "supporting_files": loader.list_supporting_files(entry["name"]),
    }


@tool_parameters(
    tool_parameters_schema(
        include_unavailable=BooleanSchema(
            description="Whether to include skills whose requirements are not currently met",
            default=True,
        ),
    )
)
class SkillsListTool(Tool):
    """List available skills with source and mutability metadata."""

    def __init__(self, workspace: Path, builtin_skills_dir: Path | None = None):
        self._loader = SkillsLoader(workspace, builtin_skills_dir=builtin_skills_dir)

    @property
    def name(self) -> str:
        return "skills_list"

    @property
    def description(self) -> str:
        return (
            "List available skills with summary metadata. "
            "Use this before skill_view to discover the right skill."
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, include_unavailable: bool = True, **kwargs: Any) -> str:
        entries = self._loader.list_skills(filter_unavailable=not include_unavailable)
        payload = [_serialize_skill(self._loader, entry) for entry in entries]
        return json.dumps(payload, ensure_ascii=False, indent=2)


@tool_parameters(
    tool_parameters_schema(
        name=StringSchema("Skill name to view", min_length=1),
        file_path=StringSchema(
            "Optional supporting file path relative to the skill root, for example references/guide.md",
            nullable=True,
        ),
        required=["name"],
    )
)
class SkillViewTool(Tool):
    """Read a full skill or one of its supporting files."""

    def __init__(self, workspace: Path, builtin_skills_dir: Path | None = None):
        self._loader = SkillsLoader(workspace, builtin_skills_dir=builtin_skills_dir)

    @property
    def name(self) -> str:
        return "skill_view"

    @property
    def description(self) -> str:
        return (
            "Read a skill's SKILL.md or one allowed supporting file under "
            "references/, templates/, scripts/, or assets/."
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, name: str, file_path: str | None = None, **kwargs: Any) -> Any:
        entry = self._loader.get_skill_entry(name)
        if not entry:
            return f"Error: Skill not found: {name}"

        raw = self._loader.load_skill_file(name, file_path)
        if raw is None:
            if file_path:
                return (
                    f"Error: Cannot read skill file '{file_path}' for skill '{name}'. "
                    "Only files under references/, templates/, scripts/, or assets/ are allowed."
                )
            return f"Error: Skill not found: {name}"

        if isinstance(raw, str):
            return raw

        mime = detect_image_mime(raw) or mimetypes.guess_type(file_path or entry["path"])[0]
        if mime and mime.startswith("image/"):
            target_path = file_path or entry["path"]
            return build_image_content_blocks(raw, mime, target_path, f"(Skill image file: {target_path})")

        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            target_path = file_path or entry["path"]
            return (
                f"Error: Cannot read binary skill file '{target_path}'. "
                "Only UTF-8 text and images are supported."
            )


@tool_parameters(
    tool_parameters_schema(
        action=StringSchema(
            "Mutation action to perform on generated skills",
            enum=("create", "edit", "patch", "delete", "write_file", "remove_file"),
        ),
        name=StringSchema("Skill name to create or mutate", min_length=1),
        content=StringSchema(
            "Full SKILL.md content for create/edit, or supporting file content for write_file",
            nullable=True,
        ),
        file_path=StringSchema(
            "Supporting file path relative to the skill root for patch/write_file/remove_file",
            nullable=True,
        ),
        old_text=StringSchema("Text to replace for patch", nullable=True),
        new_text=StringSchema("Replacement text for patch", nullable=True),
        replace_all=BooleanSchema(description="Replace all matches for patch (default false)"),
        reason=StringSchema("Optional short reason recorded in skill-events.jsonl", nullable=True),
        session_key=StringSchema("Optional session key recorded in skill-events.jsonl", nullable=True),
        required=["action", "name"],
    )
)
class SkillManageTool(Tool):
    """Create and mutate generated skills through the controlled store."""

    def __init__(
        self,
        workspace: Path,
        builtin_skills_dir: Path | None = None,
        skills_config: "SkillsConfig | None" = None,
    ):
        self._store = SkillStore(
            workspace,
            builtin_skills_dir=builtin_skills_dir,
            allow_create=True if skills_config is None else skills_config.allow_create,
            allow_patch=True if skills_config is None else skills_config.allow_patch,
            allow_delete=False if skills_config is None else skills_config.allow_delete,
        )

    @property
    def name(self) -> str:
        return "skill_manage"

    @property
    def description(self) -> str:
        return (
            "Create or modify generated skills (mutable layer) only. "
            "Supports create, edit, patch, delete, write_file, and remove_file."
        )

    async def execute(
        self,
        action: str,
        name: str,
        content: str | None = None,
        file_path: str | None = None,
        old_text: str | None = None,
        new_text: str | None = None,
        replace_all: bool = False,
        reason: str | None = None,
        session_key: str | None = None,
        **kwargs: Any,
    ) -> str:
        try:
            if action == "create":
                if content is None:
                    return "Error: content is required for skill_manage(create)."
                result = self._store.create_skill(
                    name,
                    content,
                    reason=reason,
                    session_key=session_key,
                )
            elif action == "edit":
                if content is None:
                    return "Error: content is required for skill_manage(edit)."
                result = self._store.edit_skill(
                    name,
                    content,
                    reason=reason,
                    session_key=session_key,
                )
            elif action == "patch":
                if old_text is None or new_text is None:
                    return "Error: old_text and new_text are required for skill_manage(patch)."
                result = self._store.patch_skill(
                    name,
                    old_text,
                    new_text,
                    file_path=file_path,
                    replace_all=replace_all,
                    reason=reason,
                    session_key=session_key,
                )
            elif action == "delete":
                result = self._store.delete_skill(
                    name,
                    reason=reason,
                    session_key=session_key,
                )
            elif action == "write_file":
                if file_path is None or content is None:
                    return "Error: file_path and content are required for skill_manage(write_file)."
                result = self._store.write_file(
                    name,
                    file_path,
                    content,
                    reason=reason,
                    session_key=session_key,
                )
            else:
                if file_path is None:
                    return "Error: file_path is required for skill_manage(remove_file)."
                result = self._store.remove_file(
                    name,
                    file_path,
                    reason=reason,
                    session_key=session_key,
                )
            return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        except ValueError as exc:
            return f"Error: {exc}"
