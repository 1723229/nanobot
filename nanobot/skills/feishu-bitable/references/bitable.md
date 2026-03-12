# 多维表格 (Bitable)

飞书多维表格 API，支持数据表的 CRUD 操作和字段定义查询。

## API 函数

### bitable_list_tables

获取多维表格中的数据表列表。

```python
from feishu_api import bitable_list_tables

data = bitable_list_tables("JXdtbkkchaSXmksx6eFc2Eatn45")
# data["items"] -> [{table_id, name, revision}]
```

**CLI**:
```bash
python3 scripts/feishu_api.py bitable tables --app-token JXdtbkkchaSXmksx6eFc2Eatn45
```

### bitable_get_fields

获取字段定义。

```python
from feishu_api import bitable_get_fields

data = bitable_get_fields("JXdtbkkchaSXmksx6eFc2Eatn45", "tblXXX")
# data["items"] -> [{field_id, field_name, type, ...}]
```

**CLI**:
```bash
python3 scripts/feishu_api.py bitable fields --app-token JXdtbkkchaSXmksx6eFc2Eatn45 --table-id tblXXX
```

### bitable_list_records

查询多维表格记录。

```python
from feishu_api import bitable_list_records

data = bitable_list_records("JXdtbkkchaSXmksx6eFc2Eatn45", "tblXXX", page_size=20)
# data["items"] -> [{record_id, fields: {...}}]
# data["has_more"], data["page_token"]
```

**CLI**:
```bash
python3 scripts/feishu_api.py bitable list --app-token JXdtbkkchaSXmksx6eFc2Eatn45 --table-id tblXXX --limit 20
```

### bitable_add_record

创建记录。

```python
from feishu_api import bitable_add_record

data = bitable_add_record("JXdtbkkchaSXmksx6eFc2Eatn45", "tblXXX", {
    "标题": "测试记录",
    "状态": "进行中",
})
# data["record"] -> {record_id, fields}
```

**CLI**:
```bash
python3 scripts/feishu_api.py bitable add --app-token ... --table-id ... --fields '{"标题": "测试"}'
```

### bitable_update_record

更新记录。

```python
from feishu_api import bitable_update_record

data = bitable_update_record("JXdtbkkchaSXmksx6eFc2Eatn45", "tblXXX", "recXXX", {
    "状态": "已完成",
})
```

**CLI**:
```bash
python3 scripts/feishu_api.py bitable update --app-token ... --table-id ... --record-id recXXX --fields '{"状态": "已完成"}'
```

### bitable_delete_record

删除记录。

```python
from feishu_api import bitable_delete_record

data = bitable_delete_record("JXdtbkkchaSXmksx6eFc2Eatn45", "tblXXX", "recXXX")
```

**CLI**:
```bash
python3 scripts/feishu_api.py bitable delete --app-token ... --table-id ... --record-id recXXX
```

## 预置常量（团队多维表格）

```python
APP_TOKEN        = "JXdtbkkchaSXmksx6eFc2Eatn45"   # 多维表格 app_token
DAILY_TABLE_ID   = "tblYWOnDxGsVSfDN"               # 日报表
TASK_TABLE_ID    = "tblH6xn2dp6E1UtD"               # 任务表
PROJECT_TABLE_ID = "tblihZwJnOg84PUQ"               # 项目表
```

## 便捷函数：日报

### bitable_add_daily_report

录入日报记录。

```python
from feishu_api import bitable_add_daily_report

data = bitable_add_daily_report(
    user_id="ou_xxx",        # 用户飞书 open_id
    date="2026-03-12",       # 日期
    project="XX项目",        # 项目名称
    content="完成模块开发",   # 工作内容
    hours=8,                 # 时长（小时）
)
# data["record"] -> {record_id, fields}
```

**CLI**:
```bash
python3 scripts/feishu_api.py bitable daily-add --user-id ou_xxx --date 2026-03-12 \
    --project "XX项目" --content "完成模块开发" --hours 8
```

### bitable_query_daily_reports

查询日报记录。

```python
from feishu_api import bitable_query_daily_reports

data = bitable_query_daily_reports(page_size=10)
# data["items"] -> [{record_id, fields: {姓名, 日期, 项目, 工作内容, 时长}}]
```

**CLI**:
```bash
python3 scripts/feishu_api.py bitable daily-query --limit 10
```

## 便捷函数：任务

### bitable_add_task

录入任务记录（自动检测状态字段类型：多选/单选）。

```python
from feishu_api import bitable_add_task

data = bitable_add_task(
    task_name="实现登录功能",
    serial_number=1,
    project_record_id="recXXX",     # 所属项目的 record_id
    executor_id="ou_xxx",            # 执行人 open_id
    status="进行中",
    deadline_days=7,                 # 截止天数（从今天算起）
    estimated_hours=4,
    description="包含手机号登录",
    table_id="tblH6xn2dp6E1UtD",    # 可选，默认 TASK_TABLE_ID
)
```

**CLI**:
```bash
python3 scripts/feishu_api.py bitable task-add --name "实现登录功能" --serial 1 \
    --project recXXX --executor ou_xxx --status "进行中" --hours 4
```

### bitable_query_tasks

查询任务记录。

```python
from feishu_api import bitable_query_tasks

data = bitable_query_tasks(page_size=10)
# data["items"] -> [{record_id, fields: {任务名称, 序号, 状态, 执行人, 预计耗时, ...}}]
```

**CLI**:
```bash
python3 scripts/feishu_api.py bitable task-query --limit 10
```

## 参数说明

- `app_token`: 多维表格的 token（从 URL 中获取），如 `JXdtbkkchaSXmksx6eFc2Eatn45`
- `table_id`: 数据表 ID，如 `tblYWOnDxGsVSfDN`
- `record_id`: 记录 ID，如 `recXXX`

### 从 URL 提取 app_token

| URL 格式 | 说明 |
|----------|------|
| `https://xxx.feishu.cn/base/{app_token}?table=tblXXX` | 直接提取 `app_token` |
| `https://xxx.feishu.cn/wiki/{node_token}?table=tblXXX` | 需先通过 Wiki API 的 `wiki_get_node` 获取 `obj_token` |

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
| 17 | 附件 | object[] | `[{"file_token": "xxx"}]` |
| 18 | 单向关联 | string[] | `["recXXX"]` |
| 19 | 查找引用 | — | 只读，由关联字段自动计算 |
| 20 | 公式 | — | 只读，由公式自动计算 |
| 21 | 双向关联 | string[] | `["recXXX"]` |
| 22 | 地理位置 | object | `{"location": "北京市朝阳区"}` |
| 23 | 群组 | string[] | `["oc_xxx"]` |
| 1001 | 创建时间 | — | 只读 |
| 1002 | 修改时间 | — | 只读 |
| 1003 | 创建人 | — | 只读 |
| 1004 | 修改人 | — | 只读 |

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 应用无法访问已有多维表格 | 需先将应用添加为协作者：文档右上角「...」→「更多」→「添加文档应用」 |
| 日期字段传 ISO 字符串 | 必须传毫秒时间戳数字，如 `1690992000000` |
| 人员字段传字符串 | 必须传 `[{"id": "ou_xxx"}]` 数组格式 |
| 单选/多选传不存在的选项 | 选项会自动创建，注意拼写一致 |
| `app_token` 和 `table_id` 搞混 | `app_token` 是多维表格级别，`table_id` 是数据表级别 |
| `/wiki/` URL 直接当 app_token 用 | Wiki URL 的 token 是 node_token，需先 `wiki_get_node()` 获取 `obj_token` |
| 写入只读字段 | 类型 19/20/1001-1004 为只读，不能通过 API 写入 |

## 所需权限

- `bitable:app` — 多维表格完整权限
- 或 `bitable:app:readonly` — 只读权限
