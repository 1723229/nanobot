#!/usr/bin/env python3
"""feishu_wiki - 飞书知识库 API

凭据获取优先级: ~/.hiperone/config.json > 环境变量
"""

import argparse
import json
import os
import sys
import time as _time
import requests
from typing import Any, Dict, List, Optional


BASE_URL = "https://open.feishu.cn/open-apis"


def _load_nanobot_config() -> Dict[str, str]:
    config_path = os.path.expanduser("~/.hiperone/config.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            feishu = config.get("channels", {}).get("feishu", {})
            if feishu.get("enabled"):
                return {"appId": feishu.get("appId"), "appSecret": feishu.get("appSecret")}
    except Exception:
        pass
    return {}


_nanobot_cfg = _load_nanobot_config()
APP_ID = _nanobot_cfg.get("appId") or os.environ.get("NANOBOT_CHANNELS__FEISHU__APP_ID", "")
APP_SECRET = _nanobot_cfg.get("appSecret") or os.environ.get("NANOBOT_CHANNELS__FEISHU__APP_SECRET", "")
_token_cache: Dict[str, Any] = {"token": "", "expires": 0}


def get_tenant_access_token() -> str:
    if not APP_ID or not APP_SECRET:
        raise RuntimeError(
            "缺少飞书凭据，请配置 ~/.hiperone/config.json 或设置环境变量 "
            "NANOBOT_CHANNELS__FEISHU__APP_ID / NANOBOT_CHANNELS__FEISHU__APP_SECRET"
        )
    now = _time.time()
    if _token_cache["token"] and now < _token_cache["expires"]:
        return _token_cache["token"]
    url = f"{BASE_URL}/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 Token 失败: {data}")
    _token_cache["token"] = data["tenant_access_token"]
    _token_cache["expires"] = now + data.get("expire", 7200) - 60
    return _token_cache["token"]


def _headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {get_tenant_access_token()}"}


def _check(data: dict, action: str) -> dict:
    if data.get("code") != 0:
        raise RuntimeError(f"{action}失败: [{data.get('code')}] {data.get('msg', 'Unknown error')}")
    return data.get("data", {})


def _get(path: str, params: Optional[dict] = None, *, timeout: int = 10, action: str = "") -> dict:
    resp = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params, timeout=timeout)
    return _check(resp.json(), action or path)


def _post(path: str, payload: Optional[dict] = None, *, params: Optional[dict] = None,
          timeout: int = 10, action: str = "") -> dict:
    resp = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=payload,
                         params=params, timeout=timeout)
    return _check(resp.json(), action or path)


def _pp(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ============================================================
# 知识库 (wiki/v2)
# ============================================================

def wiki_list_spaces(page_size: int = 50, page_token: str = "") -> Dict[str, Any]:
    """获取知识空间列表"""
    params: Dict[str, Any] = {"page_size": page_size}
    if page_token:
        params["page_token"] = page_token
    return _get("/wiki/v2/spaces", params, action="获取知识空间列表")


def wiki_get_space(space_id: str) -> Dict[str, Any]:
    """获取知识空间信息"""
    return _get(f"/wiki/v2/spaces/{space_id}", action="获取知识空间信息")


def wiki_list_nodes(
    space_id: str,
    parent_node_token: str = "",
    page_size: int = 50,
    page_token: str = "",
) -> Dict[str, Any]:
    """获取知识空间节点列表"""
    params: Dict[str, Any] = {"page_size": page_size}
    if parent_node_token:
        params["parent_node_token"] = parent_node_token
    if page_token:
        params["page_token"] = page_token
    return _get(f"/wiki/v2/spaces/{space_id}/nodes", params, action="获取知识空间节点")


def wiki_get_node(space_id: str, node_token: str) -> Dict[str, Any]:
    """获取知识库节点信息"""
    return _get(f"/wiki/v2/spaces/{space_id}/nodes/{node_token}",
                action="获取知识库节点信息")


def wiki_create_node(
    space_id: str,
    obj_type: str,
    parent_node_token: str = "",
    title: str = "",
    obj_token: str = "",
) -> Dict[str, Any]:
    """创建知识库节点（或移入已有文档）"""
    payload: Dict[str, Any] = {"obj_type": obj_type}
    if parent_node_token:
        payload["parent_node_token"] = parent_node_token
    if title:
        payload["title"] = title
    if obj_token:
        payload["obj_token"] = obj_token
    return _post(f"/wiki/v2/spaces/{space_id}/nodes", payload,
                 action="创建知识库节点")


def wiki_search(
    keyword: str,
    count: int = 20,
) -> Dict[str, Any]:
    """搜索知识库（通过通用文档搜索 API，使用 tenant_access_token）"""
    payload: Dict[str, Any] = {
        "search_key": keyword,
        "count": min(count, 50),
        "docs_types": ["wiki"],
    }
    return _post("/suite/docs-api/search/object", payload, action="搜索知识库")


# ============================================================
# CLI
# ============================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="feishu_wiki", description="飞书知识库")
    sub = parser.add_subparsers(dest="action")
    p = sub.add_parser("spaces", help="列出知识空间")
    p = sub.add_parser("nodes", help="列出节点")
    p.add_argument("--space-id", required=True)
    p.add_argument("--parent-node", default="")
    p = sub.add_parser("search", help="搜索知识库")
    p.add_argument("--keyword", required=True)
    p.add_argument("--limit", type=int, default=20)
    return parser


def _run_cli(args: argparse.Namespace) -> None:
    act = args.action
    if act == "spaces":
        _pp(wiki_list_spaces())
    elif act == "nodes":
        _pp(wiki_list_nodes(args.space_id, args.parent_node))
    elif act == "search":
        _pp(wiki_search(args.keyword, args.limit))


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        return 1
    try:
        _run_cli(args)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
