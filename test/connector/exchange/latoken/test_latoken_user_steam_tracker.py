import asyncio
import unittest
import conf

from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.connector.exchange.latoken.latoken_user_stream_tracker import \
    LatokenUserStreamTracker
from hummingbot.connector.time_synchronizer import TimeSynchronizer
domain = "tech"


class LatokenUserStreamTrackerUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        ts = TimeSynchronizer()
        cls.latoken_auth = LatokenAuth(conf.latoken_api_key, conf.latoken_secret_key, ts)
        cls.trading_pair = ["ETH-USDT"]
        cls.user_stream_tracker: LatokenUserStreamTracker = LatokenUserStreamTracker(
            auth=cls.latoken_auth, data_source=None, domain=domain)
        cls.user_stream_tracker_task: asyncio.Task = asyncio.ensure_future(
            cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        assert self.user_stream_tracker.user_stream.qsize() > 0
