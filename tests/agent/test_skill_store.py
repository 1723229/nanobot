from __future__ import annotations

import json
from pathlib import Path

import pytest

from nanobot.agent.skill_store import SkillStore


def _write_skill(base: Path, name: str, *, body: str = "# Skill\n") -> Path:
    skill_dir = base / name
    skill_dir.mkdir(parents=True)
    path = skill_dir / "SKILL.md"
    path.write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {name} description\n"
        "---\n"
        f"{body}",
        encoding="utf-8",
    )
    return path


def test_create_skill_writes_manifest_and_event_log(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = SkillStore(workspace)

    result = store.create_skill(
        "demo",
        "---\nname: demo\ndescription: generated demo\n---\n# Demo\nUse it.\n",
        reason="codify repeatable workflow",
        session_key="cli:direct",
    )

    assert result.action == "create"
    skill_path = workspace / ".agent-state" / "skills" / "demo" / "SKILL.md"
    assert skill_path.exists()
    content = skill_path.read_text(encoding="utf-8")
    assert "source: generated" in content

    manifest = json.loads((workspace / ".agent-state" / "skills" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["skills"]["demo"]["status"] == "active"
    assert manifest["skills"]["demo"]["source"] == "generated"

    events = (workspace / ".agent-state" / "skills" / "skill-events.jsonl").read_text(encoding="utf-8")
    assert '"action": "create"' in events
    assert '"skill_name": "demo"' in events


def test_create_allows_overlay_for_builtin_but_rejects_workspace_curated(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)
    _write_skill(builtin, "builtin-demo", body="# Builtin\n")

    store = SkillStore(workspace, builtin_skills_dir=builtin)
    store.create_skill(
        "builtin-demo",
        "---\nname: builtin-demo\ndescription: overlay\n---\n# Overlay\n",
    )
    assert (workspace / ".agent-state" / "skills" / "builtin-demo" / "SKILL.md").exists()

    ws_root = workspace / "skills"
    ws_root.mkdir(parents=True)
    _write_skill(ws_root, "curated-demo", body="# Curated\n")

    with pytest.raises(ValueError, match="workspace curated skill"):
        store.create_skill(
            "curated-demo",
            "---\nname: curated-demo\ndescription: should fail\n---\n# Fail\n",
        )


def test_patch_and_supporting_file_ops_stay_within_generated_skill(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = SkillStore(workspace)
    store.create_skill(
        "demo",
        "---\nname: demo\ndescription: demo\n---\n# Demo\nline one\n",
    )

    patched = store.patch_skill("demo", "line one", "line two")
    assert patched.action == "patch"
    assert "line two" in (workspace / ".agent-state" / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8")

    store.write_file("demo", "references/guide.md", "guide\n")
    assert (workspace / ".agent-state" / "skills" / "demo" / "references" / "guide.md").exists()

    store.remove_file("demo", "references/guide.md")
    assert not (workspace / ".agent-state" / "skills" / "demo" / "references" / "guide.md").exists()

    with pytest.raises(ValueError, match="must stay under references/"):
        store.write_file("demo", "README.md", "bad\n")


def test_patch_skill_normalizes_frontmatter_via_sanitize(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = SkillStore(workspace)
    store.create_skill(
        "normtest",
        "---\nname: normtest\ndescription: original\n---\n# Test\nold text\n",
    )
    store.patch_skill("normtest", "old text", "new text")
    content = (workspace / ".agent-state" / "skills" / "normtest" / "SKILL.md").read_text(encoding="utf-8")
    assert "source: generated" in content
    assert "new text" in content


def test_generated_skill_validation_rejects_nested_frontmatter_and_always_true(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    store = SkillStore(workspace)

    with pytest.raises(ValueError, match="must stay flat"):
        store.create_skill(
            "bad-frontmatter",
            "---\nname: bad-frontmatter\ndescription: bad\nmetadata:\n  nanobot: {}\n---\n# Bad\n",
        )

    with pytest.raises(ValueError, match="must not set always: true"):
        store.create_skill(
            "bad-always",
            "---\nname: bad-always\ndescription: bad\nalways: true\n---\n# Bad\n",
        )


def test_edit_skill_replaces_content_and_updates_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = SkillStore(workspace)
    store.create_skill(
        "demo",
        "---\nname: demo\ndescription: original\n---\n# Original\nStep one.\n",
    )

    result = store.edit_skill(
        "demo",
        "---\nname: demo\ndescription: revised\n---\n# Revised\nStep two.\n",
        reason="full rewrite",
        session_key="cli:direct",
    )

    assert result.action == "edit"
    content = (workspace / ".agent-state" / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8")
    assert "description: revised" in content
    assert "# Revised" in content
    assert "Step one" not in content

    manifest = json.loads((workspace / ".agent-state" / "skills" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["skills"]["demo"]["status"] == "active"

    events = (workspace / ".agent-state" / "skills" / "skill-events.jsonl").read_text(encoding="utf-8")
    assert '"action": "edit"' in events


def test_edit_skill_rejects_non_generated(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True)
    _write_skill(builtin, "bi-skill", body="# Builtin\n")

    store = SkillStore(workspace, builtin_skills_dir=builtin)
    with pytest.raises(ValueError, match="cannot be modified directly"):
        store.edit_skill(
            "bi-skill",
            "---\nname: bi-skill\ndescription: hacked\n---\n# Hacked\n",
        )


def test_delete_skill_removes_directory_and_marks_manifest_deleted(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = SkillStore(workspace, allow_delete=True)
    store.create_skill(
        "ephemeral",
        "---\nname: ephemeral\ndescription: temp\n---\n# Temp\nGone soon.\n",
    )
    skill_dir = workspace / ".agent-state" / "skills" / "ephemeral"
    assert skill_dir.exists()

    result = store.delete_skill("ephemeral", reason="no longer needed")

    assert result.action == "delete"
    assert not skill_dir.exists()

    manifest = json.loads((workspace / ".agent-state" / "skills" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["skills"]["ephemeral"]["status"] == "deleted"

    events = (workspace / ".agent-state" / "skills" / "skill-events.jsonl").read_text(encoding="utf-8")
    assert '"action": "delete"' in events


def test_delete_skill_blocked_when_allow_delete_false(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = SkillStore(workspace, allow_delete=False)
    store.create_skill(
        "protected",
        "---\nname: protected\ndescription: keep\n---\n# Keep\n",
    )

    with pytest.raises(ValueError, match="disabled by configuration"):
        store.delete_skill("protected")

    assert (workspace / ".agent-state" / "skills" / "protected" / "SKILL.md").exists()


def test_create_skill_blocked_when_allow_create_false(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = SkillStore(workspace, allow_create=False)

    with pytest.raises(ValueError, match="disabled by configuration"):
        store.create_skill(
            "blocked",
            "---\nname: blocked\ndescription: nope\n---\n# Nope\n",
        )


def test_patch_skill_blocked_when_allow_patch_false(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store_create = SkillStore(workspace, allow_create=True, allow_patch=True)
    store_create.create_skill(
        "frozen",
        "---\nname: frozen\ndescription: frozen\n---\n# Frozen\noriginal\n",
    )

    store_locked = SkillStore(workspace, allow_patch=False)
    with pytest.raises(ValueError, match="disabled by configuration"):
        store_locked.patch_skill("frozen", "original", "changed")


def test_create_skill_rejects_invalid_names(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = SkillStore(workspace)

    for bad_name in ("UPPER", "has spaces", "../escape", "a" * 65, "-leading-hyphen"):
        with pytest.raises(ValueError, match="Invalid skill name"):
            store.create_skill(
                bad_name,
                f"---\nname: {bad_name}\ndescription: bad\n---\n# Bad\n",
            )


def test_create_skill_rejects_duplicate_generated(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    store = SkillStore(workspace)
    store.create_skill(
        "unique",
        "---\nname: unique\ndescription: first\n---\n# First\n",
    )

    with pytest.raises(ValueError, match="already exists"):
        store.create_skill(
            "unique",
            "---\nname: unique\ndescription: second\n---\n# Second\n",
        )
