import asyncio
import json
import re
import unittest

from typing import (
    Any,
    Awaitable,
    Dict,
    List,
)
from unittest.mock import AsyncMock, patch, MagicMock

from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
import hummingbot.connector.exchange.latoken.latoken_utils as utils
from hummingbot.connector.exchange.latoken.latoken_api_order_book_data_source import LatokenAPIOrderBookDataSource
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage

from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class LatokenAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.data_source = LatokenAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                         throttler=self.throttler,
                                                         domain=self.domain)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        LatokenAPIOrderBookDataSource._trading_pair_symbol_map = {
            "com": bidict(
                {f"{self.base_asset}/{self.quote_asset}": self.trading_pair})
        }

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        LatokenAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _successfully_subscribed_event(self):
        resp = {
            "result": None,
            "id": 1
        }
        return resp

    def _trade_update_event(self):
        resp = {
            "id": "3594a477-3633-4c35-8552-436ddb2dcff9",
            "timestamp": 1633705493102,
            "baseCurrency": "92151d82-df98-4d88-9a4d-284fa9eca49f",
            "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5",
            "direction": None,
            "price": "54540.41",
            "quantity": "0.05601",
            "cost": "3054.808364100000000000",
            "order": None,
            "makerBuyer": False
        }
        return resp

    def _order_diff_event(self):
        resp = {
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
            ]
        }
        return resp

    def _snapshot_response(self):
        resp = {
            "ask": [
                {
                    "price": "123.321",
                    "quantity": "0.12",
                    "cost": "14.79852",
                    "accumulated": "14.79852"
                },
                {
                    "price": "123.321",
                    "quantity": "0.12",
                    "cost": "14.79852",
                    "accumulated": "14.79852"
                }
            ],
            "bid": [
                {
                    "price": "123.321",
                    "quantity": "0.12",
                    "cost": "14.79852",
                    "accumulated": "14.79852"
                },
                {
                    "price": "123.321",
                    "quantity": "0.12",
                    "cost": "14.79852",
                    "accumulated": "14.79852"
                }
            ],
            "totalAsk": "...",
            "totalBid": "..."
        }
        return resp

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL, domain=self.domain)
        url = f"{url}?symbol={self.base_asset}{self.quote_asset}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = [
            {
                "symbol": "ETH/USDT",
                "baseCurrency": "23fa548b-f887-4f48-9b9b-7dd2c7de5ed0",
                "quoteCurrency": "d721fcf2-cf87-4626-916a-da50548fe5b3",
                "volume24h": "450.29",
                "volume7d": "3410.23",
                "change24h": "-5.2100",
                "change7d": "1.1491",
                "amount24h": "25.2100",
                "amount7d": "111.1491",
                "lastPrice": "10034.14",
                "lastQuantity": "10034.14",
                "bestBid": "105.1445",
                "bestBidQuantity": "198789.14",
                "bestAsk": "10021.14",
                "bestAskQuantity": "1054034.14",
                "updateTimestamp": 100341454655423
            }
        ]

        mock_api.get(regex_url, body=json.dumps(mock_response))

        result: Dict[str, float] = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair],
                                                    throttler=self.throttler)
        )

        self.assertEqual(1, len(result))
        self.assertEqual(100, result[self.trading_pair])

    @aioresponses()
    def test_get_all_mid_prices(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL, domain=self.domain)

        mock_response: List[Dict[str, Any]] = [
            {
                # Truncated Response
                "symbol": self.ex_trading_pair,
                "bestBid": "99",
                "bestAsk": "101",
            },
            {
                # Truncated Response for unrecognized pair
                "symbol": "BCCBTC",
                "bestBid": "99",
                "bestAsk": "101",
            }
        ]

        mock_api.get(url, body=json.dumps(mock_response))

        result: Dict[str, float] = self.async_run_with_timeout(
            self.data_source.get_all_mid_prices()
        )

        self.assertEqual(1, len(result))
        self.assertEqual(100, result[self.trading_pair])

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_api):
        LatokenAPIOrderBookDataSource._trading_pair_symbol_map = {}
        url = utils.public_rest_url(path_url=CONSTANTS.PAIR_PATH_URL, domain=self.domain)

        mock_response: List[Dict] = [
            {
                "id": "263d5e99-1413-47e4-9215-ce4f5dec3556",
                "status": "PAIR_STATUS_ACTIVE",
                "baseCurrency": "6ae140a9-8e75-4413-b157-8dd95c711b23",
                "quoteCurrency": "23fa548b-f887-4f48-9b9b-7dd2c7de5ed0",
                "priceTick": "0.010000000",
                "priceDecimals": 2,
                "quantityTick": "0.010000000",
                "quantityDecimals": 2,
                "costDisplayDecimals": 3,
                "created": 1571333313871,
                "minOrderQuantity": "0",
                "maxOrderCostUsd": "999999999999999999",
                "minOrderCostUsd": "0",
                "externalSymbol": ""
            }
        ]

        mock_api.get(url, body=json.dumps(mock_response))

        result: Dict[str] = self.async_run_with_timeout(
            self.data_source.fetch_trading_pairs()
        )

        self.assertEqual(2, len(result))
        self.assertIn("ETH-BTC", result)
        self.assertIn("LTC-BTC", result)
        self.assertNotIn("BNB-BTC", result)

    @aioresponses()
    def test_fetch_trading_pairs_exception_raised(self, mock_api):
        LatokenAPIOrderBookDataSource._trading_pair_symbol_map = {}

        url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        result: Dict[str] = self.async_run_with_timeout(
            self.data_source.fetch_trading_pairs()
        )

        self.assertEqual(0, len(result))

    def test_get_throttler_instance(self):
        self.assertIsInstance(LatokenAPIOrderBookDataSource._get_throttler_instance(), AsyncThrottler)

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_snapshot(self.trading_pair)
        )

        self.assertEqual(self._snapshot_response(), result)

    @aioresponses()
    def test_get_snapshot_catch_exception(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_snapshot(self.trading_pair)
            )

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.BOOK_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response: Dict[str, Any] = {
            "ask": [
                {
                    "price": "123.321",
                    "quantity": "0.12",
                    "cost": "14.79852",
                    "accumulated": "14.79852"
                },
                {
                    "price": "123.321",
                    "quantity": "0.12",
                    "cost": "14.79852",
                    "accumulated": "14.79852"
                }
            ],
            "bid": [
                {
                    "price": "123.321",
                    "quantity": "0.12",
                    "cost": "14.79852",
                    "accumulated": "14.79852"
                },
                {
                    "price": "123.321",
                    "quantity": "0.12",
                    "cost": "14.79852",
                    "accumulated": "14.79852"
                }
            ],
            "totalAsk": "...",
            "totalBid": "..."
        }
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        self.assertEqual(1, result.snapshot_uid)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        # sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
        #     websocket_mock=

        #
        # self.assertEqual(2, len(sent_subscription_messages))
        # expected_trade_subscription = {
        #     "method": "SUBSCRIBE",
        #     "params": [f"{self.ex_trading_pair.lower()}@trade"],
        #     "id": 1}
        # self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        # expected_diff_subscription = {
        #     "method": "SUBSCRIBE",
        #     "params": [f"{self.ex_trading_pair.lower()}@depth@100ms"],
        #     "id": 2}
        # self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(12345, msg.trade_id)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._order_diff_event(), asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(12345, msg.update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.BOOK_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    @patch("hummingbot.connector.exchange.latoken.latoken_api_order_book_data_source"
           ".LatokenAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        url = utils.public_rest_url(path_url=CONSTANTS.BOOK_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api, ):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = utils.public_rest_url(path_url=CONSTANTS.BOOK_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(12345, msg.update_id)
