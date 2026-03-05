# -*- coding: utf-8 -*-
"""
配置文件
"""

import os

# 欢迎冷却时间（分钟）
WELCOME_COOLDOWN_MINUTES = 60

# 每批最多@人数
BATCH_SIZE = 20

# 夜间模式（不发送欢迎消息）
NIGHT_MODE_START = 23  # 23:00
NIGHT_MODE_END = 7     # 07:00

APP_ID = os.getenv("NANOBOT_CHANNELS__FEISHU__APP_ID")
APP_SECRET = os.getenv("NANOBOT_CHANNELS__FEISHU__APP_SECRET")
