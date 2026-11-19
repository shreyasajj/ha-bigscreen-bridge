"""Small aiohttp protocol client, independent of Home Assistant internals."""

import asyncio
import contextlib
import re
import uuid
from urllib.parse import urlsplit

import aiohttp

COMMAND_TIMEOUT = 100


class BridgeClientError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code  # the bridge's machine-readable error code, when it sent one


class BridgeAuthError(BridgeClientError):
    pass


PAIRING_CODE = re.compile(r"[23456789ABCDEFGHJKMNPQRSTVWXYZ]{8}")


def pairing_code(value):
    """The 8-character code shown on the TV, or None when `value` is something else (a token)."""
    code = re.sub(r"[\s-]", "", value or "").upper()
    return code if PAIRING_CODE.fullmatch(code) else None


async def pair(session, url, code, name="Home Assistant"):
    """Exchange the code shown on the TV for this client's own token."""
    url = validate_url(url)
    async with asyncio.timeout(10):
        async with session.post(url + "/pair", json={"code": code, "name": name}) as response:
            try:
                body = await response.json(content_type=None)
            except ValueError as exc:
                raise BridgeClientError("Unexpected pairing reply") from exc
    if response.status == 200 and isinstance(body, dict) and isinstance(body.get("token"), str):
        return body
    error = (body.get("error") or {}) if isinstance(body, dict) else {}
    if response.status in (403, 429):
        raise BridgeAuthError(error.get("message") or "Pairing was refused", error.get("code"))
    raise BridgeClientError(error.get("message") or "Pairing failed", error.get("code"))


def validate_url(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("Use an http(s) bridge address without credentials, path, or query")
    _ = parsed.port  # validate malformed/out-of-range ports
    return value.rstrip("/")


class BridgeClient:
    def __init__(self, session, url, token, on_state=None, on_disconnect=None):
        self.session = session
        self.url = validate_url(url)
        self.token = token
        self.on_state = on_state
        self.on_disconnect = on_disconnect
        self.state = None
        self.ws = None
        self.reader = None
        self.pending = {}

    async def connect(self):
        try:
            async with asyncio.timeout(10):
                self.ws = await self.session.ws_connect(
                    self.url + "/ws",
                    headers={"Authorization": "Bearer " + self.token},
                    heartbeat=20,
                    max_msg_size=1024 * 1024,
                    timeout=aiohttp.ClientWSTimeout(ws_close=5),
                )
        except aiohttp.WSServerHandshakeError as exc:
            if exc.status == 401:
                raise BridgeAuthError("Bridge rejected the token") from exc
            raise BridgeClientError("Bridge handshake failed") from exc
        try:
            initial = await asyncio.wait_for(self.ws.receive_json(), 10)
            if (
                not isinstance(initial, dict)
                or initial.get("type") != "state"
                or initial.get("protocol") != 1
                or not isinstance(initial.get("device_id"), str)
                or not isinstance(initial.get("apps"), list)
            ):
                raise BridgeClientError("Unsupported bridge protocol")
            self.state = initial
        except BaseException:
            await self.ws.close()
            raise
        self.reader = asyncio.create_task(self._read())
        return self.state

    async def _read(self):
        try:
            async for msg in self.ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    break
                data = msg.json()
                if not isinstance(data, dict):
                    raise ValueError("Expected a protocol object")
                if data.get("type") == "state":
                    self.state = data
                    if self.on_state:
                        self.on_state(data)
                elif data.get("type") == "result":
                    future = self.pending.get(data.get("id"))
                    if future and not future.done():
                        future.set_result(data)
        except (ValueError, TypeError, KeyError, aiohttp.ClientError, ConnectionError):
            # Treat malformed protocol data as a lost connection so HA reconnects.
            pass
        finally:
            await self.ws.close()
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(BridgeClientError("Bridge disconnected"))
            if self.on_disconnect:
                self.on_disconnect()

    async def command(self, command, **kwargs):
        if not self.ws or self.ws.closed:
            raise BridgeClientError("Bridge is disconnected")
        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        try:
            await self.ws.send_json({"id": request_id, "command": command, **kwargs})
            # A cold launch waits for a window, then readiness, then the navigation itself.
            response = await asyncio.wait_for(future, COMMAND_TIMEOUT)
            if not response["ok"]:
                raise BridgeClientError(response["error"]["message"], response["error"].get("code"))
            return response["result"]
        finally:
            self.pending.pop(request_id, None)

    async def close(self):
        self.on_disconnect = None
        if self.ws:
            await self.ws.close()
        if self.reader:
            self.reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.reader
