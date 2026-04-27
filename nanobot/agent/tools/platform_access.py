"""Runtime token-backed HTTP tools for platform data and knowledge access."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import httpx

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import ArraySchema, StringSchema, tool_parameters_schema

if TYPE_CHECKING:
    from nanobot.agent.tools.registry import ToolRegistry


class _RuntimeTokenProvider:
    """Fetch a fresh employee-platform access token for the bot owner."""

    def __init__(self, base_url: str, user_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._user_id = user_id.strip()

    async def fetch_access_token(self) -> str:
        if not self._base_url:
            raise RuntimeError("HIPERONE_EMPLOYEE_PLATFORM_BASE_URL is not configured")
        if not self._user_id:
            raise RuntimeError("HIPERONE_BOT_USER_ID is not configured")

        endpoint = f"{self._base_url}/api/bot/internal/runtime-token"
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.post(endpoint, json={"user_id": self._user_id})
            response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("runtime token response is not a JSON object")
        if int(payload.get("code", 500)) != 200:
            raise RuntimeError(str(payload.get("message") or "runtime token request failed"))

        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("runtime token payload is missing data")

        token = str(data.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("runtime token payload is missing access_token")
        return token


class _HttpPlatformTool(Tool):
    """Shared logic for HTTP-backed platform tools."""

    api_path: str = ""
    name: str = ""
    description: str = ""

    def __init__(self, token_provider: _RuntimeTokenProvider, base_url: str) -> None:
        self._token_provider = token_provider
        self._base_url = base_url.rstrip("/")

    @property
    def read_only(self) -> bool:
        return True

    async def _call_api(self, payload: dict[str, Any]) -> Any:
        try:
            access_token = await self._token_provider.fetch_access_token()
        except Exception as exc:
            return f"Error: failed to fetch runtime access token: {exc}"

        endpoint = f"{self._base_url}/{self.api_path.lstrip('/')}"
        request_payload = {**payload, "apexToken": access_token}
        try:
            async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
                response = await client.post(
                    endpoint,
                    json=request_payload,
                    headers={"apexToken": access_token},
                )
                response.raise_for_status()
            try:
                payload = response.json()
                if isinstance(payload, (dict, list)):
                    return json.dumps(payload, ensure_ascii=False)
                return payload
            except ValueError:
                return response.text
        except Exception as exc:
            return f"Error: HTTP call failed for '{self.name}': {exc}"


@tool_parameters(
    tool_parameters_schema(
        query=StringSchema("自然语言数据查询问题"),
        required=["query"],
    )
)
class QueryDataTool(_HttpPlatformTool):
    name = "query_data"
    api_path = "/data_agent"
    description = (
        "数据查询工具。将自然语言问题发送到内部数据服务。不要频繁调用，关键字：数据库。"
    )

    async def execute(self, query: str, **kwargs: Any) -> Any:
        return await self._call_api({"query": query, **kwargs})


@tool_parameters(
    tool_parameters_schema(
        query=StringSchema("用户的知识检索问题"),
        required=["query"],
    )
)
class SearchKnowledgeTool(_HttpPlatformTool):
    name = "search_knowledge"
    api_path = "/knowledge_retrieval"
    description = (
        "知识检索工具。从内部知识服务检索与问题相关的文档内容。不要频繁调用，关键字：文档、知识库。"
    )

    async def execute(self, query: str, **kwargs: Any) -> Any:
        return await self._call_api({"query": query, **kwargs})


def register_platform_access_tools(
    registry: "ToolRegistry",
    *,
    platform_base_url: str | None = None,
    user_id: str | None = None,
    sql_agent_base_url: str | None = None,
    kb_agent_base_url: str | None = None,
) -> None:
    """Register HTTP platform tools when runtime token config is present."""

    resolved_base_url = str(
        platform_base_url or os.environ.get("HIPERONE_EMPLOYEE_PLATFORM_BASE_URL") or ""
    ).strip()
    resolved_user_id = str(user_id or os.environ.get("HIPERONE_BOT_USER_ID") or "").strip()
    if not resolved_base_url or not resolved_user_id:
        return

    provider = _RuntimeTokenProvider(resolved_base_url, resolved_user_id)

    resolved_sql_base = str(
        sql_agent_base_url or os.environ.get("HIPERONE_SQL_AGENT_BASE_URL") or ""
    ).strip().rstrip("/")
    if resolved_sql_base:
        registry.register(QueryDataTool(token_provider=provider, base_url=resolved_sql_base))

    resolved_kb_base = str(
        kb_agent_base_url or os.environ.get("HIPERONE_KB_AGENT_BASE_URL") or ""
    ).strip().rstrip("/")
    if resolved_kb_base:
        registry.register(SearchKnowledgeTool(token_provider=provider, base_url=resolved_kb_base))
