# 考勤 (Attendance)

飞书考勤 API，查询员工打卡记录。

## API 函数

### get_user_employee_id

通过 open_id 获取 employee_id（考勤查询前置步骤）。

```python
from feishu_api import get_user_employee_id

eid = get_user_employee_id("ou_xxx")
# eid -> "6xxx" (employee_id 字符串)
```

### get_attendance

查询打卡结果。

```python
from feishu_api import get_attendance

data = get_attendance(
    user_ids=["6xxx"],        # employee_id 列表，最多 50 个
    date_from=20260301,       # yyyyMMdd 格式整数
    date_to=20260312,
)
# data["user_task_results"] -> [
#   {employee_name, day, records: [{check_in_result, check_out_result, ...}]}
# ]
```

**CLI**:
```bash
python3 scripts/feishu_api.py attendance query --user-ids 6xxx --date-from 20260301 --date-to 20260312
```

## 使用流程

1. 先用 `get_user_employee_id(open_id)` 获取 employee_id
2. 再用 `get_attendance([employee_id], date_from, date_to)` 查询打卡

## 打卡状态码

| 值 | 含义 |
|----|------|
| `Normal` | 正常 |
| `Late` | 迟到 |
| `Early` | 早退 |
| `Lack` | 缺卡 |
| `Todo` | 未打卡 |
| `NoNeedCheck` | 无需打卡 |

## 日期格式

考勤 API 的日期格式是 `yyyyMMdd` **整数**（不是字符串，不是时间戳）：

```python
# 正确
date_from=20260301

# 错误
date_from="2026-03-01"     # 不是字符串
date_from=1739059200        # 不是 Unix 时间戳
```

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 用 open_id 调考勤 API | 先用 `get_user_employee_id(open_id)` 转换为 employee_id |
| 日期格式传字符串或时间戳 | 必须是 yyyyMMdd 整数如 `20260209` |
| 一次查超过 50 人 | `user_ids` 最多 50 个，需分批 |
| 未申请 `contact:user.employee_id:readonly` | open_id 转 employee_id 必需此权限 |

## 所需权限

- `contact:user.employee_id:readonly` — 获取 employee_id
- `attendance:task` — 查询考勤打卡
