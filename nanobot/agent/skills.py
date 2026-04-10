"""Skills loader for agent capabilities."""

import json
import os
import re
import shutil
from pathlib import Path

from loguru import logger

# Default builtin skills directory (relative to this file)
BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"
DEFAULT_GENERATED_SKILLS_DIR = Path(".agent-state") / "skills"

# Opening ---, YAML body (group 1), closing --- on its own line; supports CRLF.
_STRIP_SKILL_FRONTMATTER = re.compile(
    r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?",
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# Prompt injection scanning (borrowed from Hermes prompt_builder.py)
# ---------------------------------------------------------------------------

_CONTEXT_THREAT_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(previous|all|above|prior)\s+instructions", "prompt_injection"),
    (r"do\s+not\s+tell\s+the\s+user", "deception_hide"),
    (r"system\s+prompt\s+override", "sys_prompt_override"),
    (r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)", "disregard_rules"),
    (r"act\s+as\s+(if|though)\s+you\s+(have\s+no|don't\s+have)\s+(restrictions|limits|rules)", "bypass_restrictions"),
    (r"<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->", "html_comment_injection"),
    (r'<\s*div\s+style\s*=\s*["\'].*display\s*:\s*none', "hidden_div"),
    (r"translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)", "translate_execute"),
    (r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)", "exfil_curl"),
    (r"cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass)", "read_secrets"),
]

_CONTEXT_INVISIBLE_CHARS = frozenset(
    "\u200b\u200c\u200d\u2060\ufeff\u202a\u202b\u202c\u202d\u202e"
)


def scan_skill_content(content: str, skill_name: str) -> str:
    """Return *content* unchanged or a ``[BLOCKED]`` placeholder if injection is detected."""
    findings: list[str] = []
    for char in _CONTEXT_INVISIBLE_CHARS:
        if char in content:
            findings.append(f"invisible unicode U+{ord(char):04X}")
            break
    for pattern, pid in _CONTEXT_THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            findings.append(pid)
    if findings:
        logger.warning("Skill {} blocked: {}", skill_name, ", ".join(findings))
        return f"[BLOCKED: skill '{skill_name}' contained potential prompt injection ({', '.join(findings)}). Content not loaded.]"
    return content


def _escape_xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class SkillsLoader:
    """
    Loader for agent skills.

    Skills are markdown files (SKILL.md) that teach the agent how to use
    specific tools or perform certain tasks.
    """

    def __init__(
        self,
        workspace: Path,
        builtin_skills_dir: Path | None = None,
        generated_skills_dir: Path | None = None,
    ):
        self.workspace = workspace
        self.workspace_skills = workspace / "skills"
        self.generated_skills = workspace / (generated_skills_dir or DEFAULT_GENERATED_SKILLS_DIR)
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR
        self._summary_cache: str | None = None
        self._summary_cache_fingerprint: str | None = None

    def _skill_entries_from_dir(self, base: Path, source: str, *, skip_names: set[str] | None = None) -> list[dict[str, str]]:
        if not base.exists():
            return []
        entries: list[dict[str, str]] = []
        for skill_dir in sorted(base.iterdir(), key=lambda path: path.name):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            name = skill_dir.name
            if skip_names is not None and name in skip_names:
                continue
            entries.append({"name": name, "path": str(skill_file), "source": source})
        return entries

    def _skill_sources(self) -> list[tuple[str, Path]]:
        return [
            ("workspace", self.workspace_skills),
            ("generated", self.generated_skills),
            ("builtin", self.builtin_skills),
        ]

    def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
        """
        List all available skills.

        Args:
            filter_unavailable: If True, filter out skills with unmet requirements.

        Returns:
            List of skill info dicts with 'name', 'path', 'source'.
        """
        skills: list[dict[str, str]] = []
        seen_names: set[str] = set()
        for source, root in self._skill_sources():
            if not root:
                continue
            source_entries = self._skill_entries_from_dir(root, source, skip_names=seen_names)
            seen_names.update(entry["name"] for entry in source_entries)
            skills.extend(source_entries)

        if filter_unavailable:
            return [skill for skill in skills if self._check_requirements(self._get_skill_meta(skill["name"]))]
        return skills

    def _read_skill_file(self, skill_file: Path) -> str | None:
        """Read a skill file as UTF-8, skipping invalid files."""
        try:
            return skill_file.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            logger.warning(f"Skipping skill {skill_file}: invalid UTF-8 ({e})")
            return None

    def _skill_is_readable(self, name: str) -> bool:
        """Return whether the skill file can be decoded as UTF-8."""
        return self.load_skill(name) is not None

    def load_skill(self, name: str) -> str | None:
        """
        Load a skill by name.

        Args:
            name: Skill name (directory name).

        Returns:
            Skill content or None if not found.
        """
        for _source, root in self._skill_sources():
            path = root / name / "SKILL.md"
            if path.exists():
                return path.read_text(encoding="utf-8")
        return None

    def get_skill_entry(self, name: str) -> dict[str, str] | None:
        for entry in self.list_skills(filter_unavailable=False):
            if entry["name"] == name:
                return entry
        return None

    def is_mutable(self, name: str) -> bool:
        entry = self.get_skill_entry(name)
        return bool(entry and entry["source"] == "generated")

    def list_supporting_files(self, name: str) -> list[str]:
        entry = self.get_skill_entry(name)
        if not entry:
            return []
        skill_dir = Path(entry["path"]).parent
        allowed_dirs = ("references", "templates", "scripts", "assets")
        files: list[str] = []
        for dirname in allowed_dirs:
            base = skill_dir / dirname
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    files.append(str(path.relative_to(skill_dir)).replace("\\", "/"))
        return files

    def load_skill_file(self, name: str, relative_path: str | None = None) -> str | bytes | None:
        entry = self.get_skill_entry(name)
        if not entry:
            return None
        skill_dir = Path(entry["path"]).parent
        if not relative_path:
            return Path(entry["path"]).read_text(encoding="utf-8")

        rel = Path(relative_path)
        if rel.is_absolute():
            return None
        if ".." in rel.parts:
            return None
        if not rel.parts or rel.parts[0] not in {"references", "templates", "scripts", "assets"}:
            return None

        target = (skill_dir / rel).resolve()
        try:
            target.relative_to(skill_dir.resolve())
        except ValueError:
            return None
        if not target.exists() or not target.is_file():
            return None
        raw = target.read_bytes()
        try:
            return raw.decode("utf-8").replace("\r\n", "\n")
        except UnicodeDecodeError:
            return raw

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """
        Load specific skills for inclusion in agent context.

        Args:
            skill_names: List of skill names to load.

        Returns:
            Formatted skills content.
        """
        parts: list[str] = []
        for name in skill_names:
            markdown = self.load_skill(name)
            if not markdown:
                continue
            safe = scan_skill_content(markdown, name)
            parts.append(f"### Skill: {name}\n\n{self._strip_frontmatter(safe)}")
        return "\n\n---\n\n".join(parts)

    def invalidate_summary_cache(self) -> None:
        """Force the next ``build_skills_summary`` to rescan the disk."""
        self._summary_cache = None
        self._summary_cache_fingerprint = None

    def _skills_fingerprint(self) -> str:
        """Cheap fingerprint: sorted (name, mtime_ns) of every SKILL.md."""
        parts: list[str] = []
        for _source, root in self._skill_sources():
            if not root or not root.exists():
                continue
            for skill_dir in sorted(root.iterdir(), key=lambda p: p.name):
                skill_file = skill_dir / "SKILL.md" if skill_dir.is_dir() else None
                if skill_file and skill_file.exists():
                    try:
                        parts.append(f"{skill_file}:{skill_file.stat().st_mtime_ns}")
                    except OSError:
                        parts.append(f"{skill_file}:?")
        return "|".join(parts)

    def build_skills_summary(self) -> str:
        """
        Build a summary of all skills (name, description, path, availability).

        Uses an mtime-based cache to avoid repeated disk scans when nothing changed.

        Returns:
            XML-formatted skills summary.
        """
        fp = self._skills_fingerprint()
        if self._summary_cache is not None and fp == self._summary_cache_fingerprint:
            return self._summary_cache

        all_skills = self.list_skills(filter_unavailable=False)
        if not all_skills:
            self._summary_cache = ""
            self._summary_cache_fingerprint = fp
            return ""

        lines: list[str] = ["<skills>"]
        for entry in all_skills:
            skill_name = entry["name"]
            meta = self._get_skill_meta(skill_name)
            available = self._check_requirements(meta)
            mutable = self.is_mutable(skill_name)
            supporting_files = self.list_supporting_files(skill_name)
            lines.extend(
                [
                    f'  <skill available="{str(available).lower()}" mutable="{str(mutable).lower()}">',
                    f"    <name>{_escape_xml(skill_name)}</name>",
                    f"    <description>{_escape_xml(self._get_skill_description(skill_name))}</description>",
                    f"    <source>{_escape_xml(entry['source'])}</source>",
                    f"    <location>{entry['path']}</location>",
                ]
            )
            if supporting_files:
                lines.append("    <supporting_files>")
                for path in supporting_files:
                    lines.append(f"      <file>{_escape_xml(path)}</file>")
                lines.append("    </supporting_files>")
            if not available:
                missing = self._get_missing_requirements(meta)
                if missing:
                    lines.append(f"    <requires>{_escape_xml(missing)}</requires>")
            lines.append("  </skill>")
        lines.append("</skills>")
        result = "\n".join(lines)
        self._summary_cache = result
        self._summary_cache_fingerprint = fp
        return result

    def _get_missing_requirements(self, skill_meta: dict) -> str:
        """Get a description of missing requirements."""
        requires = skill_meta.get("requires", {})
        required_bins = requires.get("bins", [])
        required_env_vars = requires.get("env", [])
        return ", ".join(
            [f"CLI: {command_name}" for command_name in required_bins if not shutil.which(command_name)]
            + [f"ENV: {env_name}" for env_name in required_env_vars if not os.environ.get(env_name)]
        )

    def _get_skill_description(self, name: str) -> str:
        """Get the description of a skill from its frontmatter."""
        meta = self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name  # Fallback to skill name

    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if not content.startswith("---"):
            return content
        match = _STRIP_SKILL_FRONTMATTER.match(content)
        if match:
            return content[match.end():].strip()
        return content

    def _parse_nanobot_metadata(self, raw: str) -> dict:
        """Parse skill metadata JSON from frontmatter (supports nanobot and openclaw keys)."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(data, dict):
            return {}
        payload = data.get("nanobot", data.get("openclaw", {}))
        return payload if isinstance(payload, dict) else {}

    def _check_requirements(self, skill_meta: dict) -> bool:
        """Check if skill requirements are met (bins, env vars)."""
        requires = skill_meta.get("requires", {})
        required_bins = requires.get("bins", [])
        required_env_vars = requires.get("env", [])
        return all(shutil.which(cmd) for cmd in required_bins) and all(
            os.environ.get(var) for var in required_env_vars
        )

    def _get_skill_meta(self, name: str) -> dict:
        """Get nanobot metadata for a skill (cached in frontmatter)."""
        meta = self.get_skill_metadata(name) or {}
        return self._parse_nanobot_metadata(meta.get("metadata", ""))

    def get_always_skills(self) -> list[str]:
        """Get skills marked as always=true that meet requirements."""
        return [
            entry["name"]
            for entry in self.list_skills(filter_unavailable=True)
            if entry["source"] != "generated"
            if (meta := self.get_skill_metadata(entry["name"]) or {})
            and (
                self._parse_nanobot_metadata(meta.get("metadata", "")).get("always")
                or meta.get("always")
            )
        ]

    def get_skill_metadata(self, name: str) -> dict | None:
        """
        Get metadata from a skill's frontmatter.

        Args:
            name: Skill name.

        Returns:
            Metadata dict or None.
        """
        content = self.load_skill(name)
        if not content or not content.startswith("---"):
            return None
        match = _STRIP_SKILL_FRONTMATTER.match(content)
        if not match:
            return None
        metadata: dict[str, str] = {}
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip('"\'')
        return metadata
