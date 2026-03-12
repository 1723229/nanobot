---
name: feishu-bitable
description: 飞书多维表格 — 数据表 CRUD、日报录入、任务管理
metadata:
  requires:
    - type: binary
      name: python3
---

# 飞书多维表格 (Bitable)

飞书多维表格 API，支持数据表的 CRUD 操作和字段定义查询。

## 使用流程

1. 根据下方 API 函数说明确认所需操作
2. 通过 `exec` 工具调用脚本执行

## API 函数

### bitable_list_tables

获取多维表格中的数据表列表。

```
python3 scripts/feishu_bitable.py tables --app-token JXdtbkkchaSXmksx6eFc2Eatn45
```

### bitable_get_fields

获取字段定义。

```
python3 scripts/feishu_bitable.py fields --app-token TOKEN --table-id tblXXX
```

### bitable_list_records

查询多维表格记录。

```
python3 scripts/feishu_bitable.py list --app-token TOKEN --table-id tblXXX --limit 20
```

### bitable_add_record

创建记录。

```
python3 scripts/feishu_bitable.py add --app-token TOKEN --table-id tblXXX --fields '{"标题": "测试"}'
```

### bitable_update_record

更新记录。

```
python3 scripts/feishu_bitable.py update --app-token TOKEN --table-id tblXXX --record-id recXXX --fields '{"状态": "已完成"}'
```

### bitable_delete_record

删除记录。

```
python3 scripts/feishu_bitable.py delete --app-token TOKEN --table-id tblXXX --record-id recXXX
```

## 便捷函数：日报

```
python3 scripts/feishu_bitable.py daily-add --user-id ou_xxx --date 2026-03-12 --project "XX项目" --content "完成模块开发" --hours 8
python3 scripts/feishu_bitable.py daily-query --limit 10
```

## 便捷函数：任务

```
python3 scripts/feishu_bitable.py task-add --name "实现登录" --serial 1 --project recXXX --executor ou_xxx --status "进行中" --hours 4
python3 scripts/feishu_bitable.py task-query --limit 10
```

## 预置常量（团队多维表格）

| 常量 | 值 | 说明 |
|------|------|------|
| APP_TOKEN | JXdtbkkchaSXmksx6eFc2Eatn45 | 多维表格 app_token |
| DAILY_TABLE_ID | tblYWOnDxGsVSfDN | 日报表 |
| TASK_TABLE_ID | tblH6xn2dp6E1UtD | 任务表 |
| PROJECT_TABLE_ID | tblihZwJnOg84PUQ | 项目表 |

## 参数说明

- `app_token`: 多维表格的 token（从 URL 提取），如 `JXdtbkkchaSXmksx6eFc2Eatn45`
- `table_id`: 数据表 ID，如 `tblYWOnDxGsVSfDN`
- `record_id`: 记录 ID，如 `recXXX`

### 从 URL 提取 app_token

| URL 格式 | 说明 |
|----------|------|
| `https://xxx.feishu.cn/base/{app_token}?table=tblXXX` | 直接提取 |
| `https://xxx.feishu.cn/wiki/{node_token}?table=tblXXX` | 需先通过 Wiki API 获取 `obj_token` |

## 字段类型与写入格式

| 类型编号 | 字段类型 | 写入格式 | 示例 |
|----------|----------|----------|------|
| 1 | 多行文本 | string | `"Hello"` |
| 2 | 数字 | number | `2323.23` |
| 3 | 单选 | string | `"选项1"` |
| 4 | 多选 | string[] | `["选项1", "选项2"]` |
| 5 | 日期 | number（毫秒时间戳） | `1690992000000` |
| 7 | 复选框 | boolean | `true` |
| 11 | 人员 | object[] | `[{"id": "ou_xxx"}]` |
| 13 | 电话号码 | string | `"13800138000"` |
| 15 | 超链接 | object | `{"text": "链接", "link": "https://..."}` |
| 18 | 单向关联 | string[] | `["recXXX"]` |
| 21 | 双向关联 | string[] | `["recXXX"]` |
| 19/20/1001-1004 | 公式/创建时间等 | — | 只读 |

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 应用无法访问已有多维表格 | 文档右上角 → 更多 → 添加文档应用 |
| 日期字段传 ISO 字符串 | 必须传毫秒时间戳数字 |
| 人员字段传字符串 | 必须传 `[{"id": "ou_xxx"}]` 数组格式 |
| `app_token` 和 `table_id` 搞混 | `app_token` 是多维表格级别，`table_id` 是数据表级别 |
| Wiki URL 直接当 app_token | 需先 `wiki_get_node()` 获取 `obj_token` |

## 所需权限

- `bitable:app` — 多维表格完整权限
- 或 `bitable:app:readonly` — 只读权限

## 凭据

自动读取 `~/.hiperone/config.json` 或环境变量 `NANOBOT_CHANNELS__FEISHU__APP_ID` / `NANOBOT_CHANNELS__FEISHU__APP_SECRET`，无需手动配置。
