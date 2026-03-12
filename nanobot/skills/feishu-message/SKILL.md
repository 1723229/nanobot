---
name: feishu-message
description: 飞书消息收发 — 发送/回复/获取消息、会话历史
metadata:
  requires:
    - type: binary
      name: python3
---

# 飞书消息收发 (Message)

飞书消息 API，支持发送、回复、获取单条消息和会话历史。

## 使用流程

1. 根据下方 API 函数说明确认所需操作
2. 通过 `exec` 工具调用脚本执行

## API 函数

### send_text

发送文本消息。

```
python3 scripts/feishu_message.py send --receive-id oc_xxx --text "你好" --id-type chat_id
```

`--id-type` 可选值: chat_id / open_id / union_id / email

### get_message

获取单条消息详情。

```
python3 scripts/feishu_message.py get --message-id om_xxx
```

### get_chat_history

获取会话历史消息。

```
python3 scripts/feishu_message.py history --chat-id oc_xxx --limit 20
python3 scripts/feishu_message.py history --chat-id oc_xxx --start-time "1710000000" --end-time "1710086400"
```

时间为秒级时间戳字符串。

## 消息类型 msg_type

| 类型 | content 格式 |
|------|-------------|
| text | `{"text": "内容"}` |
| post | `{"zh_cn": {"title": "标题", "content": [[{"tag": "text", "text": "段落"}]]}}` |
| interactive | 卡片 JSON |
| image | `{"image_key": "img_xxx"}` |

## @ 用户语法

在文本消息中 @ 用户：`{"text": "<at user_id=\"ou_xxx\">张三</at> 请查看"}`

## 使用限制

- 向同一用户发消息限频：**5 QPS**
- 向同一群组发消息限频：群内机器人共享 **5 QPS**
- 文本消息最大 **150 KB**
- 卡片/富文本消息最大 **30 KB**

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| `content` 传对象 | 必须 `json.dumps({"text": "hello"})` |
| 群聊 ID 用 `open_id` 类型 | `oc_` 开头的是 `chat_id` |
| 富文本 content 不是二维数组 | `content: [[{"tag":"text", "text":"..."}]]` 外层是行数组 |
| 忘记开启机器人能力 | 应用能力 → 添加机器人 |

## 所需权限

- `im:message:send_as_bot` — 发送消息
- `im:message:readonly` — 获取消息
- `im:message` — 完整消息权限

## 凭据

自动读取 `~/.hiperone/config.json` 或环境变量 `NANOBOT_CHANNELS__FEISHU__APP_ID` / `NANOBOT_CHANNELS__FEISHU__APP_SECRET`，无需手动配置。
