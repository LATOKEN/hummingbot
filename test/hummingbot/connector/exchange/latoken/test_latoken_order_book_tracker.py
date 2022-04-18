import asyncio
import time
import unittest

from collections import deque
from typing import (
    Deque,
    Optional,
    Union,
)

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
from hummingbot.connector.exchange.latoken.latoken_order_book import LatokenOrderBook
from hummingbot.connector.exchange.latoken.latoken_order_book_tracker import LatokenOrderBookTracker
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class LatokenOrderBookTrackerUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "d8ae67f2-f954-4014-98c8-64b1ac334c64"
        cls.quote_asset = "0c3a106d-bde3-4c13-a26e-3fd2394529e5"
        cls.trading_pair = "ETH-USDT"
        cls.domain = "tech"

        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.tracker: LatokenOrderBookTracker = LatokenOrderBookTracker(trading_pairs=[self.trading_pair],
                                                                        throttler=self.throttler)
        self.tracking_task: Optional[asyncio.Task] = None

        # Simulate start()
        self.tracker._order_books[self.trading_pair] = LatokenOrderBook()
        self.tracker._tracking_message_queues[self.trading_pair] = asyncio.Queue()
        self.tracker._past_diffs_windows[self.trading_pair] = deque()
        self.tracker._order_books_initialized.set()

    def tearDown(self) -> None:
        self.tracking_task and self.tracking_task.cancel()
        super().tearDown()

    def _simulate_message_enqueue(self, message_queue: Union[asyncio.Queue, Deque], msg: OrderBookMessage):
        if isinstance(message_queue, asyncio.Queue):
            self.ev_loop.run_until_complete(message_queue.put(msg))
        elif isinstance(message_queue, Deque):
            message_queue.append(msg)
        else:
            raise NotImplementedError

    def test_exchange_name(self):
        self.assertEqual("latoken", self.tracker.exchange_name)

        us_tracker = LatokenOrderBookTracker(trading_pairs=[self.trading_pair],
                                             domain=self.domain,
                                             throttler=self.throttler)

        self.assertEqual(f"latoken_{self.domain}", us_tracker.exchange_name)

    def test_order_book_diff_router_trading_pair_not_found_append_to_saved_message_queue(self):
        expected_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "update_id": 1,
                "trading_pair": self.trading_pair,
            }
        )

        self._simulate_message_enqueue(self.tracker._order_book_diff_stream, expected_msg)

        self.tracker._tracking_message_queues.clear()

        task = self.ev_loop.create_task(
            self.tracker._order_book_diff_router()
        )
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertEqual(0, len(self.tracker._tracking_message_queues))
        self.assertEqual(1, len(self.tracker._saved_message_queues[self.trading_pair]))
        task.cancel()

    def test_order_book_diff_router_snapshot_uid_above_diff_message_update_id(self):
        expected_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "update_id": 1,
                "trading_pair": self.trading_pair,
            }
        )

        self._simulate_message_enqueue(self.tracker._order_book_diff_stream, expected_msg)

        task = self.ev_loop.create_task(
            self.tracker._order_book_diff_router()
        )
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertEqual(1, self.tracker._tracking_message_queues[self.trading_pair].qsize())
        task.cancel()

    def test_order_book_diff_router_snapshot_uid_below_diff_message_update_id(self):
        # Updates the snapshot_uid
        self.tracker.order_books[self.trading_pair].apply_snapshot([], [], 2)
        expected_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "update_id": 1,
                "trading_pair": self.trading_pair,
            }
        )

        self._simulate_message_enqueue(self.tracker._order_book_diff_stream, expected_msg)

        task = self.ev_loop.create_task(
            self.tracker._order_book_diff_router()
        )
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertEqual(0, self.tracker._tracking_message_queues[self.trading_pair].qsize())
        task.cancel()

    def test_track_single_book_snapshot_message_no_past_diffs(self):
        time_ns = time.time_ns()
        snapshot_msg: OrderBookMessage = LatokenOrderBook.snapshot_message_from_exchange(
            msg={"ask": [{"price": "6.00", "quantity": "1.000", "cost": "6.00", "accumulated": "6.00"}],
                 "bid": [{"price": "50.50", "quantity": "-0.122", "cost": "-6.161", "accumulated": "-6.161"},
                         {"price": "5.00", "quantity": "1.000", "cost": "5.00", "accumulated": "-1.161"}],
                 "totalAsk": "6", "totalBid": "-1.161"},
            timestamp=time_ns
        )
        self._simulate_message_enqueue(self.tracker._tracking_message_queues[self.trading_pair], snapshot_msg)

        self.tracking_task = self.ev_loop.create_task(
            self.tracker._track_single_book(self.trading_pair)
        )
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.assertGreater(self.tracker.order_books[self.trading_pair].snapshot_uid, 1)

    def test_track_single_book_snapshot_message_with_past_diffs(self):
        time_ns = time.time_ns()
        time_ms_latoken = time_ns * 1e-6
        snapshot_msg: OrderBookMessage = LatokenOrderBook.snapshot_message_from_exchange(
            msg={"ask": [{"price": "6.00", "quantity": "1.000", "cost": "6.00", "accumulated": "6.00"}],
                 "bid": [{"price": "50.50", "quantity": "-0.122", "cost": "-6.161", "accumulated": "-6.161"},
                         {"price": "5.00", "quantity": "1.000", "cost": "5.00", "accumulated": "-1.161"}],
                 "totalAsk": "6", "totalBid": "-1.161"},
            timestamp=time_ns
        )

        past_diff_msg: OrderBookMessage = LatokenOrderBook.diff_message_from_exchange(
            msg={
                "ask": [],
                "bid": [
                    {
                        "price": "54464.69",
                        "quantityChange": "-0.07972",
                        "costChange": "-4341.9250868",
                        "quantity": "0.00000",
                        "cost": "0.00"
                    },
                    {
                        "price": "54442.80",
                        "quantityChange": "0.08927",
                        "costChange": "4860.108756",
                        "quantity": "0.08927",
                        "cost": "4860.108756"
                    }
                ],
                "timestamp": time_ms_latoken
            },
            timestamp=time_ns,
            metadata={"trading_pair": self.trading_pair}
        )

        self.tracking_task = self.ev_loop.create_task(
            self.tracker._track_single_book(self.trading_pair)
        )

        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self._simulate_message_enqueue(self.tracker._past_diffs_windows[self.trading_pair], past_diff_msg)
        self._simulate_message_enqueue(self.tracker._tracking_message_queues[self.trading_pair], snapshot_msg)

        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertGreater(self.tracker.order_books[self.trading_pair].snapshot_uid, 1)
        self.assertGreater(self.tracker.order_books[self.trading_pair].last_diff_uid, 1)

    def test_track_single_book_diff_message(self):
        time_ns = time.time_ns()
        time_ms_latoken = time_ns * 1e-6
        diff_msg: OrderBookMessage = LatokenOrderBook.diff_message_from_exchange(
            msg={
                "ask": [],
                "bid": [
                    {
                        "price": "54464.69",
                        "quantityChange": "-0.07972",
                        "costChange": "-4341.9250868",
                        "quantity": "0.00000",
                        "cost": "0.00"
                    },
                    {
                        "price": "54442.80",
                        "quantityChange": "0.08927",
                        "costChange": "4860.108756",
                        "quantity": "0.08927",
                        "cost": "4860.108756"
                    }
                ],
                "timestamp": time_ms_latoken
            },
            timestamp=time_ns,
            metadata={"trading_pair": self.trading_pair}
        )

        self._simulate_message_enqueue(self.tracker._tracking_message_queues[self.trading_pair], diff_msg)

        self.tracking_task = self.ev_loop.create_task(
            self.tracker._track_single_book(self.trading_pair)
        )
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertEqual(0, self.tracker.order_books[self.trading_pair].snapshot_uid)
        self.assertGreater(self.tracker.order_books[self.trading_pair].last_diff_uid, 1)
