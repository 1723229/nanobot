---
name: feishu-calendar
description: 飞书日历与日程 — 日历列表、日程 CRUD、忙闲查询、会议室
metadata:
  requires:
    - type: binary
      name: python3
---

# 飞书日历与日程 (Calendar)

飞书日历 API，管理日历、日程、忙闲查询和会议室。

## 使用流程

1. 根据下方 API 函数说明确认所需操作
2. 通过 `exec` 工具调用脚本执行

## API 函数

### calendar_list

获取日历列表。

```
python3 scripts/feishu_calendar.py list
```

### calendar_list_events

获取日程列表（"primary" 表示主日历）。

```
python3 scripts/feishu_calendar.py events --calendar-id primary --limit 50
python3 scripts/feishu_calendar.py events --calendar-id primary --start-time "2026-03-12T00:00:00+08:00" --end-time "2026-03-13T00:00:00+08:00"
```

### calendar_create_event

创建日程。

```
python3 scripts/feishu_calendar.py create-event --summary "团队周会" --start-time "2026-03-15T14:00:00+08:00" --end-time "2026-03-15T15:00:00+08:00" --description "讨论进展"
```

### 其他函数（通过脚本 Python API 调用）

- `calendar_get(calendar_id)` — 获取日历信息
- `calendar_get_event(calendar_id, event_id)` — 获取日程详情
- `calendar_update_event(calendar_id, event_id, fields)` — 更新日程
- `calendar_delete_event(calendar_id, event_id)` — 删除日程
- `calendar_freebusy(user_ids, start_time, end_time)` — 查询忙闲
- `meeting_room_search(query)` — 搜索会议室
- `meeting_reserve(end_time, meeting_settings)` — 预约会议

## 典型工作流

### 预约会议室

1. `meeting_room_search("大会议室")` → 搜索会议室
2. `calendar_freebusy(user_ids, start, end)` → 查询忙闲
3. `calendar_create_event(...)` → 创建日程并添加参与人

## 时间格式

日历 API 使用 RFC3339 格式：`2026-03-12T14:00:00+08:00`

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 时间传 Unix 时间戳 | 日历 API 需要 RFC3339 字符串 |
| 忘记传 `calendar_id` | 必须传，主日历用 `"primary"` |
| 会议室查询用日历 API | 会议室在 `vc` 域下：`meeting_room_search` |

## 所需权限

- `calendar:calendar` — 日历完整权限
- `calendar:calendar:readonly` — 只读权限
- `vc:room:readonly` — 查询会议室
- `vc:reserve` — 预约会议

## 凭据

自动读取 `~/.hiperone/config.json` 或环境变量 `NANOBOT_CHANNELS__FEISHU__APP_ID` / `NANOBOT_CHANNELS__FEISHU__APP_SECRET`，无需手动配置。
