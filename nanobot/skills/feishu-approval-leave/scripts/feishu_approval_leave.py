#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feishu-approval-leave - 飞书请假审批创建工具

调用飞书审批 API v4 创建请假审批实例。
凭据通过环境变量获取（与其他飞书 skill 共用）：
  NANOBOT_CHANNELS__FEISHU__APP_ID
  NANOBOT_CHANNELS__FEISHU__APP_SECRET
"""

import os
import requests
import json
import argparse
from typing import Dict, Any, Optional

BASE_URL = "https://open.feishu.cn/open-apis"
DEFAULT_APPROVAL_CODE = "E565EC28-57C7-461C-B7ED-1E2D838F4878"

LEAVE_TYPES = {
    "年假": "7138673249737506817",
    "事假": "7138673250187935772",
    "病假": "7138673250640347138",
    "调休假": "7138673251139731484",
    "婚假": "7138673251697475612",
    "产假": "7138673252143726594",
    "陪产假": "7138673252595236865",
    "丧假": "7138673253106663426",
    "哺乳假": "7138673253534695425",
}


def load_config() -> Dict[str, str]:
    """从环境变量加载飞书凭据"""
    app_id = os.environ.get("NANOBOT_CHANNELS__FEISHU__APP_ID", "")
    app_secret = os.environ.get("NANOBOT_CHANNELS__FEISHU__APP_SECRET", "")
    if not app_id or not app_secret:
        raise Exception(
            "缺少飞书凭据，请设置环境变量 "
            "NANOBOT_CHANNELS__FEISHU__APP_ID / NANOBOT_CHANNELS__FEISHU__APP_SECRET"
        )
    return {"app_id": app_id, "app_secret": app_secret}


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """获取 tenant_access_token"""
    url = f"{BASE_URL}/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"获取 token 失败：{result}")
    return result["tenant_access_token"]


def create_leave_approval(
    approval_code: str,
    user_id: str,
    leave_type: str,
    start_time: str,
    end_time: str,
    reason: str,
    unit: str = "DAY",
    interval: str = "1",
) -> Dict[str, Any]:
    """
    创建请假审批实例

    Args:
        approval_code: 审批模板码
        user_id: 申请人的 open_id
        leave_type: 假期类型名称（如"年假"）或 leave_id
        start_time: 开始时间 (RFC3339)
        end_time: 结束时间 (RFC3339)
        reason: 请假事由
        unit: 时长单位 (DAY / HOUR / HALF_DAY)
        interval: 时长计算方式

    Returns:
        {"success": bool, "instance_code": str, "instance_id": str, "error": str}
    """
    config = load_config()
    token = get_tenant_access_token(config["app_id"], config["app_secret"])

    leave_id = LEAVE_TYPES.get(leave_type, leave_type)

    form_array = [
        {
            "id": "widgetLeaveGroupV2",
            "type": "leaveGroupV2",
            "value": [
                {"id": "widgetLeaveGroupType", "type": "radioV2", "value": leave_id},
                {"id": "widgetLeaveGroupStartTime", "type": "date", "value": start_time},
                {"id": "widgetLeaveGroupEndTime", "type": "date", "value": end_time},
                {"id": "widgetLeaveGroupInterval", "type": "radioV2", "value": interval},
                {"id": "widgetLeaveGroupReason", "type": "textarea", "value": reason},
                {"id": "widgetLeaveGroupUnit", "type": "radioV2", "value": unit},
            ],
        }
    ]

    payload = {
        "approval_code": approval_code,
        "open_id": user_id,
        "form": json.dumps(form_array, ensure_ascii=False),
    }

    url = f"{BASE_URL}/approval/v4/instances"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        result = resp.json()

        if result.get("code") == 0:
            data = result.get("data", {})
            return {
                "success": True,
                "instance_code": data.get("instance_code", "N/A"),
                "instance_id": data.get("instance_id", "N/A"),
                "data": data,
            }
        else:
            return {
                "success": False,
                "error": f"{result.get('code')}: {result.get('msg', 'Unknown error')}",
                "data": result.get("data"),
            }
    except Exception as e:
        return {"success": False, "error": f"请求异常：{e}"}


def main():
    parser = argparse.ArgumentParser(
        description="飞书请假审批创建工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
凭据通过环境变量获取（与其他飞书 skill 共用）：
  NANOBOT_CHANNELS__FEISHU__APP_ID
  NANOBOT_CHANNELS__FEISHU__APP_SECRET

示例:
  python feishu_approval_leave.py \\
    --user-id ou_xxxxxxxxxxxx \\
    --leave-type 年假 \\
    --start-time "2026-03-11T09:00:00+08:00" \\
    --end-time "2026-03-11T18:00:00+08:00" \\
    --reason "API 测试"
        """,
    )

    parser.add_argument("--approval-code", default=DEFAULT_APPROVAL_CODE, help=f"审批模板码 (默认：{DEFAULT_APPROVAL_CODE})")
    parser.add_argument("--user-id", required=True, help="申请人的 open_id")
    parser.add_argument(
        "--leave-type", required=True, help="假期类型 (如：年假、事假、病假)"
    )
    parser.add_argument(
        "--start-time",
        required=True,
        help="开始时间 (RFC3339 格式，如：2026-03-11T09:00:00+08:00)",
    )
    parser.add_argument("--end-time", required=True, help="结束时间 (RFC3339 格式)")
    parser.add_argument("--reason", required=True, help="请假事由")
    parser.add_argument(
        "--unit",
        default="DAY",
        choices=["DAY", "HOUR", "HALF_DAY"],
        help="时长单位 (默认：DAY)",
    )
    parser.add_argument("--interval", default="1", help="时长计算方式 (默认：1)")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细输出")

    args = parser.parse_args()

    if args.verbose:
        print("=" * 70)
        print("飞书请假审批创建")
        print("=" * 70)
        print(f"  审批模板：{args.approval_code}")
        print(f"  open_id: {args.user_id}")
        print(f"  假期类型：{args.leave_type}")
        print(f"  时间：{args.start_time} - {args.end_time}")
        print(f"  事由：{args.reason}")
        print()

    result = create_leave_approval(
        approval_code=args.approval_code,
        user_id=args.user_id,
        leave_type=args.leave_type,
        start_time=args.start_time,
        end_time=args.end_time,
        reason=args.reason,
        unit=args.unit,
        interval=args.interval,
    )

    if result["success"]:
        print(f"✅ 审批实例创建成功")
        print(f"   实例码：{result['instance_code']}")
        print(f"   实例 ID: {result['instance_id']}")
        return 0
    else:
        print(f"❌ 创建失败")
        print(f"   错误：{result['error']}")
        if result.get("data"):
            print(f"   详情：{result['data']}")
        return 1


if __name__ == "__main__":
    exit(main())
