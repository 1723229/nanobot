"""Controlled write path for generated skills."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from nanobot.agent.skills import DEFAULT_GENERATED_SKILLS_DIR, SkillsLoader
from nanobot.agent.tools.filesystem import _find_match

_FRONTMATTER_RE = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?", re.DOTALL)
_SKILL_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_ALLOWED_SUPPORT_DIRS = {"references", "templates", "scripts", "assets"}


@dataclass
class SkillMutationResult:
    """Structured result for one skill mutation."""

    action: str
    skill_name: str
    message: str
    path: str | None = None
    file_path: str | None = None
    source: str = "generated"
    mutable: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": True,
            "action": self.action,
            "skill_name": self.skill_name,
            "source": self.source,
            "mutable": self.mutable,
            "message": self.message,
        }
        if self.path is not None:
            payload["path"] = self.path
        if self.file_path is not None:
            payload["file_path"] = self.file_path
        return payload


class SkillStore:
    """Persist generated skills under ``<workspace>/.agent-state/skills`` only."""

    def __init__(
        self,
        workspace: Path,
        builtin_skills_dir: Path | None = None,
        *,
        generated_skills_dir: Path | None = None,
        allow_create: bool = True,
        allow_patch: bool = True,
        allow_delete: bool = False,
    ):
        self.workspace = workspace
        self.root = workspace / (generated_skills_dir or DEFAULT_GENERATED_SKILLS_DIR)
        self.manifest_path = self.root / "manifest.json"
        self.events_path = self.root / "skill-events.jsonl"
        self._loader = SkillsLoader(
            workspace,
            builtin_skills_dir=builtin_skills_dir,
            generated_skills_dir=generated_skills_dir,
        )
        self._allow_create = allow_create
        self._allow_patch = allow_patch
        self._allow_delete = allow_delete

    def create_skill(
        self,
        name: str,
        content: str,
        *,
        reason: str | None = None,
        session_key: str | None = None,
        actor: str = "agent",
        origin_skill: str | None = None,
        origin_source: str | None = None,
    ) -> SkillMutationResult:
        self._assert_create_allowed()
        self._validate_skill_name(name)
        existing = self._loader.get_skill_entry(name)
        if existing and existing["source"] == "workspace":
            raise ValueError(
                f"Cannot create generated skill '{name}' because a workspace curated skill with the same name already exists."
            )
        if existing and existing["source"] == "generated":
            raise ValueError(f"Generated skill '{name}' already exists. Use edit or patch instead.")

        skill_dir = self._skill_dir(name)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_doc = self._sanitize_skill_document(name, content)
        self._write_text_atomic(skill_dir / "SKILL.md", skill_doc)

        manifest = self._load_manifest()
        prior = manifest["skills"].get(name, {})
        manifest["skills"][name] = self._build_manifest_entry(
            name=name,
            existing=prior,
            actor=actor,
            origin_skill=origin_skill if origin_skill is not None else (existing or {}).get("name"),
            origin_source=origin_source if origin_source is not None else (existing or {}).get("source"),
            status="active",
        )
        self._write_manifest(manifest)
        self._append_event(
            action="create",
            skill_name=name,
            session_key=session_key,
            reason=reason,
            actor=actor,
            path=str(skill_dir / "SKILL.md"),
        )
        return SkillMutationResult(
            action="create",
            skill_name=name,
            message=f"Created generated skill '{name}'.",
            path=str(skill_dir / "SKILL.md"),
        )

    def edit_skill(
        self,
        name: str,
        content: str,
        *,
        reason: str | None = None,
        session_key: str | None = None,
        actor: str = "agent",
    ) -> SkillMutationResult:
        self._assert_patch_allowed()
        entry = self._require_generated(name)
        skill_doc = self._sanitize_skill_document(name, content)
        target = Path(entry["path"])
        self._write_text_atomic(target, skill_doc)

        manifest = self._load_manifest()
        prior = manifest["skills"].get(name, {})
        manifest["skills"][name] = self._build_manifest_entry(
            name=name,
            existing=prior,
            actor=actor,
            origin_skill=prior.get("origin_skill"),
            origin_source=prior.get("origin_source"),
            status="active",
        )
        self._write_manifest(manifest)
        self._append_event(
            action="edit",
            skill_name=name,
            session_key=session_key,
            reason=reason,
            actor=actor,
            path=str(target),
        )
        return SkillMutationResult(
            action="edit",
            skill_name=name,
            message=f"Updated generated skill '{name}'.",
            path=str(target),
        )

    def patch_skill(
        self,
        name: str,
        old_text: str,
        new_text: str,
        *,
        file_path: str | None = None,
        replace_all: bool = False,
        reason: str | None = None,
        session_key: str | None = None,
        actor: str = "agent",
    ) -> SkillMutationResult:
        self._assert_patch_allowed()
        entry = self._require_generated(name)
        target = self._resolve_mutation_target(Path(entry["path"]).parent, file_path)
        raw = target.read_bytes()
        try:
            text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Cannot patch binary file '{target.name}': {exc}") from exc

        match, count = _find_match(text, old_text.replace("\r\n", "\n").replace("\r", "\n"))
        if match is None:
            raise ValueError(f"old_text not found in '{self._display_file_path(entry, file_path)}'.")
        if count > 1 and not replace_all:
            raise ValueError(
                f"old_text appears {count} times in '{self._display_file_path(entry, file_path)}'. "
                "Provide more context or set replace_all=true."
            )

        replacement = new_text.replace("\r\n", "\n").replace("\r", "\n")
        updated = text.replace(match, replacement) if replace_all else text.replace(match, replacement, 1)
        if target.name == "SKILL.md":
            updated = self._sanitize_skill_document(name, updated)
        self._write_text_atomic(target, updated)

        manifest = self._load_manifest()
        prior = manifest["skills"].get(name, {})
        manifest["skills"][name] = self._build_manifest_entry(
            name=name,
            existing=prior,
            actor=actor,
            origin_skill=prior.get("origin_skill"),
            origin_source=prior.get("origin_source"),
            status="active",
        )
        self._write_manifest(manifest)
        self._append_event(
            action="patch",
            skill_name=name,
            session_key=session_key,
            reason=reason,
            actor=actor,
            path=str(target),
            file_path=self._display_file_path(entry, file_path),
        )
        return SkillMutationResult(
            action="patch",
            skill_name=name,
            message=f"Patched generated skill '{name}'.",
            path=str(target),
            file_path=self._display_file_path(entry, file_path),
        )

    def delete_skill(
        self,
        name: str,
        *,
        reason: str | None = None,
        session_key: str | None = None,
        actor: str = "agent",
    ) -> SkillMutationResult:
        self._assert_delete_allowed()
        entry = self._require_generated(name)
        skill_dir = Path(entry["path"]).parent
        shutil.rmtree(skill_dir)

        manifest = self._load_manifest()
        prior = manifest["skills"].get(name, {})
        manifest["skills"][name] = {
            **prior,
            "name": name,
            "root_dir": str(skill_dir.relative_to(self.workspace)).replace("\\", "/"),
            "source": "generated",
            "status": "deleted",
            "deleted_at": self._now(),
            "updated_at": self._now(),
            "updated_by": actor,
        }
        self._write_manifest(manifest)
        self._append_event(
            action="delete",
            skill_name=name,
            session_key=session_key,
            reason=reason,
            actor=actor,
            path=str(skill_dir),
        )
        return SkillMutationResult(
            action="delete",
            skill_name=name,
            message=f"Deleted generated skill '{name}'.",
            path=str(skill_dir),
        )

    def write_file(
        self,
        name: str,
        file_path: str,
        content: str,
        *,
        reason: str | None = None,
        session_key: str | None = None,
        actor: str = "agent",
    ) -> SkillMutationResult:
        self._assert_patch_allowed()
        entry = self._require_generated(name)
        target = self._resolve_mutation_target(Path(entry["path"]).parent, file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._write_text_atomic(target, content.replace("\r\n", "\n").replace("\r", "\n"))

        manifest = self._load_manifest()
        prior = manifest["skills"].get(name, {})
        manifest["skills"][name] = self._build_manifest_entry(
            name=name,
            existing=prior,
            actor=actor,
            origin_skill=prior.get("origin_skill"),
            origin_source=prior.get("origin_source"),
            status="active",
        )
        self._write_manifest(manifest)
        self._append_event(
            action="write_file",
            skill_name=name,
            session_key=session_key,
            reason=reason,
            actor=actor,
            path=str(target),
            file_path=file_path,
        )
        return SkillMutationResult(
            action="write_file",
            skill_name=name,
            message=f"Wrote supporting file '{file_path}' for generated skill '{name}'.",
            path=str(target),
            file_path=file_path,
        )

    def remove_file(
        self,
        name: str,
        file_path: str,
        *,
        reason: str | None = None,
        session_key: str | None = None,
        actor: str = "agent",
    ) -> SkillMutationResult:
        self._assert_patch_allowed()
        entry = self._require_generated(name)
        target = self._resolve_mutation_target(Path(entry["path"]).parent, file_path)
        if not target.exists():
            raise ValueError(f"Supporting file '{file_path}' does not exist for generated skill '{name}'.")
        target.unlink()

        manifest = self._load_manifest()
        prior = manifest["skills"].get(name, {})
        manifest["skills"][name] = self._build_manifest_entry(
            name=name,
            existing=prior,
            actor=actor,
            origin_skill=prior.get("origin_skill"),
            origin_source=prior.get("origin_source"),
            status="active",
        )
        self._write_manifest(manifest)
        self._append_event(
            action="remove_file",
            skill_name=name,
            session_key=session_key,
            reason=reason,
            actor=actor,
            path=str(target),
            file_path=file_path,
        )
        return SkillMutationResult(
            action="remove_file",
            skill_name=name,
            message=f"Removed supporting file '{file_path}' from generated skill '{name}'.",
            path=str(target),
            file_path=file_path,
        )

    def _require_generated(self, name: str) -> dict[str, str]:
        self._validate_skill_name(name)
        entry = self._loader.get_skill_entry(name)
        if not entry:
            raise ValueError(f"Skill '{name}' does not exist.")
        if entry["source"] != "generated":
            raise ValueError(
                f"Skill '{name}' is {entry['source']} and cannot be modified directly. "
                "Only generated skills under .agent-state/skills are mutable."
            )
        return entry

    def _assert_create_allowed(self) -> None:
        if not self._allow_create:
            raise ValueError("Creating generated skills is disabled by configuration.")

    def _assert_patch_allowed(self) -> None:
        if not self._allow_patch:
            raise ValueError("Updating generated skills is disabled by configuration.")

    def _assert_delete_allowed(self) -> None:
        if not self._allow_delete:
            raise ValueError("Deleting generated skills is disabled by configuration.")

    @staticmethod
    def _validate_skill_name(name: str) -> None:
        if not _SKILL_NAME_RE.fullmatch(name):
            raise ValueError(
                "Invalid skill name. Use lowercase letters, digits, and hyphens only, up to 64 characters."
            )

    def _skill_dir(self, name: str) -> Path:
        self._validate_skill_name(name)
        return self.root / name

    def _resolve_mutation_target(self, skill_dir: Path, file_path: str | None) -> Path:
        if not file_path:
            return skill_dir / "SKILL.md"
        rel = Path(file_path)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Supporting file path must be relative and must not contain '..'.")
        if not rel.parts or rel.parts[0] not in _ALLOWED_SUPPORT_DIRS:
            raise ValueError(
                "Supporting file path must stay under references/, templates/, scripts/, or assets/."
            )
        target = (skill_dir / rel).resolve()
        try:
            target.relative_to(skill_dir.resolve())
        except ValueError as exc:
            raise ValueError("Supporting file path escapes the generated skill directory.") from exc
        return target

    def _sanitize_skill_document(self, name: str, content: str) -> str:
        normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
        match = _FRONTMATTER_RE.match(normalized)
        if not match:
            raise ValueError("SKILL.md must start with flat YAML frontmatter delimited by --- lines.")

        raw_frontmatter = match.group(1)
        meta = self._parse_flat_frontmatter(raw_frontmatter)
        description = meta.get("description", "").strip()
        if not description:
            raise ValueError("Skill frontmatter must include a non-empty description field.")
        if meta.get("always", "").strip().lower() == "true":
            raise ValueError("Generated skills must not set always: true.")
        metadata_raw = meta.get("metadata")
        if metadata_raw:
            try:
                payload = json.loads(metadata_raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"metadata must be a JSON object string: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError("metadata must decode to a JSON object.")

        body = normalized[match.end():].strip()
        if not body:
            raise ValueError("SKILL.md body must not be empty.")

        extras = {
            key: value
            for key, value in meta.items()
            if key not in {"name", "description", "source", "always"}
        }
        lines = ["---", f"name: {name}", f"description: {description}", "source: generated"]
        for key, value in extras.items():
            lines.append(f"{key}: {value}")
        lines.extend(["---", "", body])
        return "\n".join(lines) + "\n"

    @staticmethod
    def _parse_flat_frontmatter(raw: str) -> dict[str, str]:
        metadata: dict[str, str] = {}
        for line in raw.splitlines():
            if not line.strip():
                continue
            if line.startswith((" ", "\t", "- ")):
                raise ValueError(
                    "Generated skill frontmatter must stay flat. Nested YAML should move into manifest.json metadata."
                )
            if ":" not in line:
                raise ValueError(f"Invalid frontmatter line: {line}")
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip("\"'")
        return metadata

    def _load_manifest(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists():
            return {"skills": {}}
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"skills": {}}
        if not isinstance(payload, dict):
            return {"skills": {}}
        skills = payload.get("skills")
        if not isinstance(skills, dict):
            payload["skills"] = {}
        return payload

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        self._write_text_atomic(
            self.manifest_path,
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )

    def _build_manifest_entry(
        self,
        *,
        name: str,
        existing: dict[str, Any],
        actor: str,
        origin_skill: str | None,
        origin_source: str | None,
        status: str,
    ) -> dict[str, Any]:
        skill_dir = self._skill_dir(name)
        now = self._now()
        created_at = existing.get("created_at", now)
        created_by = existing.get("created_by", actor)
        return {
            "name": name,
            "root_dir": str(skill_dir.relative_to(self.workspace)).replace("\\", "/"),
            "source": "generated",
            "origin_skill": origin_skill,
            "origin_source": origin_source,
            "created_by": created_by,
            "created_at": created_at,
            "updated_by": actor,
            "updated_at": now,
            "status": status,
            "current_hash": self._hash_skill_dir(skill_dir),
            "last_used_at": existing.get("last_used_at"),
            "last_reviewed_at": existing.get("last_reviewed_at"),
            "review_count": existing.get("review_count", 0),
        }

    def _append_event(
        self,
        *,
        action: str,
        skill_name: str,
        actor: str,
        session_key: str | None,
        reason: str | None,
        path: str | None,
        file_path: str | None = None,
    ) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": self._now(),
            "action": action,
            "skill_name": skill_name,
            "source": "generated",
            "actor": actor,
            "session_key": session_key,
            "reason": reason,
            "path": path,
            "file_path": file_path,
            "result": "ok",
        }
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._loader.invalidate_summary_cache()

    def _hash_skill_dir(self, skill_dir: Path) -> str:
        digest = hashlib.sha256()
        if not skill_dir.exists():
            return digest.hexdigest()
        for path in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(skill_dir)).replace("\\", "/").encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def _write_text_atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(path)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    @staticmethod
    def _display_file_path(entry: dict[str, str], file_path: str | None) -> str:
        return file_path or Path(entry["path"]).name

    @staticmethod
    def _now() -> str:
        from datetime import datetime

        return datetime.now().astimezone().isoformat()
