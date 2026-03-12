---
name: feishu-chat
description: 飞书群组管理 — 列出群组、获取群信息、获取群成员列表
metadata:
  requires:
    - type: binary
      name: python3
---

# 飞书群组管理 (Chat)

飞书 IM 群组相关 API，管理机器人所在的群、获取群信息和群成员。

## 使用流程

1. 根据下方 API 函数说明确认所需操作
2. 通过 `exec` 工具调用脚本执行

## API 函数

### list_chats

获取机器人所在的群列表。

```
python3 scripts/feishu_chat.py list --limit 20
```

返回: `items` -> [{chat_id, name, description, owner_id, ...}], `has_more`, `page_token`

### get_chat

获取群详细信息。

```
python3 scripts/feishu_chat.py info --chat-id oc_xxx
```

返回: {chat_id, name, description, owner_id, chat_mode, chat_type, ...}

### get_chat_members

获取群成员列表（单页）。

```
python3 scripts/feishu_chat.py members --chat-id oc_xxx --limit 50
```

返回: `items` -> [{member_id, name, tenant_key}], `has_more`

### get_chat_members_all

获取群全部成员（自动分页）。

```
python3 scripts/feishu_chat.py members --chat-id oc_xxx --all
```

返回: [{member_id, name, tenant_key}, ...]

## ID 前缀对应关系

| receive_id_type | ID 前缀 | 说明 |
|-----------------|---------|------|
| `chat_id` | `oc_` | 群聊 ID |
| `open_id` | `ou_` | 用户 open_id |
| `union_id` | `on_` | 用户 union_id |

## 所需权限

- `im:chat:readonly` — 获取群组信息
- `im:chat.member:read` — 获取群成员

## 凭据

自动读取 `~/.hiperone/config.json` 或环境变量 `NANOBOT_CHANNELS__FEISHU__APP_ID` / `NANOBOT_CHANNELS__FEISHU__APP_SECRET`，无需手动配置。
