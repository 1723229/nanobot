---
name: feishu-bitable
description: 飞书多维表格 — 数据表 CRUD、智能字段转换、日报/任务录入、批量操作。当用户提及多维表格、bitable、数据表、日报录入、任务录入、写日报、记录任务时，务必先读取此技能。
metadata:
  requires:
    - type: binary
      name: python3
---

# 飞书多维表格 (Bitable)

支持飞书多维表格 API，支持数据表的 CRUD 操作和字段定义查询、智能字段格式转换、便捷业务函数、批量操作。

## 功能特点

### 1. 智能字段转换
自动处理日期、用户、多选等字段格式，无需手动转换毫秒时间戳。

### 2. 错误提示优化
API 错误码映射为可读提示，快速定位问题。

### 3. 便捷函数
- `daily-add` - 录入日报
- `task-add` - 录入任务（完整功能）

### 4. 批量操作
- `batch-add` - 批量创建记录
- `batch-update` - 批量更新记录
- `batch-delete` - 批量删除记录

---

## API 函数

### 基础函数

| 函数 | 说明 |
|------|------|
| `bitable_list_tables` | 获取数据表列表 |
| `bitable_get_fields` | 获取字段定义 |
| `bitable_list_records` | 查询记录（支持 filter 表达式） |
| `bitable_add_record` | 创建记录 |
| `bitable_add_record_smart` | 创建记录（智能转换格式） |
| `bitable_update_record` | 更新记录 |
| `bitable_update_record_smart` | 更新记录（智能转换格式） |
| `bitable_delete_record` | 删除记录 |
| `bitable_batch_add_records` | 批量创建记录（飞书批量 API，单次最多 500 条） |
| `bitable_batch_update_records` | 批量更新记录（单次最多 500 条） |
| `bitable_batch_delete_records` | 批量删除记录（单次最多 500 条） |

### 便捷函数

| 函数 | 说明 |
|------|------|
| `bitable_add_daily_report` | 录入日报 |
| `bitable_query_daily_reports` | 查询日报 |
| `bitable_add_task` | 录入任务 |
| `bitable_query_tasks` | 查询任务 |

---

## 使用示例

### 智能创建记录

```bash
# 自动转换日期和用户字段格式
python3 scripts/feishu_bitable.py add-smart \
  --app-token JXdtbkkchaSXmksx6eFc2Eatn45 \
  --table-id tblH6xn2dp6E1UtD \
  --fields '{"任务名称":"测试任务","执行人":"ou_xxx","计划截止时间":"2026-03-14","状态":["待处理"]}'
```

### 录入日报

```bash
python3 scripts/feishu_bitable.py daily-add \
  --user-id ou_617ce34ae1db1f2b7eb2aa04f55aca11 \
  --date 2026-03-13 \
  --project hiperone_bot 开发 \
  --content "完成功能开发" \
  --hours 8
```

### 录入任务

```bash
python3 scripts/feishu_bitable.py task-add \
  --name "明天休息下" \
  --project recXXX \
  --executor ou_617ce34ae1db1f2b7eb2aa04f55aca11 \
  --status 待处理 \
  --deadline 7 \
  --hours 0 \
  --description "个人休息日"
```

### 智能更新记录

```bash
python3 scripts/feishu_bitable.py update-smart \
  --app-token JXdtbkkchaSXmksx6eFc2Eatn45 \
  --table-id tblH6xn2dp6E1UtD \
  --record-id recXXX \
  --fields '{"状态":"完成","实际完成时间":"2026-03-13"}'
```

### 批量创建记录

```bash
# 普通批量
python3 scripts/feishu_bitable.py batch-add \
  --app-token JXdtbkkchaSXmksx6eFc2Eatn45 \
  --table-id tblH6xn2dp6E1UtD \
  --records '[{"任务名称":"任务 1","状态":["待处理"]},{"任务名称":"任务 2","状态":["待处理"]}]'

# 带智能转换的批量
python3 scripts/feishu_bitable.py batch-add \
  --app-token JXdtbkkchaSXmksx6eFc2Eatn45 \
  --table-id tblH6xn2dp6E1UtD \
  --records '[{"任务名称":"任务","执行人":"ou_xxx","计划截止时间":"2026-03-20"}]' \
  --smart
```

### 批量更新记录

```bash
python3 scripts/feishu_bitable.py batch-update \
  --app-token JXdtbkkchaSXmksx6eFc2Eatn45 \
  --table-id tblH6xn2dp6E1UtD \
  --records '[{"record_id":"recXXX","fields":{"状态":"完成"}},{"record_id":"recYYY","fields":{"状态":"完成"}}]'
```

### 批量删除记录

```bash
python3 scripts/feishu_bitable.py batch-delete \
  --app-token JXdtbkkchaSXmksx6eFc2Eatn45 \
  --table-id tblH6xn2dp6E1UtD \
  --record-ids '["recXXX","recYYY"]'
```

### 带过滤条件查询

```bash
python3 scripts/feishu_bitable.py list \
  --app-token JXdtbkkchaSXmksx6eFc2Eatn45 \
  --table-id tblYWOnDxGsVSfDN \
  --filter 'CurrentValue.[项目]="华谊问数问知"' \
  --limit 10
```

---

## 字段格式自动转换

| 字段类型 | 输入格式 | 自动转换为 |
|---------|---------|-----------|
| DateTime | `"2026-03-14"` | 毫秒时间戳 |
| DateTime | `1773417600000` | 保持不变 |
| User | `"ou_xxx"` | `[{"id":"ou_xxx"}]` |
| MultiSelect | `"选项"` | `["选项"]` |
| Number | `"8"` | `8` |

---

## 错误码提示

| 错误码 | 提示 |
|--------|------|
| 1254045 | 字段名不存在，请先调用 bitable_get_fields 查看字段定义 |
| 1254064 | 日期字段格式错误，请使用毫秒时间戳或 YYYY-MM-DD 格式 |
| 1254066 | 用户字段格式错误，请提供有效的 open_id 或 union_id |
| 1254063 | 单选/多选字段值错误，请检查选项是否存在 |

---

## 预置常量

| 常量 | 值 | 说明 |
|------|------|------|
| BITABLE_APP_TOKEN | JXdtbkkchaSXmksx6eFc2Eatn45 | 多维表格 app_token |
| DAILY_TABLE_ID | tblYWOnDxGsVSfDN | 日报表 |
| TASK_TABLE_ID | tblH6xn2dp6E1UtD | 任务表 |
| PROJECT_TABLE_ID | tblihZwJnOg84PUQ | 项目表 |

---

## 字段缓存

`bitable_add_record_smart` 和 `bitable_update_record_smart` 会自动缓存字段定义，避免重复 API 调用。日期转换统一使用 UTC+8 (Asia/Shanghai) 时区。

```python
# 首次调用会获取字段定义并缓存
bitable_add_record_smart(app_token, table_id, fields)

# 后续调用使用缓存，性能更好
bitable_add_record_smart(app_token, table_id, fields2)
```

---

## CLI 命令

| 命令 | 说明 |
|------|------|
| `tables` | 列出数据表 |
| `fields` | 获取字段定义 |
| `list` | 查询记录（支持 `--filter`） |
| `add` | 创建记录 |
| `add-smart` | 创建记录（智能转换格式） |
| `update` | 更新记录 |
| `update-smart` | 更新记录（智能转换格式） |
| `delete` | 删除记录 |
| `batch-add` | 批量创建记录（支持 `--smart`） |
| `batch-update` | 批量更新记录 |
| `batch-delete` | 批量删除记录 |
| `daily-add` | 录入日报 |
| `daily-query` | 查询日报 |
| `task-add` | 录入任务 |
| `task-query` | 查询任务 |

---
