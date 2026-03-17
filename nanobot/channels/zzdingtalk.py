"""浙政钉 (Zhejiang Government DingTalk) channel — HTTP webhook mode.

Uses a lightweight uvicorn server to receive webhook callbacks from 浙政钉,
and HTTP REST API (with HMAC-SHA256 signing) to send messages back.

API domains:
  - SaaS / test:  https://openplatform.dg-work.cn
  - Production:   https://openplatform-pro.ding.zj.gov.cn
"""

import asyncio
import base64
import hashlib
import hmac as hmac_mod
import json
import random
import socket
import time
import uuid
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import Field

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import Base


def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _get_mac_address() -> str:
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return ":".join(mac[i : i + 2] for i in range(0, 12, 2))


class ZZDingTalkConfig(Base):
    """浙政钉 channel configuration."""

    enabled: bool = False
    domain: str = "https://openplatform.dg-work.cn"
    app_key: str = ""
    app_secret: str = ""
    tenant_id: str = ""
    sender_id: str = ""
    webhook_port: int = 9440
    webhook_path: str = "/zzdingtalk/webhook"
    webhook_integrated: bool = True  # True: use main gateway port; False: run own server on webhook_port
    allow_from: list[str] = Field(default_factory=list)


class ZZDingTalkApiClient:
    """Lightweight HTTP client implementing 浙政钉 HMAC-SHA256 signing protocol."""

    def __init__(self, domain: str, api_key: str, secret_key: str):
        self.domain = domain.rstrip("/")
        self.api_key = api_key
        self.secret_key = secret_key
        self._ip = _get_local_ip()
        self._mac = _get_mac_address()
        self._http: httpx.AsyncClient | None = None

    async def open(self) -> None:
        self._http = httpx.AsyncClient(timeout=30)

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    def _build_params_str(self, params: dict[str, Any]) -> str:
        pairs: list[str] = []
        for key in sorted(params.keys()):
            val = params[key]
            if isinstance(val, list):
                for v in val:
                    pairs.append(f"{key}={v}")
            else:
                pairs.append(f"{key}={val}")
        pairs.sort()
        return "&".join(pairs)

    def _sign(self, method: str, api_path: str, params: dict[str, Any]) -> dict[str, str]:
        timestamp = int(time.time()) + 28800
        format_time = time.strftime(
            "%Y-%m-%dT%H:%M:%S.000+08:00", time.gmtime(timestamp)
        )
        nonce = f"{timestamp}000{random.randint(1000, 9999)}"

        params_str = self._build_params_str(params) if params else ""
        if params_str:
            sign_data = f"{method}\n{format_time}\n{nonce}\n{api_path}\n{params_str}"
        else:
            sign_data = f"{method}\n{format_time}\n{nonce}\n{api_path}"

        signature = base64.b64encode(
            hmac_mod.new(
                self.secret_key.encode("utf-8"),
                sign_data.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        return {
            "X-Hmac-Auth-Timestamp": format_time,
            "X-Hmac-Auth-Version": "1.0",
            "X-Hmac-Auth-Nonce": nonce,
            "apiKey": self.api_key,
            "X-Hmac-Auth-Signature": signature,
            "X-Hmac-Auth-IP": self._ip,
            "X-Hmac-Auth-MAC": self._mac,
        }

    async def post(
        self, api_path: str, params: dict[str, Any] | None = None
    ) -> dict | None:
        if not self._http:
            return None
        params = params or {}
        headers = self._sign("POST", api_path, params)
        body = self._build_params_str(params)
        url = f"{self.domain}{api_path}"

        try:
            resp = await self._http.post(url, headers=headers, content=body)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("浙政钉 API POST {} error: {}", api_path, e)
            return None

    async def get(
        self, api_path: str, params: dict[str, Any] | None = None
    ) -> dict | None:
        if not self._http:
            return None
        params = params or {}
        headers = self._sign("GET", api_path, params)
        query = self._build_params_str(params)
        url = f"{self.domain}{api_path}"
        if query:
            url = f"{url}?{query}"

        try:
            resp = await self._http.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("浙政钉 API GET {} error: {}", api_path, e)
            return None


class ZZDingTalkChannel(BaseChannel):
    """浙政钉 channel using HTTP webhook for inbound + REST API for outbound."""

    name = "zzdingtalk"
    display_name = "浙政钉"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return ZZDingTalkConfig().model_dump(by_alias=True)

    def __init__(
        self,
        config: Any,
        bus: MessageBus,
        channel_manager: Any = None,
    ):
        if isinstance(config, dict):
            config = ZZDingTalkConfig.model_validate(config)
        super().__init__(config, bus)
        self.config: ZZDingTalkConfig = config
        self._channel_manager = channel_manager
        self._api: ZZDingTalkApiClient | None = None
        self._http: httpx.AsyncClient | None = None

        self._access_token: str | None = None
        self._token_expiry: float = 0

        self._server: uvicorn.Server | None = None
        self._background_tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        if not self.config.app_key or not self.config.app_secret:
            logger.error("浙政钉 app_key and app_secret not configured")
            return

        self._running = True
        self._api = ZZDingTalkApiClient(
            self.config.domain, self.config.app_key, self.config.app_secret
        )
        await self._api.open()
        self._http = httpx.AsyncClient(timeout=30)

        if self.config.webhook_integrated and self._channel_manager:
            web_enabled = self._channel_manager.get_channel("web") is not None
            if web_enabled:
                logger.info(
                    "浙政钉 webhook integrated with main gateway at path {}",
                    self.config.webhook_path,
                )
                return

        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        app.add_api_route(
            self.config.webhook_path, self._webhook_handler, methods=["POST"]
        )

        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=self.config.webhook_port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)

        logger.info(
            "浙政钉 webhook server starting on port {} path {}",
            self.config.webhook_port,
            self.config.webhook_path,
        )

        await self._server.serve()

    async def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.should_exit = True
            self._server = None
        if self._api:
            await self._api.close()
            self._api = None
        if self._http:
            await self._http.aclose()
            self._http = None
        for task in self._background_tasks:
            task.cancel()
        self._background_tasks.clear()
        logger.info("浙政钉 channel stopped")

    async def _webhook_handler(self, request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            logger.warning("浙政钉 webhook: invalid JSON body")
            return JSONResponse({"errmsg": "invalid body"}, status_code=400)

        logger.debug(
            "浙政钉 webhook received: {}",
            json.dumps(body, ensure_ascii=False)[:500],
        )

        msg_type = body.get("msgtype", "")
        content = ""
        if msg_type == "text":
            content = (body.get("text") or {}).get("content", "").strip()
        elif msg_type == "richText":
            for section in (body.get("richText") or {}).get("richTextList", []):
                if section.get("text"):
                    content += section["text"]
            content = content.strip()
        else:
            content = (body.get("text") or {}).get("content", "").strip()

        if not content:
            logger.debug("浙政钉 webhook: empty message, skipping")
            return JSONResponse({"errmsg": "ok"})

        sender_id = body.get("senderId") or body.get("senderStaffId") or ""
        sender_nick = body.get("senderNick") or body.get("senderCorpName") or "Unknown"
        conversation_id = body.get("conversationId") or ""
        conversation_type = str(body.get("conversationType", "1"))

        session_webhook = body.get("sessionWebhook") or ""
        session_webhook_expired = body.get("sessionWebhookExpiredTime", 0)

        logger.info(
            "浙政钉 inbound from {} ({}): {}",
            sender_nick,
            sender_id,
            content[:80],
        )

        is_group = conversation_type == "2" and conversation_id
        chat_id = f"group:{conversation_id}" if is_group else sender_id

        task = asyncio.create_task(
            self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                metadata={
                    "sender_name": sender_nick,
                    "platform": "zzdingtalk",
                    "conversation_type": conversation_type,
                    "session_webhook": session_webhook,
                    "session_webhook_expired_time": session_webhook_expired,
                    "conversation_id": conversation_id,
                },
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        return JSONResponse({"errmsg": "ok"})

    async def _get_access_token(self) -> str | None:
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        if not self._api:
            return None

        data = await self._api.post(
            "/gettoken.json",
            {"appkey": self.config.app_key, "appsecret": self.config.app_secret},
        )
        if not data:
            return None

        if not data.get("success"):
            logger.error("浙政钉 gettoken failed: {}", data)
            return None

        content = data.get("content", data)
        token_data = content.get("data", content)
        self._access_token = token_data.get("accessToken")
        expire_in = token_data.get("expiresIn") or token_data.get("expireIn", 7200)
        self._token_expiry = time.time() + int(expire_in) - 60
        logger.debug("浙政钉 access_token refreshed, expires in {}s", expire_in)
        return self._access_token

    async def send(self, msg: OutboundMessage) -> None:
        if not msg.content or not msg.content.strip():
            return

        session_webhook = (msg.metadata or {}).get("session_webhook")
        session_expired = (msg.metadata or {}).get("session_webhook_expired_time", 0)

        if session_webhook and session_expired and time.time() * 1000 < session_expired:
            ok = await self._send_via_session_webhook(
                session_webhook, msg.content.strip()
            )
            if ok:
                return

        await self._send_chat_msg(msg.chat_id, msg.content.strip())

    async def _send_via_session_webhook(self, webhook_url: str, content: str) -> bool:
        if not self._http:
            return False

        payload = {"msgtype": "text", "text": {"content": content}}
        try:
            resp = await self._http.post(webhook_url, json=payload)
            if resp.status_code != 200:
                logger.warning(
                    "浙政钉 session webhook failed status={}", resp.status_code
                )
                return False
            result = resp.json()
            if result.get("errcode", 0) != 0:
                logger.warning("浙政钉 session webhook error: {}", result)
                return False
            logger.debug("浙政钉 message sent via session webhook")
            return True
        except Exception as e:
            logger.warning("浙政钉 session webhook error: {}", e)
            return False

    async def _send_chat_msg(self, chat_id: str, content: str) -> bool:
        token = await self._get_access_token()
        if not token or not self._api:
            logger.error("浙政钉 cannot send: no access token or client")
            return False

        is_group = chat_id.startswith("group:")
        conversation_id = chat_id[6:] if is_group else chat_id

        msg_body = json.dumps(
            {"msgtype": "text", "text": {"content": content}}, ensure_ascii=False
        )

        params: dict[str, Any] = {
            "access_token": token,
            "msg": msg_body,
            "tenantId": self.config.tenant_id,
        }
        if self.config.sender_id:
            params["senderId"] = self.config.sender_id

        if is_group:
            params["chatType"] = "2"
            params["chatId"] = conversation_id
        else:
            params["chatType"] = "1"
            params["receiverId"] = conversation_id

        data = await self._api.post("/chat/sendMsg", params)

        if not data:
            logger.error("浙政钉 sendMsg failed: no response")
            return False
        if not data.get("success") and data.get("errcode", 0) != 0:
            logger.error("浙政钉 sendMsg error: {}", data)
            return False

        logger.debug("浙政钉 message sent to {}", chat_id)
        return True
