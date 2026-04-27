from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from nanobot.agent.tools.platform_access import (
    QueryDataTool,
    SearchKnowledgeTool,
    register_platform_access_tools,
)
from nanobot.agent.tools.registry import ToolRegistry


class _FakeTokenProvider:
    def __init__(self, token: str = "token-123") -> None:
        self._token = token

    async def fetch_access_token(self) -> str:
        return self._token


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.text = str(payload)

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


@pytest.mark.asyncio
async def test_query_data_posts_to_http_api(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    class _FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            calls.append({"kind": "init", "kwargs": kwargs})

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(
            self,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> _FakeResponse:
            calls.append({"kind": "post", "url": url, "json": json, "headers": headers})
            return _FakeResponse({"transport": "http", "ok": True})

    monkeypatch.setattr("nanobot.agent.tools.platform_access.httpx.AsyncClient", _FakeAsyncClient)

    tool = QueryDataTool(
        token_provider=_FakeTokenProvider(),
        base_url="https://sql.example.com/",
    )

    result = await tool.execute(
        query="查询退役军人数量",
        theme_ids=["退伍"],
        skip_steps=["summary"],
    )

    assert json.loads(result) == {"transport": "http", "ok": True}
    assert calls[1]["url"] == "https://sql.example.com/data_agent"
    assert calls[1]["json"] == {
        "query": "查询退役军人数量",
        "theme_ids": ["退伍"],
        "skip_steps": ["summary"],
        "apexToken": "token-123",
    }
    assert calls[1]["headers"] == {"apexToken": "token-123"}


@pytest.mark.asyncio
async def test_search_knowledge_posts_to_http_api(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    class _FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            calls.append({"kind": "init", "kwargs": kwargs})

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(
            self,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> _FakeResponse:
            calls.append({"kind": "post", "url": url, "json": json, "headers": headers})
            return _FakeResponse({"transport": "http", "source": "kb"})

    monkeypatch.setattr("nanobot.agent.tools.platform_access.httpx.AsyncClient", _FakeAsyncClient)

    tool = SearchKnowledgeTool(
        token_provider=_FakeTokenProvider(),
        base_url="https://kb.example.com/",
    )

    result = await tool.execute(query="查询优抚政策")

    assert json.loads(result) == {"transport": "http", "source": "kb"}
    assert calls[1]["url"] == "https://kb.example.com/knowledge_retrieval"
    assert calls[1]["json"] == {
        "query": "查询优抚政策",
        "apexToken": "token-123",
    }
    assert calls[1]["headers"] == {"apexToken": "token-123"}


@pytest.mark.asyncio
async def test_query_data_reports_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenAsyncClient:
        async def __aenter__(self) -> "_BrokenAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(
            self,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> _FakeResponse:
            raise httpx.ConnectError("boom", request=httpx.Request("POST", url))

    monkeypatch.setattr("nanobot.agent.tools.platform_access.httpx.AsyncClient", _BrokenAsyncClient)

    tool = QueryDataTool(
        token_provider=_FakeTokenProvider(),
        base_url="https://sql.example.com",
    )

    result = await tool.execute(query="查询退役军人数量")

    assert "Error: HTTP call failed for 'query_data'" in result


def test_register_platform_access_tools_registers_only_configured_http_tools() -> None:
    registry = ToolRegistry()

    register_platform_access_tools(
        registry,
        platform_base_url="https://platform.example.com",
        user_id="u-1",
        sql_agent_base_url="https://sql.example.com",
    )

    assert registry.tool_names == ["query_data"]


def test_register_platform_access_tools_registers_both_tools() -> None:
    registry = ToolRegistry()

    register_platform_access_tools(
        registry,
        platform_base_url="https://platform.example.com",
        user_id="u-1",
        sql_agent_base_url="https://sql.example.com",
        kb_agent_base_url="https://kb.example.com",
    )

    assert registry.tool_names == ["query_data", "search_knowledge"]
