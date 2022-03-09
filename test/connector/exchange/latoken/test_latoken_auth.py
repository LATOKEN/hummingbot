import asyncio
import json
import unittest
from typing import List

import websockets

import conf
from hummingbot.connector.exchange.latoken import LATOKEN_WS_AUTH_URI
from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from unittest.mock import MagicMock


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.latoken_api_key
        secret_key = conf.latoken_secret_key
        now = 1234567890.000
        mock_time_provider = MagicMock()  # possibly not useful  for latoken rest
        mock_time_provider.time.return_value = now
        cls.auth = LatokenAuth(api_key, secret_key, mock_time_provider)

    async def con_auth(self):
        async with websockets.connect(LATOKEN_WS_AUTH_URI) as ws:
            ws: websockets.WebSocketClientProtocol = ws
            # unfinished continue with the stomper or follow websocketclientprotocol
            # and take from ws_authenticate headers
            payload = self.auth.generate_auth_payload('AUTH{nonce}'.format(nonce=self.auth.get_nonce()))

            await ws.send(json.dumps(payload))
            msg = await asyncio.wait_for(ws.recv(), timeout=30)  # response
            return msg

    def test_auth(self):
        result: List[str] = self.ev_loop.run_until_complete(self.con_auth())
        assert "serverId" in result
