#!/usr/bin/env python3
"""feishu_drive - 飞书云空间/文件管理 API

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


def _delete(path: str, *, timeout: int = 10, action: str = "") -> dict:
    resp = requests.delete(f"{BASE_URL}{path}", headers=_headers(), timeout=timeout)
    return _check(resp.json(), action or path)


def _pp(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ============================================================
# 云空间 / 文件管理 (drive/v1)
# ============================================================

def drive_list_files(
    folder_token: str = "",
    page_size: int = 50,
    page_token: str = "",
    order_by: str = "EditedTime",
    direction: str = "DESC",
) -> Dict[str, Any]:
    """列出文件夹中的文件和子文件夹

    Args:
        folder_token: 文件夹 token，空字符串表示根目录
        page_size: 每页数量（最大 200）
        order_by: 排序字段 EditedTime | CreatedTime
        direction: ASC | DESC
    """
    params: Dict[str, Any] = {
        "page_size": min(page_size, 200),
        "order_by": order_by,
        "direction": direction,
    }
    if folder_token:
        params["folder_token"] = folder_token
    if page_token:
        params["page_token"] = page_token
    return _get("/drive/v1/files", params, action="列出文件")


def drive_search(
    search_key: str,
    count: int = 20,
    docs_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """搜索云文档

    Args:
        search_key: 搜索关键词
        count: 返回数量（最大 50）
        docs_types: 过滤文档类型列表，如 ["doc","sheet","bitable","folder"]
    """
    payload: Dict[str, Any] = {"search_key": search_key, "count": min(count, 50)}
    if docs_types:
        payload["docs_types"] = docs_types
    return _post("/suite/docs-api/search/object", payload, action="搜索云文档")


def drive_create_folder(
    name: str,
    folder_token: str = "",
) -> Dict[str, Any]:
    """创建文件夹"""
    payload: Dict[str, Any] = {"name": name, "folder_token": folder_token}
    return _post("/drive/v1/files/create_folder", payload, action="创建文件夹")


def drive_upload_file(
    file_path: str,
    parent_node: str,
    file_name: str = "",
) -> Dict[str, Any]:
    """上传文件到云空间（< 20MB）"""
    name = file_name or os.path.basename(file_path)
    size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/drive/v1/files/upload_all",
            headers={"Authorization": f"Bearer {get_tenant_access_token()}"},
            data={"file_name": name, "parent_type": "explorer", "parent_node": parent_node, "size": str(size)},
            files={"file": (name, f)},
            timeout=60,
        )
    return _check(resp.json(), "上传文件")


def drive_download_file(file_token: str, save_path: str) -> str:
    """下载文件"""
    resp = requests.get(
        f"{BASE_URL}/drive/v1/files/{file_token}/download",
        headers=_headers(), stream=True, timeout=60,
    )
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    return save_path


def drive_move_file(file_token: str, dst_folder_token: str) -> Dict[str, Any]:
    """移动文件"""
    return _post(f"/drive/v1/files/{file_token}/move",
                 {"folder_token": dst_folder_token}, action="移动文件")


def drive_copy_file(file_token: str, dst_folder_token: str, name: str = "") -> Dict[str, Any]:
    """复制文件"""
    payload: Dict[str, Any] = {"folder_token": dst_folder_token}
    if name:
        payload["name"] = name
    return _post(f"/drive/v1/files/{file_token}/copy", payload, action="复制文件")


def drive_delete_file(file_token: str) -> Dict[str, Any]:
    """删除文件"""
    return _delete(f"/drive/v1/files/{file_token}", action="删除文件")


def drive_add_permission(
    token: str,
    member_type: str,
    member_id: str,
    perm: str = "view",
    token_type: str = "doc",
) -> Dict[str, Any]:
    """添加文档权限"""
    return _post(f"/drive/v1/permissions/{token}/members",
                 {"member_type": member_type, "member_id": member_id, "perm": perm},
                 params={"type": token_type}, action="添加文档权限")


# ============================================================
# CLI
# ============================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="feishu_drive", description="飞书云空间/文件管理")
    sub = parser.add_subparsers(dest="action")

    p = sub.add_parser("list", help="列出文件夹内容")
    p.add_argument("--folder-token", default="", help="文件夹 token，空=根目录")
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("search", help="搜索云文档")
    p.add_argument("--keyword", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--types", default="", help="文档类型过滤，逗号分隔: doc,sheet,bitable,folder")

    p = sub.add_parser("mkdir", help="创建文件夹")
    p.add_argument("--name", required=True)
    p.add_argument("--folder-token", default="")

    p = sub.add_parser("upload", help="上传文件")
    p.add_argument("--file", required=True)
    p.add_argument("--parent-node", required=True)

    p = sub.add_parser("download", help="下载文件")
    p.add_argument("--file-token", required=True)
    p.add_argument("--save-path", required=True)

    return parser


def _run_cli(args: argparse.Namespace) -> None:
    act = args.action
    if act == "list":
        _pp(drive_list_files(args.folder_token, args.limit))
    elif act == "search":
        types = [t.strip() for t in args.types.split(",") if t.strip()] if args.types else None
        _pp(drive_search(args.keyword, args.limit, types))
    elif act == "mkdir":
        _pp(drive_create_folder(args.name, args.folder_token))
    elif act == "upload":
        _pp(drive_upload_file(args.file, args.parent_node))
    elif act == "download":
        print(drive_download_file(args.file_token, args.save_path))


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
