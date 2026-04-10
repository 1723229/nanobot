from __future__ import annotations

import json
from pathlib import Path

from nanobot.agent.tools.skills import SkillManageTool, SkillViewTool, SkillsListTool


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


async def test_skills_list_returns_source_mutable_and_supporting_files(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    generated_root = workspace / ".agent-state" / "skills"
    generated_root.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    _write_skill(generated_root, "demo", body="# Demo\n")
    (generated_root / "demo" / "references").mkdir()
    (generated_root / "demo" / "references" / "guide.md").write_text("guide\n", encoding="utf-8")

    tool = SkillsListTool(workspace=workspace, builtin_skills_dir=builtin)
    raw = await tool.execute()
    payload = json.loads(raw)

    assert payload == [{
        "name": "demo",
        "description": "demo description",
        "source": "generated",
        "available": True,
        "mutable": True,
        "path": str(generated_root / "demo" / "SKILL.md"),
        "supporting_files": ["references/guide.md"],
    }]


async def test_skill_view_reads_skill_md_and_supporting_files(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    ws_root = workspace / "skills"
    ws_root.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    _write_skill(ws_root, "demo", body="# Demo\nUse it.\n")
    (ws_root / "demo" / "templates").mkdir()
    (ws_root / "demo" / "templates" / "snippet.txt").write_text("snippet\n", encoding="utf-8")

    tool = SkillViewTool(workspace=workspace, builtin_skills_dir=builtin)

    skill_md = await tool.execute(name="demo")
    assert "# Demo" in skill_md
    assert "Use it." in skill_md

    snippet = await tool.execute(name="demo", file_path="templates/snippet.txt")
    assert snippet == "snippet\n"


async def test_skill_view_rejects_disallowed_supporting_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    ws_root = workspace / "skills"
    ws_root.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    _write_skill(ws_root, "demo")
    (ws_root / "demo" / "README.md").write_text("ignored\n", encoding="utf-8")

    tool = SkillViewTool(workspace=workspace, builtin_skills_dir=builtin)
    result = await tool.execute(name="demo", file_path="../README.md")
    assert "Only files under references/, templates/, scripts/, or assets/ are allowed." in result


async def test_skill_manage_create_writes_generated_skill_and_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    tool = SkillManageTool(workspace=workspace, builtin_skills_dir=builtin)
    raw = await tool.execute(
        action="create",
        name="demo",
        content="---\nname: demo\ndescription: demo generated\n---\n# Demo\nUse it.\n",
        reason="capture workflow",
        session_key="cli:direct",
    )
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert payload["action"] == "create"
    assert payload["skill_name"] == "demo"
    assert (workspace / ".agent-state" / "skills" / "demo" / "SKILL.md").exists()

    manifest = json.loads((workspace / ".agent-state" / "skills" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["skills"]["demo"]["status"] == "active"
    assert manifest["skills"]["demo"]["source"] == "generated"


async def test_skill_manage_blocks_workspace_skill_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    ws_root = workspace / "skills"
    ws_root.mkdir(parents=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir()

    _write_skill(ws_root, "demo", body="# Demo\n")

    tool = SkillManageTool(workspace=workspace, builtin_skills_dir=builtin)
    result = await tool.execute(
        action="patch",
        name="demo",
        old_text="# Demo",
        new_text="# Updated Demo",
    )

    assert "cannot be modified directly" in result
