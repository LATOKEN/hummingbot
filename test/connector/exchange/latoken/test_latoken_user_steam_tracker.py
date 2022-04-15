import asyncio
import unittest
import conf
import ujson
import logging
from hummingbot.connector.exchange.latoken import latoken_constants as CONSTANTS
from typing import Dict
from typing import AsyncIterable
from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.connector.exchange.latoken.latoken_user_stream_tracker import \
    LatokenUserStreamTracker
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.connector.exchange.latoken.latoken_api_user_stream_data_source import LatokenAPIUserStreamDataSource
domain = "tech"


class LatokenUserStreamTrackerUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        ts = TimeSynchronizer()
        auth = LatokenAuth(conf.latoken_api_key, conf.latoken_secret_key, ts)
        cls.trading_pair = ["ETH-USDT"]
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        api_factory = WebAssistantsFactory(auth=auth)
        data_source = LatokenAPIUserStreamDataSource(
            auth=auth, domain=domain, api_factory=api_factory, throttler=throttler)
        cls.user_stream_tracker: LatokenUserStreamTracker = LatokenUserStreamTracker(
            auth=auth, data_source=data_source, domain=domain)
        cls.user_stream_tracker_task: asyncio.Task = asyncio.ensure_future(
            cls.user_stream_tracker.start())

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self.user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        user_account_data = []
        async for event_message in self._iter_user_event_queue():
            try:
                cmd = event_message.get('cmd', None)
                if cmd and cmd == 'MESSAGE':
                    subscription_id = int(event_message['headers']['subscription'])
                    body = ujson.loads(event_message["body"])
                    if subscription_id == CONSTANTS.SUBSCRIPTION_ID_ACCOUNT:
                        user_account_data.append(body["payload"])
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5.0)
        return user_account_data

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(self._user_stream_event_listener())
        assert self.user_stream_tracker.user_stream.qsize() > 0


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
