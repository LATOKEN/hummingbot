import asyncio
import unittest
import conf

from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.connector.exchange.latoken.latoken_user_stream_tracker import \
    LatokenUserStreamTracker


class LatokenUserStreamTrackerUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.latoken_auth = LatokenAuth(conf.latoken_api_key, conf.latoken_secret_key)
        cls.trading_pair = ["ETHUSDT"]
        cls.user_stream_tracker: LatokenUserStreamTracker = LatokenUserStreamTracker(
            latoken_auth=cls.latoken_auth, trading_pairs=cls.trading_pair)
        cls.user_stream_tracker_task: asyncio.Task = asyncio.ensure_future(
            cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        assert self.user_stream_tracker.user_stream.qsize() > 0
