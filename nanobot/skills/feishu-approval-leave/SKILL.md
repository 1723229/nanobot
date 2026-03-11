---
name: feishu-approval-leave
description: 通过飞书审批 API v4 创建请假审批实例。当用户需要提交请假申请、创建飞书请假审批、调用飞书审批接口时使用此技能。支持年假、事假、病假、调休假、婚假、产假、陪产假、丧假、哺乳假等假期类型。
---

# 飞书请假审批

通过飞书审批 API v4 创建请假审批实例。

## 配置

通过系统环境变量配置飞书应用凭据（与其他飞书 skill 共用）：

```bash
export NANOBOT_CHANNELS__FEISHU__APP_ID=cli_xxx
export NANOBOT_CHANNELS__FEISHU__APP_SECRET=xxx
```

## 审批模板编码

请假审批使用固定的模板编码，**无需向用户询问**：

```
approval_code = "E565EC28-57C7-461C-B7ED-1E2D838F4878"
```

此编码对应组织内的「请假」审批流程，所有请假类型（年假、事假、病假等）共用同一个模板。

## 前置条件

- 环境变量已配置飞书 App ID / App Secret
- 已知申请人的 open_id（飞书用户唯一标识，格式如 `ou_xxxxxxxxxxxx`）

## 使用方式

运行 `scripts/feishu_approval_leave.py`，支持 Python API 调用和命令行两种方式。

### Python API

```python
from feishu_approval_leave import create_leave_approval

APPROVAL_CODE = "E565EC28-57C7-461C-B7ED-1E2D838F4878"  # 固定值，无需修改

result = create_leave_approval(
    approval_code=APPROVAL_CODE,
    user_id="ou_xxxxxxxxxxxx",  # 申请人的 open_id
    leave_type="年假",            # 支持中文名称或 leave_id
    start_time="2026-03-11T09:00:00+08:00",  # RFC3339 格式
    end_time="2026-03-11T18:00:00+08:00",
    reason="请假事由",
    unit="DAY"                   # DAY / HOUR / HALF_DAY
)
```

### 命令行

```bash
python scripts/feishu_approval_leave.py \
  --user-id ou_xxxxxxxxxxxx \
  --leave-type 年假 \
  --start-time "2026-03-11T09:00:00+08:00" \
  --end-time "2026-03-11T18:00:00+08:00" \
  --reason "请假事由"
```

## 关键注意事项

1. **form 必须是 JSON 字符串数组**，使用 `json.dumps(form_array)` 序列化，不是直接传对象
2. **时间格式必须为 RFC3339**，如 `2026-03-11T09:00:00+08:00`（不能用 `2026-03-11 09:00:00`）
3. 使用 `tenant_access_token`，不需要 `user_access_token`
4. 限额假期类型会检查余额，不足时创建失败

## 参考资料

- 假期类型列表、完整参数说明、错误码：见 [references/api-guide.md](references/api-guide.md)
- 飞书官方文档：https://open.feishu.cn/document/server-docs/approval-v4/instance/create
