from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.skill_review import SkillReviewService
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import SkillsConfig
from nanobot.providers.base import LLMResponse


def _review_messages() -> list[dict]:
    return [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "list_dir", "arguments": "{\"path\":\".\"}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "name": "list_dir", "content": "skills\nsrc\n"},
        {"role": "assistant", "content": "done"},
    ]


@pytest.mark.asyncio
async def test_skill_review_creates_generated_skill(tmp_path: Path) -> None:
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(
            content=(
                '{"action":"create","skill_name":"demo-skill","reason":"reusable workflow",'
                '"content":"---\\nname: demo-skill\\ndescription: demo skill\\n---\\n# Demo\\nUse it.\\n",'
                '"supporting_files":{"references/guide.md":"guide\\n"}}'
            )
        )
    )

    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_mode="auto_create", review_min_tool_calls=1),
    )

    result = await review.review_turn(
        session_key="cli:direct",
        recent_messages=_review_messages(),
        final_content="done",
        stop_reason="completed",
        user_message="总结这个流程",
    )

    assert result is not None
    assert result.action == "create"
    assert (tmp_path / ".agent-state" / "skills" / "demo-skill" / "SKILL.md").exists()
    assert (tmp_path / ".agent-state" / "skills" / "demo-skill" / "references" / "guide.md").exists()


@pytest.mark.asyncio
async def test_skill_review_updates_existing_generated_skill(tmp_path: Path) -> None:
    skill_dir = tmp_path / ".agent-state" / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: old\nsource: generated\n---\n# Old\n",
        encoding="utf-8",
    )

    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(
            content=(
                '{"action":"update","skill_name":"demo-skill","reason":"improve steps",'
                '"content":"---\\nname: demo-skill\\ndescription: new\\n---\\n# New\\nUse it better.\\n",'
                '"supporting_files":{}}'
            )
        )
    )

    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_mode="auto_update", review_min_tool_calls=1),
    )

    result = await review.review_turn(
        session_key="cli:direct",
        recent_messages=_review_messages(),
        final_content="done",
        stop_reason="completed",
        user_message="修正已有 skill",
    )

    assert result is not None
    content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "description: new" in content
    assert "# New" in content


@pytest.mark.asyncio
async def test_skill_review_clones_workspace_skill_to_generated_name(tmp_path: Path) -> None:
    ws_skill = tmp_path / "skills" / "demo-skill"
    ws_skill.mkdir(parents=True)
    (ws_skill / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: curated\n---\n# Curated\n",
        encoding="utf-8",
    )

    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(
            content=(
                '{"action":"update","skill_name":"demo-skill","reason":"runtime specialization",'
                '"content":"---\\nname: demo-skill\\ndescription: runtime\\n---\\n# Runtime\\n",'
                '"supporting_files":{}}'
            )
        )
    )

    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_mode="auto_update", review_min_tool_calls=1),
    )

    result = await review.review_turn(
        session_key="cli:direct",
        recent_messages=_review_messages(),
        final_content="done",
        stop_reason="completed",
        user_message="优化 curated skill",
    )

    assert result is not None
    assert (tmp_path / ".agent-state" / "skills" / "demo-skill-generated" / "SKILL.md").exists()
    assert "# Curated" in (ws_skill / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_skill_review_auto_update_does_not_create_brand_new_skill(tmp_path: Path) -> None:
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(
            content=(
                '{"action":"create","skill_name":"brand-new","reason":"new",'
                '"content":"---\\nname: brand-new\\ndescription: new\\n---\\n# New\\n",'
                '"supporting_files":{}}'
            )
        )
    )

    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_mode="auto_update", review_min_tool_calls=1),
    )

    result = await review.review_turn(
        session_key="cli:direct",
        recent_messages=_review_messages(),
        final_content="done",
        stop_reason="completed",
        user_message="不要创建新 skill",
    )

    assert result is None
    assert not (tmp_path / ".agent-state" / "skills" / "brand-new").exists()


def test_should_review_returns_false_when_disabled(tmp_path: Path) -> None:
    provider = MagicMock()
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(enabled=False, review_enabled=True, review_min_tool_calls=1),
    )
    assert review.should_review(_review_messages()) is False


def test_should_review_returns_false_when_review_disabled(tmp_path: Path) -> None:
    provider = MagicMock()
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(enabled=True, review_enabled=False, review_min_tool_calls=1),
    )
    assert review.should_review(_review_messages()) is False


def test_should_review_returns_false_when_mode_off(tmp_path: Path) -> None:
    provider = MagicMock()
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_mode="off", review_min_tool_calls=1),
    )
    assert review.should_review(_review_messages()) is False


def test_should_review_true_when_tool_call_threshold_met(tmp_path: Path) -> None:
    provider = MagicMock()
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_min_tool_calls=1, review_trigger_iterations=100),
    )
    assert review.should_review(_review_messages()) is True


def test_should_review_true_when_iteration_threshold_met(tmp_path: Path) -> None:
    provider = MagicMock()
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_min_tool_calls=100, review_trigger_iterations=1),
    )
    assert review.should_review(_review_messages()) is True


def test_should_review_true_when_skill_view_used(tmp_path: Path) -> None:
    provider = MagicMock()
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_min_tool_calls=100, review_trigger_iterations=100),
    )
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_sv",
                    "type": "function",
                    "function": {"name": "skill_view", "arguments": '{"name":"demo"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_sv", "name": "skill_view", "content": "# Demo"},
        {"role": "assistant", "content": "done"},
    ]
    assert review.should_review(messages) is True


def test_should_review_false_when_no_threshold_met(tmp_path: Path) -> None:
    provider = MagicMock()
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_min_tool_calls=100, review_trigger_iterations=100),
    )
    assert review.should_review([{"role": "assistant", "content": "hi"}]) is False


def test_should_review_false_when_agent_already_managed_skills(tmp_path: Path) -> None:
    provider = MagicMock()
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_min_tool_calls=1, review_trigger_iterations=1),
    )
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_sm",
                    "type": "function",
                    "function": {"name": "skill_manage", "arguments": '{"action":"create","name":"demo"}'},
                },
            ],
        },
        {"role": "tool", "tool_call_id": "call_sm", "name": "skill_manage", "content": '{"ok":true}'},
        {"role": "assistant", "content": "done"},
    ]
    assert review.should_review(messages) is False


@pytest.mark.asyncio
async def test_review_turn_returns_none_on_error_stop_reason(tmp_path: Path) -> None:
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="should not be called"))
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_mode="auto_create", review_min_tool_calls=1),
    )
    result = await review.review_turn(
        session_key="test",
        recent_messages=_review_messages(),
        final_content="error",
        stop_reason="error",
        user_message="test",
    )
    assert result is None
    provider.chat_with_retry.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_turn_returns_none_on_malformed_json(tmp_path: Path) -> None:
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(content="This is not JSON at all, just rambling text.")
    )
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_mode="auto_create", review_min_tool_calls=1),
    )
    result = await review.review_turn(
        session_key="test",
        recent_messages=_review_messages(),
        final_content="done",
        stop_reason="completed",
        user_message="test",
    )
    assert result is None


@pytest.mark.asyncio
async def test_review_turn_suggest_mode_does_not_write(tmp_path: Path) -> None:
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(
            content=(
                '{"action":"create","skill_name":"new-skill","reason":"workflow",'
                '"content":"---\\nname: new-skill\\ndescription: new\\n---\\n# New\\nDo it.\\n"}'
            )
        )
    )
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_mode="suggest", review_min_tool_calls=1),
    )
    result = await review.review_turn(
        session_key="test",
        recent_messages=_review_messages(),
        final_content="done",
        stop_reason="completed",
        user_message="test",
    )
    assert result is None
    assert not (tmp_path / ".agent-state" / "skills" / "new-skill").exists()


@pytest.mark.asyncio
async def test_review_turn_handles_provider_exception_gracefully(tmp_path: Path) -> None:
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(side_effect=RuntimeError("provider down"))
    review = SkillReviewService(
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        config=SkillsConfig(review_enabled=True, review_mode="auto_create", review_min_tool_calls=1),
    )
    result = await review.review_turn(
        session_key="test",
        recent_messages=_review_messages(),
        final_content="done",
        stop_reason="completed",
        user_message="test",
    )
    assert result is None


@pytest.mark.asyncio
async def test_loop_schedules_skill_review_in_background(tmp_path: Path) -> None:
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        skills_config=SkillsConfig(review_enabled=True, review_mode="auto_create", review_min_tool_calls=0),
    )
    loop.consolidator.maybe_consolidate_by_tokens = AsyncMock()
    loop._run_agent_loop = AsyncMock(
        return_value=(
            "done",
            [],
            [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "done"},
            ],
            "completed",
        )
    )
    loop.skill_review.review_turn = AsyncMock(return_value=None)

    tasks: list[asyncio.Task] = []
    loop._schedule_background = lambda coro: tasks.append(asyncio.create_task(coro))  # type: ignore[method-assign]

    msg = InboundMessage(channel="cli", sender_id="user", chat_id="direct", content="hello")
    await loop._process_message(msg)
    await asyncio.gather(*tasks)

    loop.skill_review.review_turn.assert_awaited_once()
