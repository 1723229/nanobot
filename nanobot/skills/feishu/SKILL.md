---
name: feishu
description: |
  飞书统一 API 技能 — 覆盖群组、消息、通讯录、考勤、云文档、多维表格、审批、
  日历、任务、知识库、云空间等全部常用飞书开放平台接口。
  当用户涉及飞书相关操作（发消息、查群成员、查考勤、读文档、操作多维表格、
  审批、日程管理等）时使用此技能。凭据自动从配置文件或环境变量读取。
metadata:
  requires:
    - type: binary
      name: python3
---

# 飞书统一 API 技能

## 脚本路径

1. 确定本 SKILL.md 所在目录路径，记为 `SKILL_DIR`
2. 脚本路径 = `${SKILL_DIR}/scripts/feishu_api.py`

## 使用流程

1. 根据用户请求，从下方快速索引找到对应模块
2. 阅读对应的 reference 文件获取函数签名和参数说明
3. 通过 `exec` 工具调用脚本执行操作

## 快速索引

| 模块 | Reference 文件 | 说明 |
|------|---------------|------|
| 群组管理 | `references/chat.md` | 列出群组、获取群信息、群成员 |
| 消息收发 | `references/message.md` | 发送/回复/获取消息、会话历史 |
| 通讯录 | `references/contact.md` | 用户信息、部门查询 |
| 考勤 | `references/attendance.md` | 打卡记录查询 |
| 云文档 | `references/doc.md` | 文件列表、读取文档、搜索文档 |
| 多维表格 | `references/bitable.md` | 数据表 CRUD、日报/任务便捷函数 |
| 审批 | `references/approval.md` | 审批定义、实例管理、请假审批 |
| 日历日程 | `references/calendar.md` | 日历列表、日程 CRUD、忙闲查询、会议室 |
| 任务管理 | `references/task.md` | 任务 CRUD、任务清单 |
| 知识库 | `references/wiki.md` | 知识空间、节点管理、搜索 |
| 云空间 | `references/drive.md` | 文件夹、上传/下载、权限管理 |

## CLI 调用格式

```bash
python3 ${SKILL_DIR}/scripts/feishu_api.py <module> <action> [options]
```

示例：

```bash
python3 ${SKILL_DIR}/scripts/feishu_api.py chat list
python3 ${SKILL_DIR}/scripts/feishu_api.py chat members --chat-id oc_xxx --all
python3 ${SKILL_DIR}/scripts/feishu_api.py message send --receive-id oc_xxx --text "Hello"
python3 ${SKILL_DIR}/scripts/feishu_api.py contact user --user-id ou_xxx
python3 ${SKILL_DIR}/scripts/feishu_api.py doc search --keyword "季度报告"
python3 ${SKILL_DIR}/scripts/feishu_api.py bitable daily-query --limit 10
python3 ${SKILL_DIR}/scripts/feishu_api.py approval list --code E565EC28-...
python3 ${SKILL_DIR}/scripts/feishu_api.py calendar events --calendar-id primary
```

## 凭据配置

优先读取 `~/.hiperone/config.json`：

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx"
    }
  }
}
```

回退到环境变量：`NANOBOT_CHANNELS__FEISHU__APP_ID` / `NANOBOT_CHANNELS__FEISHU__APP_SECRET`

## ID 类型说明

| 类型 | 前缀 | 说明 |
|------|------|------|
| open_id | `ou_` | 用户在应用内的唯一标识（最常用） |
| union_id | `on_` | 同一开发者下应用的用户唯一标识 |
| user_id | | 企业自定义用户 ID |
| chat_id | `oc_` | 群聊 ID |
| message_id | `om_` | 消息 ID |
| employee_id | | 员工工号（考勤等场景） |

## 常见错误码

| 错误码 | 含义 | 解决方式 |
|--------|------|----------|
| 99991663 | token 无效/过期 | 检查 app_id/app_secret 是否正确 |
| 99991668 | 用户不在通讯录权限范围 | 安全设置 → 通讯录权限范围 → 全部成员 |
| 99991672 | 无权限 | 在开发者后台开通对应 API 权限 |
| 99991400 | 参数错误 | 检查必填字段和参数类型 |
| 40004 | 无部门权限 | 配置通讯录权限范围为「全部成员」 |
| 230001 | 应用不可见/未安装 | 管理员审核发布应用 |

## 日期格式速查

| API 模块 | 格式 | 示例 |
|----------|------|------|
| 日历 | RFC3339 | `"2026-03-12T09:00:00+08:00"` |
| 审批（请假） | RFC3339 | `"2026-03-12T00:00:00+08:00"` |
| 考勤 | yyyyMMdd 整数 | `20260312` |
| 多维表格（日期字段） | 毫秒时间戳 | `1690992000000` |
| 消息历史 | 秒级时间戳字符串 | `"1710000000"` |
