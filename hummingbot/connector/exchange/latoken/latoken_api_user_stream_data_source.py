import asyncio
import logging

# import json
import time

from typing import (
    Dict,
    Optional,
    # Tuple,
)

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
from hummingbot.connector.exchange.latoken import latoken_utils
from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.connector.utils import build_api_factory
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod,
    RESTRequest,
    RESTResponse,
    # WSRequest,
)
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger
# import websocket
# import stomper


class LatokenAPIUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0

    _bausds_logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: LatokenAuth,
                 domain: str = CONSTANTS.DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None):
        super().__init__()
        self._auth: LatokenAuth = auth
        self._current_listen_key = None
        self._last_recv_time: float = 0
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()
        self._api_factory = api_factory or build_api_factory()
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None

        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bausds_logger is None:
            cls._bausds_logger = logging.getLogger(__name__)
        return cls._bausds_logger

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message
        :return: the timestamp of the last received message in seconds
        """
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return -1

    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue
        """
        ws = None
        while True:
            try:
                self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
                await self._listen_key_initialized_event.wait()
                # path_params = {'user': str(self._current_listen_key)}
                # account_path = CONSTANTS.ACCOUNT_STREAM.format(**path_params)

                client: WSAssistant = await self._get_ws_assistant()
                await client.connect(
                    ws_url=f"{CONSTANTS.WSS_URL.format(self._domain)}",
                    ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                # TODO review to integrate websocket.create_connection from python client application to hbot framework
                # ws = websocket.create_connection(CONSTANTS.WSS_URL.format(self._domain))

                # msg_out = stomper.Frame()
                # msg_out.cmd = "CONNECT"
                # msg_out.headers.update({
                #     "accept-version": "1.1",
                #     "heart-beat": "0,0"
                # })

                # auth_header = await self._auth.stomp_authenticate()
                # msg_out.headers.update(auth_header)

                # ws.send(msg_out.pack())
                # ws.recv()
                # subscribe_id_account = 0
                # msg_subscribe = stomper.subscribe(account_path, subscribe_id_account)
                # ws.send(msg_subscribe)

                #
                # # async def pop_task():
                # #     while True:
                # #         message = ws.recv()
                # #         message_unpacked = stomper.unpack_frame(message.decode())
                # #         output.put_nowait(message_unpacked)
                # # # task = asyncio.Task(pop_task())
                # # await pop_task()
                # # while True:
                # msg_in = ws.recv()
                # msg_in_unpacked = stomper.unpack_frame(msg_in.decode())
                # if msg_in_unpacked['cmd'] == "MESSAGE":
                #     body = json.loads(msg_in_unpacked["body"])
                #     # I think body["nonce"] has subscrition id
                #     if body["nonce"] == subscribe_id_account:
                #         output.put_nowait(body["payload"])

                async for ws_response in client.iter_messages():
                    data = ws_response.data
                    if len(data) > 0:
                        output.put_nowait(data)

                # while True:
                #     self.logger().warning("listen_for_user_stream::LatokenAPIUserStreamDataSource websocket needs to be implemented")
                #     await self._sleep(5)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
            finally:
                # Make sure no background task is leaked.
                # client and await client.disconnect()
                ws and ws.abort()
                self._manage_listen_key_task and self._manage_listen_key_task.cancel()
                self._current_listen_key = None
                self._listen_key_initialized_event.clear()
                await self._sleep(5)

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    async def _get_listen_key(self):
        url = latoken_utils.private_rest_url(path_url=CONSTANTS.LATOKEN_USER_STREAM_PATH_URL, domain=self._domain)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        request = RESTRequest(method=RESTMethod.GET, url=url, headers=headers, is_auth_required=True)
        client = await self._get_rest_assistant()
        # async with self._throttler.execute_task(limit_id=CONSTANTS.LATOKEN_USER_STREAM_PATH_URL):
        async with self._throttler.execute_task(limit_id=CONSTANTS.GLOBAL_RATE_LIMIT):
            response: RESTResponse = await client.call(request)

            if response.status != 200:
                raise IOError(f"Error fetching user stream listen key. Response: {response}")
            data: Dict[str, str] = await response.json()
            return data["id"]

    async def _ping_listen_key(self) -> bool:  # possibly can be skipped
        url = latoken_utils.private_rest_url(path_url=CONSTANTS.LATOKEN_USER_STREAM_PATH_URL, domain=self._domain)
        request = RESTRequest(method=RESTMethod.GET, url=url, is_auth_required=True)
        rest_assistant = await self._get_rest_assistant()
        async with self._throttler.execute_task(limit_id=CONSTANTS.LATOKEN_USER_STREAM_PATH_URL):
            response: RESTResponse = await rest_assistant.call(request=request)

            data: Dict[str, str] = await response.json()
            if "id" not in data:
                self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {data}")
                return False
            return True

    async def _manage_listen_key_task_loop(self):
        try:
            while True:
                now = int(time.time())
                if self._current_listen_key is None:
                    self._current_listen_key = await self._get_listen_key()
                    self.logger().info(f"Successfully obtained listen key {self._current_listen_key}")
                    self._listen_key_initialized_event.set()
                    self._last_listen_key_ping_ts = int(time.time())

                if now - self._last_listen_key_ping_ts >= self.LISTEN_KEY_KEEP_ALIVE_INTERVAL:
                    success: bool = await self._ping_listen_key()
                    if success:
                        self.logger().info(f"Refreshed listen key {self._current_listen_key}.")
                        self._last_listen_key_ping_ts = int(time.time())
                    else:
                        self.logger().error("Error occurred renewing listen key ...")
                        break
                else:
                    await self._sleep(self.LISTEN_KEY_KEEP_ALIVE_INTERVAL)
        finally:
            self._current_listen_key = None
            self._listen_key_initialized_event.clear()

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
