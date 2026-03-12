# 审批 (Approval)

飞书审批 API，管理审批定义、审批实例，以及请假审批便捷函数。

## 预置常量

### 默认请假审批编码

```
DEFAULT_APPROVAL_CODE = "E565EC28-57C7-461C-B7ED-1E2D838F4878"
```

### 假期类型映射

| 名称 | leave_id |
|------|----------|
| 年假 | 7138673249737506817 |
| 事假 | 7138673250187935772 |
| 病假 | 7138673250640347138 |
| 调休假 | 7138673251139731484 |
| 婚假 | 7138673251697475612 |
| 产假 | 7138673252143726594 |
| 陪产假 | 7138673252595236865 |
| 丧假 | 7138673253106663426 |
| 哺乳假 | 7138673253534695425 |

`create_leave_approval` 的 `leave_type` 参数可直接传中文名称（如 `"年假"`），会自动映射为 leave_id。

## API 函数

### approval_get_definition

获取审批定义详情（含表单结构）。

```python
from feishu_api import approval_get_definition

data = approval_get_definition("E565EC28-57C7-461C-B7ED-1E2D838F4878")
# data -> {approval_name, form, node_list, ...}
```

**CLI**:
```bash
python3 scripts/feishu_api.py approval definition --code E565EC28-57C7-461C-B7ED-1E2D838F4878
```

### approval_list_instances

批量获取审批实例 ID。默认查询最近 30 天。

```python
from feishu_api import approval_list_instances

data = approval_list_instances(
    approval_code="E565EC28-...",
    start_time="1710000000000",   # 毫秒时间戳（可选）
    end_time="1710086400000",     # 毫秒时间戳（可选）
    page_size=100,
    user_id="ou_xxx",             # 筛选特定用户（可选）
)
# data["instance_code_list"] -> ["xxx", ...]
```

**CLI**:
```bash
python3 scripts/feishu_api.py approval list --code E565EC28-... --limit 20
```

### approval_get_instance

获取审批实例详情。

```python
from feishu_api import approval_get_instance

data = approval_get_instance("xxx-instance-code")
# data -> {approval_code, approval_name, open_id, status, form, timeline, ...}
```

**CLI**:
```bash
python3 scripts/feishu_api.py approval get --instance-code xxx
```

### approval_create_instance

创建审批实例。

```python
from feishu_api import approval_create_instance
import json

form = json.dumps([...])  # 表单内容，结构取决于审批定义
data = approval_create_instance("E565EC28-...", "ou_xxx", form)
# data -> {instance_code}
```

**CLI**:
```bash
python3 scripts/feishu_api.py approval create --code ... --user-id ou_xxx --form '[...]'
```

### approval_cancel_instance

撤回审批实例。

```python
from feishu_api import approval_cancel_instance

data = approval_cancel_instance("E565EC28-...", "instance_code", "ou_xxx", reason="取消")
```

### approval_approve_task / approval_reject_task

审批同意或拒绝。

```python
from feishu_api import approval_approve_task, approval_reject_task

approval_approve_task("E565EC28-...", "instance_code", "task_id", "ou_xxx", comment="同意")
approval_reject_task("E565EC28-...", "instance_code", "task_id", "ou_xxx", comment="不同意")
```

### approval_list_comments

获取审批评论。

```python
from feishu_api import approval_list_comments

data = approval_list_comments("instance_id")
# data["comment_list"] -> [{id, content, create_time, ...}]
```

### create_leave_approval

请假审批便捷函数。

```python
from feishu_api import create_leave_approval

data = create_leave_approval(
    approval_code="E565EC28-...",
    user_id="ou_xxx",
    leave_type="年假",            # 或直接传 leave_id
    start_time="2026-03-15",
    end_time="2026-03-16",
    reason="个人事务",
    unit="DAY",                   # DAY / HOUR / HALF_DAY
)
```

### approval_transfer_task

审批转交。

```python
from feishu_api import approval_transfer_task

approval_transfer_task("E565EC28-...", "instance_code", "task_id", "ou_xxx",
                       transfer_user_id="ou_yyy", comment="转交给主管")
```

## 如何获取 approval_code

飞书不提供「列出所有审批定义」的 API，需从管理后台获取：

1. 打开 [飞书审批管理后台（开发者模式）](https://www.feishu.cn/approval/admin/approvalList?devMode=on)
2. 找到目标审批 → 点击 **编辑**
3. 从浏览器地址栏复制 `definitionCode=` 后面的值

## 常见表单控件类型

| 控件类型 | 说明 | value 格式 |
|----------|------|------------|
| `input` | 单行文本 | `"文本内容"` |
| `textarea` | 多行文本 | `"文本内容"` |
| `number` | 数字 | `123.45` |
| `date` | 日期 | `"2026-03-01T09:00:00+08:00"` (RFC3339) |
| `leaveGroup` | 请假控件组 | `{"name":"年假","start":"...","end":"...","interval":2.0}` |
| `radioV2` | 单选 | `"选项名称"` |
| `checkboxV2` | 多选 | `["选项1","选项2"]` |

## 典型工作流

### 处理审批（审批人视角）

1. `approval_list_instances(code)` → 获取实例列表
2. `approval_get_instance(instance_code)` → 查看详情，从 `task_list` 中找到待办的 `task_id`
3. `approval_approve_task()` 同意 / `approval_reject_task()` 拒绝 / `approval_transfer_task()` 转交

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 想用 API 列出所有审批定义 | 无此 API，从管理后台获取 approval_code |
| form 传对象而非 JSON 字符串 | `form` 参数需要 `json.dumps([...])` |
| 忘记传 `task_id` 执行同意/拒绝 | 先通过 `approval_get_instance` 获取 task_id |
| 撤回失败 | 检查审批定义是否允许撤回 |
| 请假日期格式错误 | 必须用 RFC3339 格式 `"2026-03-01T00:00:00+08:00"` |

## 所需权限

- `approval:approval` — 审批完整权限
- `approval:approval:readonly` — 只读权限
- `approval:task` — 审批人操作（同意/拒绝/转交）
