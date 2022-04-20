import asyncio
import json
import re
import unittest
from decimal import Decimal

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
        cls.base_asset = "d8ae67f2-f954-4014-98c8-64b1ac334c64"
        cls.quote_asset = "0c3a106d-bde3-4c13-a26e-3fd2394529e5"
        cls.trading_pair = "ETH-USDT"
        # cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "tech"

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
            # "com": bidict(
            #     {f"{self.base_asset}/{self.quote_asset}": self.trading_pair}),
            self.domain: bidict(
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
        return b'CONNECTED\nserver:vertx-stomp/3.9.6\nheart-beat:1000,1000\nsession:37a8e962-7fa7-4eab-b163-146eeafdef63\nversion:1.1\n\n\x00 '

    def _subscribed_events(self):
        return b'MESSAGE\ndestination:/v1/book/d8ae67f2-f954-4014-98c8-64b1ac334c64/0c3a106d-bde3-4c13-a26e-3fd2394529e5\nmessage-id:0294925d-771c-4b18-85bb-90b4867489f0\ncontent-length:17741\nsubscription:1\n\n{"payload":{"ask":[{"price":"3.22","quantityChange":"10","costChange":"32.20","quantity":"10","cost":"32.20"},{"price":"3.23","quantityChange":"10","costChange":"32.30","quantity":"10","cost":"32.30"},{"price":"3.24","quantityChange":"10","costChange":"32.40","quantity":"10","cost":"32.40"},{"price":"3.25","quantityChange":"10","costChange":"32.50","quantity":"10","cost":"32.50"},{"price":"3.26","quantityChange":"10","costChange":"32.60","quantity":"10","cost":"32.60"},{"price":"3.27","quantityChange":"10","costChange":"32.70","quantity":"10","cost":"32.70"},{"price":"3.28","quantityChange":"10","costChange":"32.80","quantity":"10","cost":"32.80"},{"price":"3.29","quantityChange":"10","costChange":"32.90","quantity":"10","cost":"32.90"},{"price":"3.30","quantityChange":"10","costChange":"33.00","quantity":"10","cost":"33.00"},{"price":"3.31","quantityChange":"10","costChange":"33.10","quantity":"10","cost":"33.10"},{"price":"3.32","quantityChange":"10","costChange":"33.20","quantity":"10","cost":"33.20"},{"price":"3.33","quantityChange":"10","costChange":"33.30","quantity":"10","cost":"33.30"},{"price":"3.34","quantityChange":"10","costChange":"33.40","quantity":"10","cost":"33.40"},{"price":"3.35","quantityChange":"10","costChange":"33.50","quantity":"10","cost":"33.50"},{"price":"3.36","quantityChange":"10","costChange":"33.60","quantity":"10","cost":"33.60"},{"price":"3.37","quantityChange":"10","costChange":"33.70","quantity":"10","cost":"33.70"},{"price":"3.38","quantityChange":"10","costChange":"33.80","quantity":"10","cost":"33.80"},{"price":"3.39","quantityChange":"10","costChange":"33.90","quantity":"10","cost":"33.90"},{"price":"3.40","quantityChange":"10","costChange":"34.00","quantity":"10","cost":"34.00"},{"price":"3.41","quantityChange":"10","costChange":"34.10","quantity":"10","cost":"34.10"},{"price":"3.42","quantityChange":"10","costChange":"34.20","quantity":"10","cost":"34.20"},{"price":"3.43","quantityChange":"10","costChange":"34.30","quantity":"10","cost":"34.30"},{"price":"3.44","quantityChange":"10","costChange":"34.40","quantity":"10","cost":"34.40"},{"price":"3.45","quantityChange":"10","costChange":"34.50","quantity":"10","cost":"34.50"},{"price":"3.46","quantityChange":"10","costChange":"34.60","quantity":"10","cost":"34.60"},{"price":"3.47","quantityChange":"10","costChange":"34.70","quantity":"10","cost":"34.70"},{"price":"3.48","quantityChange":"10","costChange":"34.80","quantity":"10","cost":"34.80"},{"price":"3.49","quantityChange":"10","costChange":"34.90","quantity":"10","cost":"34.90"},{"price":"3.50","quantityChange":"10","costChange":"35.00","quantity":"10","cost":"35.00"},{"price":"3.51","quantityChange":"10","costChange":"35.10","quantity":"10","cost":"35.10"},{"price":"3.52","quantityChange":"10","costChange":"35.20","quantity":"10","cost":"35.20"},{"price":"3.53","quantityChange":"10","costChange":"35.30","quantity":"10","cost":"35.30"},{"price":"3.54","quantityChange":"10","costChange":"35.40","quantity":"10","cost":"35.40"},{"price":"3.55","quantityChange":"10","costChange":"35.50","quantity":"10","cost":"35.50"},{"price":"3.56","quantityChange":"10","costChange":"35.60","quantity":"10","cost":"35.60"},{"price":"3.57","quantityChange":"10","costChange":"35.70","quantity":"10","cost":"35.70"},{"price":"3.58","quantityChange":"10","costChange":"35.80","quantity":"10","cost":"35.80"},{"price":"3.59","quantityChange":"10","costChange":"35.90","quantity":"10","cost":"35.90"},{"price":"3.60","quantityChange":"10","costChange":"36.00","quantity":"10","cost":"36.00"},{"price":"3.61","quantityChange":"10","costChange":"36.10","quantity":"10","cost":"36.10"},{"price":"3.62","quantityChange":"10","costChange":"36.20","quantity":"10","cost":"36.20"},{"price":"3.63","quantityChange":"10","costChange":"36.30","quantity":"10","cost":"36.30"},{"price":"3.64","quantityChange":"10","costChange":"36.40","quantity":"10","cost":"36.40"},{"price":"3.65","quantityChange":"10","costChange":"36.50","quantity":"10","cost":"36.50"},{"price":"3.66","quantityChange":"10","costChange":"36.60","quantity":"10","cost":"36.60"},{"price":"3.67","quantityChange":"10","costChange":"36.70","quantity":"10","cost":"36.70"},{"price":"3.68","quantityChange":"20","costChange":"73.60","quantity":"20","cost":"73.60"},{"price":"3.70","quantityChange":"20","costChange":"74.00","quantity":"20","cost":"74.00"},{"price":"3.80","quantityChange":"1","costChange":"3.80","quantity":"1","cost":"3.80"},{"price":"3.81","quantityChange":"1","costChange":"3.81","quantity":"1","cost":"3.81"},{"price":"3.82","quantityChange":"1","costChange":"3.82","quantity":"1","cost":"3.82"},{"price":"3.83","quantityChange":"1","costChange":"3.83","quantity":"1","cost":"3.83"},{"price":"3.84","quantityChange":"1","costChange":"3.84","quantity":"1","cost":"3.84"},{"price":"3.85","quantityChange":"1","costChange":"3.85","quantity":"1","cost":"3.85"},{"price":"3.86","quantityChange":"1","costChange":"3.86","quantity":"1","cost":"3.86"},{"price":"3.87","quantityChange":"1","costChange":"3.87","quantity":"1","cost":"3.87"},{"price":"3.88","quantityChange":"1","costChange":"3.88","quantity":"1","cost":"3.88"},{"price":"3.89","quantityChange":"1","costChange":"3.89","quantity":"1","cost":"3.89"},{"price":"3.90","quantityChange":"1","costChange":"3.90","quantity":"1","cost":"3.90"},{"price":"3.91","quantityChange":"1","costChange":"3.91","quantity":"1","cost":"3.91"},{"price":"3.92","quantityChange":"1","costChange":"3.92","quantity":"1","cost":"3.92"},{"price":"3.93","quantityChange":"1","costChange":"3.93","quantity":"1","cost":"3.93"},{"price":"3.94","quantityChange":"1","costChange":"3.94","quantity":"1","cost":"3.94"},{"price":"3.95","quantityChange":"1","costChange":"3.95","quantity":"1","cost":"3.95"},{"price":"3.96","quantityChange":"1","costChange":"3.96","quantity":"1","cost":"3.96"},{"price":"3.97","quantityChange":"1","costChange":"3.97","quantity":"1","cost":"3.97"},{"price":"3.98","quantityChange":"1","costChange":"3.98","quantity":"1","cost":"3.98"},{"price":"3.99","quantityChange":"1","costChange":"3.99","quantity":"1","cost":"3.99"},{"price":"4.00","quantityChange":"1","costChange":"4.00","quantity":"1","cost":"4.00"},{"price":"4.01","quantityChange":"1","costChange":"4.01","quantity":"1","cost":"4.01"},{"price":"4.02","quantityChange":"1","costChange":"4.02","quantity":"1","cost":"4.02"},{"price":"4.03","quantityChange":"1","costChange":"4.03","quantity":"1","cost":"4.03"},{"price":"4.04","quantityChange":"1","costChange":"4.04","quantity":"1","cost":"4.04"},{"price":"4.05","quantityChange":"1","costChange":"4.05","quantity":"1","cost":"4.05"},{"price":"4.06","quantityChange":"1","costChange":"4.06","quantity":"1","cost":"4.06"},{"price":"4.07","quantityChange":"1","costChange":"4.07","quantity":"1","cost":"4.07"},{"price":"4.08","quantityChange":"1","costChange":"4.08","quantity":"1","cost":"4.08"},{"price":"4.09","quantityChange":"1","costChange":"4.09","quantity":"1","cost":"4.09"},{"price":"4.10","quantityChange":"1","costChange":"4.10","quantity":"1","cost":"4.10"},{"price":"4.11","quantityChange":"1","costChange":"4.11","quantity":"1","cost":"4.11"},{"price":"4.12","quantityChange":"1","costChange":"4.12","quantity":"1","cost":"4.12"},{"price":"4.13","quantityChange":"1","costChange":"4.13","quantity":"1","cost":"4.13"},{"price":"4.18","quantityChange":"1","costChange":"4.18","quantity":"1","cost":"4.18"},{"price":"4.91","quantityChange":"1","costChange":"4.91","quantity":"1","cost":"4.91"},{"price":"4.92","quantityChange":"1","costChange":"4.92","quantity":"1","cost":"4.92"},{"price":"4.93","quantityChange":"1","costChange":"4.93","quantity":"1","cost":"4.93"},{"price":"4.94","quantityChange":"1","costChange":"4.94","quantity":"1","cost":"4.94"},{"price":"4.95","quantityChange":"1","costChange":"4.95","quantity":"1","cost":"4.95"},{"price":"4.96","quantityChange":"1","costChange":"4.96","quantity":"1","cost":"4.96"},{"price":"4.97","quantityChange":"1","costChange":"4.97","quantity":"1","cost":"4.97"},{"price":"4.98","quantityChange":"1","costChange":"4.98","quantity":"1","cost":"4.98"},{"price":"4.99","quantityChange":"1","costChange":"4.99","quantity":"1","cost":"4.99"},{"price":"5.00","quantityChange":"1","costChange":"5.00","quantity":"1","cost":"5.00"},{"price":"5.06","quantityChange":"400","costChange":"2024.00","quantity":"400","cost":"2024.00"},{"price":"130.00","quantityChange":"1","costChange":"130.00","quantity":"1","cost":"130.00"},{"price":"140.00","quantityChange":"1","costChange":"140.00","quantity":"1","cost":"140.00"},{"price":"150.00","quantityChange":"10","costChange":"1500.00","quantity":"10","cost":"1500.00"}],"bid":[{"price":"18.21","quantityChange":"8","costChange":"145.68","quantity":"8","cost":"145.68"},{"price":"3.18","quantityChange":"10","costChange":"31.80","quantity":"10","cost":"31.80"},{"price":"3.17","quantityChange":"10","costChange":"31.70","quantity":"10","cost":"31.70"},{"price":"3.16","quantityChange":"10","costChange":"31.60","quantity":"10","cost":"31.60"},{"price":"3.15","quantityChange":"10","costChange":"31.50","quantity":"10","cost":"31.50"},{"price":"3.14","quantityChange":"10","costChange":"31.40","quantity":"10","cost":"31.40"},{"price":"3.13","quantityChange":"10","costChange":"31.30","quantity":"10","cost":"31.30"},{"price":"3.12","quantityChange":"10","costChange":"31.20","quantity":"10","cost":"31.20"},{"price":"3.11","quantityChange":"10","costChange":"31.10","quantity":"10","cost":"31.10"},{"price":"3.10","quantityChange":"10","costChange":"31.00","quantity":"10","cost":"31.00"},{"price":"3.09","quantityChange":"10","costChange":"30.90","quantity":"10","cost":"30.90"},{"price":"3.08","quantityChange":"110","costChange":"338.80","quantity":"110","cost":"338.80"},{"price":"3.07","quantityChange":"100","costChange":"307.00","quantity":"100","cost":"307.00"},{"price":"3.06","quantityChange":"100","costChange":"306.00","quantity":"100","cost":"306.00"},{"price":"3.05","quantityChange":"100","costChange":"305.00","quantity":"100","cost":"305.00"},{"price":"3.04","quantityChange":"100","costChange":"304.00","quantity":"100","cost":"304.00"},{"price":"3.03","quantityChange":"10","costChange":"30.30","quantity":"10","cost":"30.30"},{"price":"3.02","quantityChange":"10","costChange":"30.20","quantity":"10","cost":"30.20"},{"price":"3.01","quantityChange":"10","costChange":"30.10","quantity":"10","cost":"30.10"},{"price":"3.00","quantityChange":"10","costChange":"30.00","quantity":"10","cost":"30.00"},{"price":"2.99","quantityChange":"10","costChange":"29.90","quantity":"10","cost":"29.90"},{"price":"2.98","quantityChange":"10","costChange":"29.80","quantity":"10","cost":"29.80"},{"price":"2.97","quantityChange":"10","costChange":"29.70","quantity":"10","cost":"29.70"},{"price":"2.96","quantityChange":"10","costChange":"29.60","quantity":"10","cost":"29.60"},{"price":"2.95","quantityChange":"10","costChange":"29.50","quantity":"10","cost":"29.50"},{"price":"2.94","quantityChange":"10","costChange":"29.40","quantity":"10","cost":"29.40"},{"price":"2.93","quantityChange":"10","costChange":"29.30","quantity":"10","cost":"29.30"},{"price":"2.92","quantityChange":"10","costChange":"29.20","quantity":"10","cost":"29.20"},{"price":"2.91","quantityChange":"10","costChange":"29.10","quantity":"10","cost":"29.10"},{"price":"2.90","quantityChange":"10","costChange":"29.00","quantity":"10","cost":"29.00"},{"price":"2.89","quantityChange":"10","costChange":"28.90","quantity":"10","cost":"28.90"},{"price":"2.88","quantityChange":"10","costChange":"28.80","quantity":"10","cost":"28.80"},{"price":"2.87","quantityChange":"10","costChange":"28.70","quantity":"10","cost":"28.70"},{"price":"2.86","quantityChange":"10","costChange":"28.60","quantity":"10","cost":"28.60"},{"price":"2.85","quantityChange":"10","costChange":"28.50","quantity":"10","cost":"28.50"},{"price":"2.84","quantityChange":"10","costChange":"28.40","quantity":"10","cost":"28.40"},{"price":"2.83","quantityChange":"10","costChange":"28.30","quantity":"10","cost":"28.30"},{"price":"2.82","quantityChange":"10","costChange":"28.20","quantity":"10","cost":"28.20"},{"price":"2.81","quantityChange":"10","costChange":"28.10","quantity":"10","cost":"28.10"},{"price":"2.80","quantityChange":"10","costChange":"28.00","quantity":"10","cost":"28.00"},{"price":"2.79","quantityChange":"10","costChange":"27.90","quantity":"10","cost":"27.90"},{"price":"2.78","quantityChange":"10","costChange":"27.80","quantity":"10","cost":"27.80"},{"price":"2.77","quantityChange":"10","costChange":"27.70","quantity":"10","cost":"27.70"},{"price":"2.76","quantityChange":"20","costChange":"55.20","quantity":"20","cost":"55.20"},{"price":"2.75","quantityChange":"10","costChange":"27.50","quantity":"10","cost":"27.50"},{"price":"2.74","quantityChange":"10","costChange":"27.40","quantity":"10","cost":"27.40"},{"price":"2.73","quantityChange":"20","costChange":"54.60","quantity":"20","cost":"54.60"},{"price":"2.72","quantityChange":"10","costChange":"27.20","quantity":"10","cost":"27.20"},{"price":"2.71","quantityChange":"10","costChange":"27.10","quantity":"10","cost":"27.10"},{"price":"2.70","quantityChange":"10","costChange":"27.00","quantity":"10","cost":"27.00"},{"price":"2.69","quantityChange":"10","costChange":"26.90","quantity":"10","cost":"26.90"},{"price":"2.68","quantityChange":"10","costChange":"26.80","quantity":"10","cost":"26.80"},{"price":"2.67","quantityChange":"10","costChange":"26.70","quantity":"10","cost":"26.70"},{"price":"2.66","quantityChange":"10","costChange":"26.60","quantity":"10","cost":"26.60"},{"price":"2.65","quantityChange":"10","costChange":"26.50","quantity":"10","cost":"26.50"},{"price":"2.64","quantityChange":"10","costChange":"26.40","quantity":"10","cost":"26.40"},{"price":"2.63","quantityChange":"10","costChange":"26.30","quantity":"10","cost":"26.30"},{"price":"2.62","quantityChange":"10","costChange":"26.20","quantity":"10","cost":"26.20"},{"price":"2.61","quantityChange":"10","costChange":"26.10","quantity":"10","cost":"26.10"},{"price":"2.60","quantityChange":"10","costChange":"26.00","quantity":"10","cost":"26.00"},{"price":"2.59","quantityChange":"10","costChange":"25.90","quantity":"10","cost":"25.90"},{"price":"2.58","quantityChange":"10","costChange":"25.80","quantity":"10","cost":"25.80"},{"price":"2.57","quantityChange":"10","costChange":"25.70","quantity":"10","cost":"25.70"},{"price":"2.56","quantityChange":"10","costChange":"25.60","quantity":"10","cost":"25.60"},{"price":"2.55","quantityChange":"10","costChange":"25.50","quantity":"10","cost":"25.50"},{"price":"2.54","quantityChange":"10","costChange":"25.40","quantity":"10","cost":"25.40"},{"price":"2.53","quantityChange":"10","costChange":"25.30","quantity":"10","cost":"25.30"},{"price":"2.52","quantityChange":"10","costChange":"25.20","quantity":"10","cost":"25.20"},{"price":"2.51","quantityChange":"10","costChange":"25.10","quantity":"10","cost":"25.10"},{"price":"2.50","quantityChange":"10","costChange":"25.00","quantity":"10","cost":"25.00"},{"price":"2.49","quantityChange":"10","costChange":"24.90","quantity":"10","cost":"24.90"},{"price":"2.48","quantityChange":"200","costChange":"496.00","quantity":"200","cost":"496.00"},{"price":"2.47","quantityChange":"1","costChange":"2.47","quantity":"1","cost":"2.47"},{"price":"2.46","quantityChange":"1","costChange":"2.46","quantity":"1","cost":"2.46"},{"price":"2.45","quantityChange":"1","costChange":"2.45","quantity":"1","cost":"2.45"},{"price":"2.44","quantityChange":"1","costChange":"2.44","quantity":"1","cost":"2.44"},{"price":"2.43","quantityChange":"1","costChange":"2.43","quantity":"1","cost":"2.43"},{"price":"2.42","quantityChange":"1","costChange":"2.42","quantity":"1","cost":"2.42"},{"price":"2.41","quantityChange":"1","costChange":"2.41","quantity":"1","cost":"2.41"},{"price":"2.40","quantityChange":"1","costChange":"2.40","quantity":"1","cost":"2.40"},{"price":"2.39","quantityChange":"1","costChange":"2.39","quantity":"1","cost":"2.39"},{"price":"2.38","quantityChange":"1","costChange":"2.38","quantity":"1","cost":"2.38"},{"price":"2.37","quantityChange":"1","costChange":"2.37","quantity":"1","cost":"2.37"},{"price":"2.36","quantityChange":"1","costChange":"2.36","quantity":"1","cost":"2.36"},{"price":"2.35","quantityChange":"1","costChange":"2.35","quantity":"1","cost":"2.35"},{"price":"2.34","quantityChange":"1","costChange":"2.34","quantity":"1","cost":"2.34"},{"price":"2.33","quantityChange":"1","costChange":"2.33","quantity":"1","cost":"2.33"},{"price":"2.32","quantityChange":"1","costChange":"2.32","quantity":"1","cost":"2.32"},{"price":"2.31","quantityChange":"1","costChange":"2.31","quantity":"1","cost":"2.31"},{"price":"2.30","quantityChange":"1","costChange":"2.30","quantity":"1","cost":"2.30"},{"price":"2.29","quantityChange":"1","costChange":"2.29","quantity":"1","cost":"2.29"},{"price":"2.28","quantityChange":"1","costChange":"2.28","quantity":"1","cost":"2.28"},{"price":"2.27","quantityChange":"1","costChange":"2.27","quantity":"1","cost":"2.27"},{"price":"2.26","quantityChange":"1","costChange":"2.26","quantity":"1","cost":"2.26"},{"price":"2.25","quantityChange":"1","costChange":"2.25","quantity":"1","cost":"2.25"},{"price":"2.24","quantityChange":"1","costChange":"2.24","quantity":"1","cost":"2.24"},{"price":"2.23","quantityChange":"1","costChange":"2.23","quantity":"1","cost":"2.23"},{"price":"2.22","quantityChange":"1","costChange":"2.22","quantity":"1","cost":"2.22"},{"price":"2.21","quantityChange":"1","costChange":"2.21","quantity":"1","cost":"2.21"},{"price":"2.20","quantityChange":"1","costChange":"2.20","quantity":"1","cost":"2.20"}]},"nonce":0,"timestamp":1650127205077}\x00'

    def _trade_update_event(self):
        resp = {'cmd': 'MESSAGE', 'headers': {'destination': '/v1/trade/d8ae67f2-f954-4014-98c8-64b1ac334c64/0c3a106d-bde3-4c13-a26e-3fd2394529e5', 'message-id': '85462563-2a5e-4162-93f3-c59194929677', 'content-length': '24486', 'subscription': '2'}, 'body': '{"payload":[{"id":"4e278949-00c8-4513-bddd-c69f4ff50fc6","timestamp":1649760685161,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.24","quantity":"10","cost":"32.4","makerBuyer":false},{"id":"6e27ca81-5306-4ac8-9d0e-5f0107c11407","timestamp":1649760685161,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.23","quantity":"10","cost":"32.3","makerBuyer":false},{"id":"3326e01e-b689-43db-a25c-c28fcd2fb6a4","timestamp":1649760685161,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.22","quantity":"10","cost":"32.2","makerBuyer":false},{"id":"3e45f539-a559-46ca-b711-89cb8b227247","timestamp":1649760685161,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.21","quantity":"10","cost":"32.1","makerBuyer":false},{"id":"d7712f61-1052-4631-b9b0-ef54593c47fd","timestamp":1649760685161,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.2","quantity":"10","cost":"32","makerBuyer":false},{"id":"fb03f520-79f2-4e81-a2d2-d3c917b719aa","timestamp":1649760344429,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.2","quantity":"10","cost":"32","makerBuyer":false},{"id":"81a865a2-11bf-400b-b971-62f266e42ded","timestamp":1649760344429,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.19","quantity":"10","cost":"31.9","makerBuyer":false},{"id":"5c5db69d-5074-4d4b-8560-9ee3e9958ea8","timestamp":1649760344429,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":false},{"id":"c268b088-abaf-4795-8f7f-e65a64c77f6d","timestamp":1649760344429,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.17","quantity":"10","cost":"31.7","makerBuyer":false},{"id":"350398ca-0564-4a8c-b2cc-15c0e3b21219","timestamp":1649760344429,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.16","quantity":"10","cost":"31.6","makerBuyer":false},{"id":"72f40d27-f8a3-41cc-ab3d-4226b3eb9d28","timestamp":1649760326004,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.15","quantity":"10","cost":"31.5","makerBuyer":true},{"id":"8d0a5a0c-aa85-4f06-81cd-24f5b866da9e","timestamp":1649760272256,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":false},{"id":"0de9a38d-94b9-4b32-aaf6-f2253b28dfa2","timestamp":1649760272256,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.17","quantity":"10","cost":"31.7","makerBuyer":false},{"id":"6d62d4b5-d42c-449b-9d5a-a8c29362df58","timestamp":1649760272256,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.16","quantity":"10","cost":"31.6","makerBuyer":false},{"id":"f206a5a2-4703-40d0-8147-7ffd957efd04","timestamp":1649760272256,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.15","quantity":"10","cost":"31.5","makerBuyer":false},{"id":"2f71e6c2-0267-4d1f-af6e-da1174537e02","timestamp":1649760272256,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.14","quantity":"10","cost":"31.4","makerBuyer":false},{"id":"02f109cd-deb5-49a2-9cd0-de958289899c","timestamp":1649758855175,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.13","quantity":"10","cost":"31.3","makerBuyer":false},{"id":"f6c4c7a7-ce76-467c-a22f-0ee7337192e8","timestamp":1649757551351,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.2","quantity":"10","cost":"32","makerBuyer":false},{"id":"7553947c-4ee6-419f-a670-58115f297d48","timestamp":1649757551351,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.19","quantity":"10","cost":"31.9","makerBuyer":false},{"id":"3cb059a6-5636-4fc2-b73f-54f17f09e42b","timestamp":1649757551351,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":false},{"id":"19b190ee-88f5-4cef-9135-208bf8cee947","timestamp":1649757551351,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.17","quantity":"10","cost":"31.7","makerBuyer":false},{"id":"4b5eaa0a-407e-441a-800a-8a2b3f8ca233","timestamp":1649757551351,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.16","quantity":"10","cost":"31.6","makerBuyer":false},{"id":"a564031d-199d-4588-85b0-a0131c57fc52","timestamp":1649757551351,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.15","quantity":"10","cost":"31.5","makerBuyer":false},{"id":"7ba42599-8cf6-4336-bf8e-70698d2eb507","timestamp":1649418503717,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.39","quantity":"10","cost":"33.9","makerBuyer":false},{"id":"bb715389-e6c9-4def-9eb5-1ab35fc588ac","timestamp":1649248205111,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"2.28","quantity":"1","cost":"2.28","makerBuyer":false},{"id":"d81b2b54-1250-45b8-95a6-96838c21f27d","timestamp":1649242686129,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"140","quantity":"1","cost":"140","makerBuyer":false},{"id":"04dc4441-643e-4e2e-8a2b-33d47b944481","timestamp":1649241559785,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"15","quantity":"7","cost":"105","makerBuyer":false},{"id":"7bddc732-ae6e-45e8-b3f7-a4dad7e14f33","timestamp":1649241559785,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"14","quantity":"1","cost":"14","makerBuyer":false},{"id":"56197ca5-185b-48b2-9b96-ee2445a54b65","timestamp":1649241559785,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13","quantity":"1","cost":"13","makerBuyer":false},{"id":"9a129000-a8de-43d9-904f-5b89e79efa16","timestamp":1649241559785,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"12","quantity":"1","cost":"12","makerBuyer":false},{"id":"6704b1f0-6d95-4c34-9284-98caf6bb3564","timestamp":1649241541185,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"11","quantity":"1","cost":"11","makerBuyer":false},{"id":"1d44a6e6-9604-466c-bebd-79e3493383a7","timestamp":1649241533548,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"10","quantity":"1","cost":"10","makerBuyer":false},{"id":"5cbef23b-0bcd-4bfd-91b4-baf99d883874","timestamp":1649241461361,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"15","quantity":"3","cost":"45","makerBuyer":false},{"id":"aef917b7-7aa5-4934-88aa-bd1b249ba0a9","timestamp":1649241461361,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"14","quantity":"97","cost":"1358","makerBuyer":false},{"id":"3e55890d-90c8-439e-80a9-ee27d45d384d","timestamp":1649241441932,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"2.36","quantity":"70","cost":"165.2","makerBuyer":true},{"id":"01109a6f-364e-4c3a-bd10-50bd77f0535f","timestamp":1649241441932,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"2.36","quantity":"200","cost":"472","makerBuyer":true},{"id":"9cf4dc7b-902b-49e3-9c2d-68d7cb447a15","timestamp":1649241441932,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"2.36","quantity":"30","cost":"70.8","makerBuyer":true},{"id":"ac2bd38a-1a32-41b0-a527-1c5147068c28","timestamp":1649241439646,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"2.36","quantity":"170","cost":"401.2","makerBuyer":true},{"id":"ba50212a-2134-4a48-be23-c5290cf2b300","timestamp":1649241439646,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3","quantity":"90","cost":"270","makerBuyer":true},{"id":"be5d3f07-f9b7-41c8-8951-b13cf33bc93a","timestamp":1649241439646,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3","quantity":"40","cost":"120","makerBuyer":true},{"id":"f31e532e-2ed0-43cf-b97f-1ff0b69ffd7b","timestamp":1649241432695,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3","quantity":"60","cost":"180","makerBuyer":true},{"id":"3d31e89f-fab2-4361-ad2b-0bd41b62bc23","timestamp":1649241432695,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.1","quantity":"90","cost":"279","makerBuyer":true},{"id":"4da39dbc-35c6-4609-ab93-fbd2a2364d89","timestamp":1649241432695,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.11","quantity":"70","cost":"217.7","makerBuyer":true},{"id":"5be2cb53-dfa7-4d16-84f7-f69fc981ee17","timestamp":1649241432695,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.11","quantity":"80","cost":"248.8","makerBuyer":true},{"id":"d5c1d014-4ff7-482e-bcc9-35c28a9b716d","timestamp":1649240750871,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.12","quantity":"70","cost":"218.4","makerBuyer":true},{"id":"c5d6a9ec-e53d-4922-a517-79036d6cd6eb","timestamp":1649240316923,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.13","quantity":"30","cost":"93.9","makerBuyer":true},{"id":"c9dcd511-97fb-46b8-9518-cf6cd26caeaa","timestamp":1649240192819,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.14","quantity":"30","cost":"94.2","makerBuyer":true},{"id":"6b5f4d3a-59f8-453e-b928-8a888e7d573e","timestamp":1649239913235,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.15","quantity":"30","cost":"94.5","makerBuyer":true},{"id":"1aa27ffb-c2fa-4825-b7ed-86f1250c63d5","timestamp":1649239481462,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"100","cost":"318","makerBuyer":true},{"id":"ab824387-c9bf-4cce-99fe-4d93a63e5eb6","timestamp":1649239248734,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.16","quantity":"20","cost":"63.2","makerBuyer":true},{"id":"36aadc23-0516-450a-a4d7-0557b63f046c","timestamp":1649239248734,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.17","quantity":"80","cost":"253.6","makerBuyer":true},{"id":"f6ba3759-9014-4aa3-bd88-9348d82e7041","timestamp":1649238269134,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":true},{"id":"4ce33a08-6b10-4b55-aa1f-919eae0e43c2","timestamp":1649238267503,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":true},{"id":"86f3d904-c9b1-4523-9406-ac165240ba36","timestamp":1649238264617,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":true},{"id":"064e3d2a-91fb-4875-90d8-64f5b3d92dfd","timestamp":1649238261352,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":true},{"id":"01e2312f-9820-418c-9cfe-557ecd3f0c51","timestamp":1649238259989,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":true},{"id":"03d12bd0-9bf7-4d8b-898d-960db8e64b6e","timestamp":1649238254501,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":true},{"id":"8c9e4b1a-1d3c-4e7e-ac54-a07ce0653228","timestamp":1649238252215,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":true},{"id":"6a1c9289-10c2-4d64-9cfa-fad341f2971e","timestamp":1649238250244,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":true},{"id":"8b6e2d50-d108-4682-a12b-ee4b736bdd80","timestamp":1649238247221,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":true},{"id":"4f05425e-01e9-401b-825f-6207870c66ce","timestamp":1649238242954,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.18","quantity":"10","cost":"31.8","makerBuyer":true},{"id":"93a7fa6e-8b4a-4b02-a37c-33394fdaee68","timestamp":1649238190761,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.99","quantity":"90","cost":"1259.1","makerBuyer":false},{"id":"dedb5c46-da6b-4ad8-9c23-e768f4c56396","timestamp":1649238146537,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.98","quantity":"80","cost":"1118.4","makerBuyer":false},{"id":"00ffd39b-667b-454f-8030-758697988b3d","timestamp":1649238090175,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.16","quantity":"10","cost":"31.6","makerBuyer":true},{"id":"b4a5a13f-6dd1-4a32-adf3-e642984050c6","timestamp":1649238086236,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.17","quantity":"10","cost":"31.7","makerBuyer":true},{"id":"abf1d4d5-d9a8-406b-a0b7-08687ff53e34","timestamp":1649238083493,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.17","quantity":"10","cost":"31.7","makerBuyer":true},{"id":"35d4bd61-8bd1-4bbd-b84a-699a8ee36c20","timestamp":1649238080617,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.17","quantity":"10","cost":"31.7","makerBuyer":true},{"id":"9ace0c9e-ffa5-48b0-8ac3-91074d2e66f7","timestamp":1649238068399,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.97","quantity":"10","cost":"139.7","makerBuyer":false},{"id":"e0e3930e-35bd-4da0-b07d-5e1ca085feff","timestamp":1649238066202,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.96","quantity":"10","cost":"139.6","makerBuyer":false},{"id":"af62d4bf-c02d-42d3-ad62-5d49cbfee7bb","timestamp":1649238063111,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.95","quantity":"10","cost":"139.5","makerBuyer":false},{"id":"9c3dc421-fd45-486f-a50e-97ea122ba3da","timestamp":1649238059512,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.94","quantity":"10","cost":"139.4","makerBuyer":false},{"id":"33ddeee7-d023-4eab-9395-57442a4717e0","timestamp":1649237979531,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.97","quantity":"20","cost":"279.4","makerBuyer":false},{"id":"0244f5fe-7693-4653-8ca9-40e575a114e1","timestamp":1649237979531,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.96","quantity":"10","cost":"139.6","makerBuyer":false},{"id":"5ebef1fb-a488-45e3-a242-465f5fc849b9","timestamp":1649237964958,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.14","quantity":"10","cost":"31.4","makerBuyer":true},{"id":"ad3a6504-458b-42b2-ad4c-f0e51822d4b6","timestamp":1649237935312,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.96","quantity":"10","cost":"139.6","makerBuyer":false},{"id":"209fc097-020c-400f-8923-aa5e70f1518b","timestamp":1649237925447,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.14","quantity":"10","cost":"31.4","makerBuyer":true},{"id":"27a2c97e-da3f-45b8-abd7-cf1f4dadef7c","timestamp":1649237903428,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.15","quantity":"20","cost":"63","makerBuyer":true},{"id":"65f8f015-103c-4589-bd83-bfdde29d08f4","timestamp":1649237894579,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.95","quantity":"20","cost":"279","makerBuyer":false},{"id":"0b7aebe8-4b9b-433f-a2ed-7f82b83d658a","timestamp":1649237324017,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.93","quantity":"20","cost":"278.6","makerBuyer":false},{"id":"472c79e0-9087-466d-829a-d83e19c35348","timestamp":1649237211245,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.13","quantity":"20","cost":"62.6","makerBuyer":true},{"id":"0bbf3858-9045-48fb-bd2c-f7d1888ee05e","timestamp":1649237204916,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.96","quantity":"10","cost":"139.6","makerBuyer":false},{"id":"5271cb3e-0d89-4285-bedc-d39857c45477","timestamp":1649237204916,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.95","quantity":"10","cost":"139.5","makerBuyer":false},{"id":"e899d0c4-8f81-47dd-a8a2-297626af5bea","timestamp":1649237196345,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.13","quantity":"10","cost":"31.3","makerBuyer":true},{"id":"0b777bfb-9b8b-483d-9740-c36fb53016e0","timestamp":1649237196345,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.14","quantity":"10","cost":"31.4","makerBuyer":true},{"id":"9b5763ff-bc9a-44d6-9007-07fcc497286b","timestamp":1649237191084,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.94","quantity":"10","cost":"139.4","makerBuyer":false},{"id":"92000e88-f6c7-4134-87ec-7c48603d7118","timestamp":1649237191084,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.93","quantity":"10","cost":"139.3","makerBuyer":false},{"id":"f2119a8e-a781-4834-8c29-02bd35bdef64","timestamp":1649237180038,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"6","quantity":"20","cost":"120","makerBuyer":true},{"id":"a3d413c5-ae07-4934-af06-b661e5fd81a8","timestamp":1649237169485,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.92","quantity":"10","cost":"139.2","makerBuyer":false},{"id":"b55e487f-daf2-4362-89b9-9aabc37d2590","timestamp":1649237169485,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.91","quantity":"10","cost":"139.1","makerBuyer":false},{"id":"37cf88cd-9e92-4cd8-a89e-bd2d2eb1bfda","timestamp":1649164335969,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.15","quantity":"10","cost":"31.5","makerBuyer":true},{"id":"5218dfc8-c126-42c0-a27c-8c433e9815f9","timestamp":1649164333320,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.9","quantity":"10","cost":"139","makerBuyer":false},{"id":"9f6e1108-96ec-421d-8a04-f0b7ed6d5e47","timestamp":1649164205410,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.15","quantity":"10","cost":"31.5","makerBuyer":true},{"id":"f6ff6127-6044-4452-9382-98105595335b","timestamp":1649164200088,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.89","quantity":"10","cost":"138.9","makerBuyer":false},{"id":"551fa7fe-ed10-4966-8f19-c596dd8c6194","timestamp":1649163970448,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.97","quantity":"10","cost":"139.7","makerBuyer":false},{"id":"740b462e-8e92-43bb-8d58-7e3500628dcd","timestamp":1649163939915,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.97","quantity":"10","cost":"139.7","makerBuyer":false},{"id":"048997dc-d4b8-470f-b10f-0f7d4eaed11e","timestamp":1649163936937,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.97","quantity":"10","cost":"139.7","makerBuyer":false},{"id":"00e3ff48-c40b-49df-8cc0-c88639bcce60","timestamp":1649163933674,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"13.97","quantity":"10","cost":"139.7","makerBuyer":false},{"id":"240e3075-d39b-4eb1-9f83-32c35402edf7","timestamp":1649163929275,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.14","quantity":"10","cost":"31.4","makerBuyer":true},{"id":"69056d17-23d6-4bbd-be5d-7c4f355c0b06","timestamp":1649163926353,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.14","quantity":"10","cost":"31.4","makerBuyer":true},{"id":"f98760bb-d872-4f7c-9834-83e6a840942e","timestamp":1649163923585,"baseCurrency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","price":"3.14","quantity":"10","cost":"31.4","makerBuyer":true}],"nonce":0,"timestamp":1650124982296}'}
        return resp

    def _order_diff_event(self):
        resp = {'cmd': 'MESSAGE', 'headers': {'destination': '/v1/book/d8ae67f2-f954-4014-98c8-64b1ac334c64/0c3a106d-bde3-4c13-a26e-3fd2394529e5', 'message-id': '088ea805-f566-4882-b4dd-17a84cbf6744', 'content-length': '17741', 'subscription': '1'}, 'body': '{"payload":{"ask":[{"price":"3.22","quantityChange":"10","costChange":"32.20","quantity":"10","cost":"32.20"},{"price":"3.23","quantityChange":"10","costChange":"32.30","quantity":"10","cost":"32.30"},{"price":"3.24","quantityChange":"10","costChange":"32.40","quantity":"10","cost":"32.40"},{"price":"3.25","quantityChange":"10","costChange":"32.50","quantity":"10","cost":"32.50"},{"price":"3.26","quantityChange":"10","costChange":"32.60","quantity":"10","cost":"32.60"},{"price":"3.27","quantityChange":"10","costChange":"32.70","quantity":"10","cost":"32.70"},{"price":"3.28","quantityChange":"10","costChange":"32.80","quantity":"10","cost":"32.80"},{"price":"3.29","quantityChange":"10","costChange":"32.90","quantity":"10","cost":"32.90"},{"price":"3.30","quantityChange":"10","costChange":"33.00","quantity":"10","cost":"33.00"},{"price":"3.31","quantityChange":"10","costChange":"33.10","quantity":"10","cost":"33.10"},{"price":"3.32","quantityChange":"10","costChange":"33.20","quantity":"10","cost":"33.20"},{"price":"3.33","quantityChange":"10","costChange":"33.30","quantity":"10","cost":"33.30"},{"price":"3.34","quantityChange":"10","costChange":"33.40","quantity":"10","cost":"33.40"},{"price":"3.35","quantityChange":"10","costChange":"33.50","quantity":"10","cost":"33.50"},{"price":"3.36","quantityChange":"10","costChange":"33.60","quantity":"10","cost":"33.60"},{"price":"3.37","quantityChange":"10","costChange":"33.70","quantity":"10","cost":"33.70"},{"price":"3.38","quantityChange":"10","costChange":"33.80","quantity":"10","cost":"33.80"},{"price":"3.39","quantityChange":"10","costChange":"33.90","quantity":"10","cost":"33.90"},{"price":"3.40","quantityChange":"10","costChange":"34.00","quantity":"10","cost":"34.00"},{"price":"3.41","quantityChange":"10","costChange":"34.10","quantity":"10","cost":"34.10"},{"price":"3.42","quantityChange":"10","costChange":"34.20","quantity":"10","cost":"34.20"},{"price":"3.43","quantityChange":"10","costChange":"34.30","quantity":"10","cost":"34.30"},{"price":"3.44","quantityChange":"10","costChange":"34.40","quantity":"10","cost":"34.40"},{"price":"3.45","quantityChange":"10","costChange":"34.50","quantity":"10","cost":"34.50"},{"price":"3.46","quantityChange":"10","costChange":"34.60","quantity":"10","cost":"34.60"},{"price":"3.47","quantityChange":"10","costChange":"34.70","quantity":"10","cost":"34.70"},{"price":"3.48","quantityChange":"10","costChange":"34.80","quantity":"10","cost":"34.80"},{"price":"3.49","quantityChange":"10","costChange":"34.90","quantity":"10","cost":"34.90"},{"price":"3.50","quantityChange":"10","costChange":"35.00","quantity":"10","cost":"35.00"},{"price":"3.51","quantityChange":"10","costChange":"35.10","quantity":"10","cost":"35.10"},{"price":"3.52","quantityChange":"10","costChange":"35.20","quantity":"10","cost":"35.20"},{"price":"3.53","quantityChange":"10","costChange":"35.30","quantity":"10","cost":"35.30"},{"price":"3.54","quantityChange":"10","costChange":"35.40","quantity":"10","cost":"35.40"},{"price":"3.55","quantityChange":"10","costChange":"35.50","quantity":"10","cost":"35.50"},{"price":"3.56","quantityChange":"10","costChange":"35.60","quantity":"10","cost":"35.60"},{"price":"3.57","quantityChange":"10","costChange":"35.70","quantity":"10","cost":"35.70"},{"price":"3.58","quantityChange":"10","costChange":"35.80","quantity":"10","cost":"35.80"},{"price":"3.59","quantityChange":"10","costChange":"35.90","quantity":"10","cost":"35.90"},{"price":"3.60","quantityChange":"10","costChange":"36.00","quantity":"10","cost":"36.00"},{"price":"3.61","quantityChange":"10","costChange":"36.10","quantity":"10","cost":"36.10"},{"price":"3.62","quantityChange":"10","costChange":"36.20","quantity":"10","cost":"36.20"},{"price":"3.63","quantityChange":"10","costChange":"36.30","quantity":"10","cost":"36.30"},{"price":"3.64","quantityChange":"10","costChange":"36.40","quantity":"10","cost":"36.40"},{"price":"3.65","quantityChange":"10","costChange":"36.50","quantity":"10","cost":"36.50"},{"price":"3.66","quantityChange":"10","costChange":"36.60","quantity":"10","cost":"36.60"},{"price":"3.67","quantityChange":"10","costChange":"36.70","quantity":"10","cost":"36.70"},{"price":"3.68","quantityChange":"20","costChange":"73.60","quantity":"20","cost":"73.60"},{"price":"3.70","quantityChange":"20","costChange":"74.00","quantity":"20","cost":"74.00"},{"price":"3.80","quantityChange":"1","costChange":"3.80","quantity":"1","cost":"3.80"},{"price":"3.81","quantityChange":"1","costChange":"3.81","quantity":"1","cost":"3.81"},{"price":"3.82","quantityChange":"1","costChange":"3.82","quantity":"1","cost":"3.82"},{"price":"3.83","quantityChange":"1","costChange":"3.83","quantity":"1","cost":"3.83"},{"price":"3.84","quantityChange":"1","costChange":"3.84","quantity":"1","cost":"3.84"},{"price":"3.85","quantityChange":"1","costChange":"3.85","quantity":"1","cost":"3.85"},{"price":"3.86","quantityChange":"1","costChange":"3.86","quantity":"1","cost":"3.86"},{"price":"3.87","quantityChange":"1","costChange":"3.87","quantity":"1","cost":"3.87"},{"price":"3.88","quantityChange":"1","costChange":"3.88","quantity":"1","cost":"3.88"},{"price":"3.89","quantityChange":"1","costChange":"3.89","quantity":"1","cost":"3.89"},{"price":"3.90","quantityChange":"1","costChange":"3.90","quantity":"1","cost":"3.90"},{"price":"3.91","quantityChange":"1","costChange":"3.91","quantity":"1","cost":"3.91"},{"price":"3.92","quantityChange":"1","costChange":"3.92","quantity":"1","cost":"3.92"},{"price":"3.93","quantityChange":"1","costChange":"3.93","quantity":"1","cost":"3.93"},{"price":"3.94","quantityChange":"1","costChange":"3.94","quantity":"1","cost":"3.94"},{"price":"3.95","quantityChange":"1","costChange":"3.95","quantity":"1","cost":"3.95"},{"price":"3.96","quantityChange":"1","costChange":"3.96","quantity":"1","cost":"3.96"},{"price":"3.97","quantityChange":"1","costChange":"3.97","quantity":"1","cost":"3.97"},{"price":"3.98","quantityChange":"1","costChange":"3.98","quantity":"1","cost":"3.98"},{"price":"3.99","quantityChange":"1","costChange":"3.99","quantity":"1","cost":"3.99"},{"price":"4.00","quantityChange":"1","costChange":"4.00","quantity":"1","cost":"4.00"},{"price":"4.01","quantityChange":"1","costChange":"4.01","quantity":"1","cost":"4.01"},{"price":"4.02","quantityChange":"1","costChange":"4.02","quantity":"1","cost":"4.02"},{"price":"4.03","quantityChange":"1","costChange":"4.03","quantity":"1","cost":"4.03"},{"price":"4.04","quantityChange":"1","costChange":"4.04","quantity":"1","cost":"4.04"},{"price":"4.05","quantityChange":"1","costChange":"4.05","quantity":"1","cost":"4.05"},{"price":"4.06","quantityChange":"1","costChange":"4.06","quantity":"1","cost":"4.06"},{"price":"4.07","quantityChange":"1","costChange":"4.07","quantity":"1","cost":"4.07"},{"price":"4.08","quantityChange":"1","costChange":"4.08","quantity":"1","cost":"4.08"},{"price":"4.09","quantityChange":"1","costChange":"4.09","quantity":"1","cost":"4.09"},{"price":"4.10","quantityChange":"1","costChange":"4.10","quantity":"1","cost":"4.10"},{"price":"4.11","quantityChange":"1","costChange":"4.11","quantity":"1","cost":"4.11"},{"price":"4.12","quantityChange":"1","costChange":"4.12","quantity":"1","cost":"4.12"},{"price":"4.13","quantityChange":"1","costChange":"4.13","quantity":"1","cost":"4.13"},{"price":"4.18","quantityChange":"1","costChange":"4.18","quantity":"1","cost":"4.18"},{"price":"4.91","quantityChange":"1","costChange":"4.91","quantity":"1","cost":"4.91"},{"price":"4.92","quantityChange":"1","costChange":"4.92","quantity":"1","cost":"4.92"},{"price":"4.93","quantityChange":"1","costChange":"4.93","quantity":"1","cost":"4.93"},{"price":"4.94","quantityChange":"1","costChange":"4.94","quantity":"1","cost":"4.94"},{"price":"4.95","quantityChange":"1","costChange":"4.95","quantity":"1","cost":"4.95"},{"price":"4.96","quantityChange":"1","costChange":"4.96","quantity":"1","cost":"4.96"},{"price":"4.97","quantityChange":"1","costChange":"4.97","quantity":"1","cost":"4.97"},{"price":"4.98","quantityChange":"1","costChange":"4.98","quantity":"1","cost":"4.98"},{"price":"4.99","quantityChange":"1","costChange":"4.99","quantity":"1","cost":"4.99"},{"price":"5.00","quantityChange":"1","costChange":"5.00","quantity":"1","cost":"5.00"},{"price":"5.06","quantityChange":"400","costChange":"2024.00","quantity":"400","cost":"2024.00"},{"price":"130.00","quantityChange":"1","costChange":"130.00","quantity":"1","cost":"130.00"},{"price":"140.00","quantityChange":"1","costChange":"140.00","quantity":"1","cost":"140.00"},{"price":"150.00","quantityChange":"10","costChange":"1500.00","quantity":"10","cost":"1500.00"}],"bid":[{"price":"18.21","quantityChange":"8","costChange":"145.68","quantity":"8","cost":"145.68"},{"price":"3.18","quantityChange":"10","costChange":"31.80","quantity":"10","cost":"31.80"},{"price":"3.17","quantityChange":"10","costChange":"31.70","quantity":"10","cost":"31.70"},{"price":"3.16","quantityChange":"10","costChange":"31.60","quantity":"10","cost":"31.60"},{"price":"3.15","quantityChange":"10","costChange":"31.50","quantity":"10","cost":"31.50"},{"price":"3.14","quantityChange":"10","costChange":"31.40","quantity":"10","cost":"31.40"},{"price":"3.13","quantityChange":"10","costChange":"31.30","quantity":"10","cost":"31.30"},{"price":"3.12","quantityChange":"10","costChange":"31.20","quantity":"10","cost":"31.20"},{"price":"3.11","quantityChange":"10","costChange":"31.10","quantity":"10","cost":"31.10"},{"price":"3.10","quantityChange":"10","costChange":"31.00","quantity":"10","cost":"31.00"},{"price":"3.09","quantityChange":"10","costChange":"30.90","quantity":"10","cost":"30.90"},{"price":"3.08","quantityChange":"110","costChange":"338.80","quantity":"110","cost":"338.80"},{"price":"3.07","quantityChange":"100","costChange":"307.00","quantity":"100","cost":"307.00"},{"price":"3.06","quantityChange":"100","costChange":"306.00","quantity":"100","cost":"306.00"},{"price":"3.05","quantityChange":"100","costChange":"305.00","quantity":"100","cost":"305.00"},{"price":"3.04","quantityChange":"100","costChange":"304.00","quantity":"100","cost":"304.00"},{"price":"3.03","quantityChange":"10","costChange":"30.30","quantity":"10","cost":"30.30"},{"price":"3.02","quantityChange":"10","costChange":"30.20","quantity":"10","cost":"30.20"},{"price":"3.01","quantityChange":"10","costChange":"30.10","quantity":"10","cost":"30.10"},{"price":"3.00","quantityChange":"10","costChange":"30.00","quantity":"10","cost":"30.00"},{"price":"2.99","quantityChange":"10","costChange":"29.90","quantity":"10","cost":"29.90"},{"price":"2.98","quantityChange":"10","costChange":"29.80","quantity":"10","cost":"29.80"},{"price":"2.97","quantityChange":"10","costChange":"29.70","quantity":"10","cost":"29.70"},{"price":"2.96","quantityChange":"10","costChange":"29.60","quantity":"10","cost":"29.60"},{"price":"2.95","quantityChange":"10","costChange":"29.50","quantity":"10","cost":"29.50"},{"price":"2.94","quantityChange":"10","costChange":"29.40","quantity":"10","cost":"29.40"},{"price":"2.93","quantityChange":"10","costChange":"29.30","quantity":"10","cost":"29.30"},{"price":"2.92","quantityChange":"10","costChange":"29.20","quantity":"10","cost":"29.20"},{"price":"2.91","quantityChange":"10","costChange":"29.10","quantity":"10","cost":"29.10"},{"price":"2.90","quantityChange":"10","costChange":"29.00","quantity":"10","cost":"29.00"},{"price":"2.89","quantityChange":"10","costChange":"28.90","quantity":"10","cost":"28.90"},{"price":"2.88","quantityChange":"10","costChange":"28.80","quantity":"10","cost":"28.80"},{"price":"2.87","quantityChange":"10","costChange":"28.70","quantity":"10","cost":"28.70"},{"price":"2.86","quantityChange":"10","costChange":"28.60","quantity":"10","cost":"28.60"},{"price":"2.85","quantityChange":"10","costChange":"28.50","quantity":"10","cost":"28.50"},{"price":"2.84","quantityChange":"10","costChange":"28.40","quantity":"10","cost":"28.40"},{"price":"2.83","quantityChange":"10","costChange":"28.30","quantity":"10","cost":"28.30"},{"price":"2.82","quantityChange":"10","costChange":"28.20","quantity":"10","cost":"28.20"},{"price":"2.81","quantityChange":"10","costChange":"28.10","quantity":"10","cost":"28.10"},{"price":"2.80","quantityChange":"10","costChange":"28.00","quantity":"10","cost":"28.00"},{"price":"2.79","quantityChange":"10","costChange":"27.90","quantity":"10","cost":"27.90"},{"price":"2.78","quantityChange":"10","costChange":"27.80","quantity":"10","cost":"27.80"},{"price":"2.77","quantityChange":"10","costChange":"27.70","quantity":"10","cost":"27.70"},{"price":"2.76","quantityChange":"20","costChange":"55.20","quantity":"20","cost":"55.20"},{"price":"2.75","quantityChange":"10","costChange":"27.50","quantity":"10","cost":"27.50"},{"price":"2.74","quantityChange":"10","costChange":"27.40","quantity":"10","cost":"27.40"},{"price":"2.73","quantityChange":"20","costChange":"54.60","quantity":"20","cost":"54.60"},{"price":"2.72","quantityChange":"10","costChange":"27.20","quantity":"10","cost":"27.20"},{"price":"2.71","quantityChange":"10","costChange":"27.10","quantity":"10","cost":"27.10"},{"price":"2.70","quantityChange":"10","costChange":"27.00","quantity":"10","cost":"27.00"},{"price":"2.69","quantityChange":"10","costChange":"26.90","quantity":"10","cost":"26.90"},{"price":"2.68","quantityChange":"10","costChange":"26.80","quantity":"10","cost":"26.80"},{"price":"2.67","quantityChange":"10","costChange":"26.70","quantity":"10","cost":"26.70"},{"price":"2.66","quantityChange":"10","costChange":"26.60","quantity":"10","cost":"26.60"},{"price":"2.65","quantityChange":"10","costChange":"26.50","quantity":"10","cost":"26.50"},{"price":"2.64","quantityChange":"10","costChange":"26.40","quantity":"10","cost":"26.40"},{"price":"2.63","quantityChange":"10","costChange":"26.30","quantity":"10","cost":"26.30"},{"price":"2.62","quantityChange":"10","costChange":"26.20","quantity":"10","cost":"26.20"},{"price":"2.61","quantityChange":"10","costChange":"26.10","quantity":"10","cost":"26.10"},{"price":"2.60","quantityChange":"10","costChange":"26.00","quantity":"10","cost":"26.00"},{"price":"2.59","quantityChange":"10","costChange":"25.90","quantity":"10","cost":"25.90"},{"price":"2.58","quantityChange":"10","costChange":"25.80","quantity":"10","cost":"25.80"},{"price":"2.57","quantityChange":"10","costChange":"25.70","quantity":"10","cost":"25.70"},{"price":"2.56","quantityChange":"10","costChange":"25.60","quantity":"10","cost":"25.60"},{"price":"2.55","quantityChange":"10","costChange":"25.50","quantity":"10","cost":"25.50"},{"price":"2.54","quantityChange":"10","costChange":"25.40","quantity":"10","cost":"25.40"},{"price":"2.53","quantityChange":"10","costChange":"25.30","quantity":"10","cost":"25.30"},{"price":"2.52","quantityChange":"10","costChange":"25.20","quantity":"10","cost":"25.20"},{"price":"2.51","quantityChange":"10","costChange":"25.10","quantity":"10","cost":"25.10"},{"price":"2.50","quantityChange":"10","costChange":"25.00","quantity":"10","cost":"25.00"},{"price":"2.49","quantityChange":"10","costChange":"24.90","quantity":"10","cost":"24.90"},{"price":"2.48","quantityChange":"200","costChange":"496.00","quantity":"200","cost":"496.00"},{"price":"2.47","quantityChange":"1","costChange":"2.47","quantity":"1","cost":"2.47"},{"price":"2.46","quantityChange":"1","costChange":"2.46","quantity":"1","cost":"2.46"},{"price":"2.45","quantityChange":"1","costChange":"2.45","quantity":"1","cost":"2.45"},{"price":"2.44","quantityChange":"1","costChange":"2.44","quantity":"1","cost":"2.44"},{"price":"2.43","quantityChange":"1","costChange":"2.43","quantity":"1","cost":"2.43"},{"price":"2.42","quantityChange":"1","costChange":"2.42","quantity":"1","cost":"2.42"},{"price":"2.41","quantityChange":"1","costChange":"2.41","quantity":"1","cost":"2.41"},{"price":"2.40","quantityChange":"1","costChange":"2.40","quantity":"1","cost":"2.40"},{"price":"2.39","quantityChange":"1","costChange":"2.39","quantity":"1","cost":"2.39"},{"price":"2.38","quantityChange":"1","costChange":"2.38","quantity":"1","cost":"2.38"},{"price":"2.37","quantityChange":"1","costChange":"2.37","quantity":"1","cost":"2.37"},{"price":"2.36","quantityChange":"1","costChange":"2.36","quantity":"1","cost":"2.36"},{"price":"2.35","quantityChange":"1","costChange":"2.35","quantity":"1","cost":"2.35"},{"price":"2.34","quantityChange":"1","costChange":"2.34","quantity":"1","cost":"2.34"},{"price":"2.33","quantityChange":"1","costChange":"2.33","quantity":"1","cost":"2.33"},{"price":"2.32","quantityChange":"1","costChange":"2.32","quantity":"1","cost":"2.32"},{"price":"2.31","quantityChange":"1","costChange":"2.31","quantity":"1","cost":"2.31"},{"price":"2.30","quantityChange":"1","costChange":"2.30","quantity":"1","cost":"2.30"},{"price":"2.29","quantityChange":"1","costChange":"2.29","quantity":"1","cost":"2.29"},{"price":"2.28","quantityChange":"1","costChange":"2.28","quantity":"1","cost":"2.28"},{"price":"2.27","quantityChange":"1","costChange":"2.27","quantity":"1","cost":"2.27"},{"price":"2.26","quantityChange":"1","costChange":"2.26","quantity":"1","cost":"2.26"},{"price":"2.25","quantityChange":"1","costChange":"2.25","quantity":"1","cost":"2.25"},{"price":"2.24","quantityChange":"1","costChange":"2.24","quantity":"1","cost":"2.24"},{"price":"2.23","quantityChange":"1","costChange":"2.23","quantity":"1","cost":"2.23"},{"price":"2.22","quantityChange":"1","costChange":"2.22","quantity":"1","cost":"2.22"},{"price":"2.21","quantityChange":"1","costChange":"2.21","quantity":"1","cost":"2.21"},{"price":"2.20","quantityChange":"1","costChange":"2.20","quantity":"1","cost":"2.20"}]},"nonce":0,"timestamp":1650124759447}'}
        return resp

    def _snapshot_response(self):
        resp = {"ask": [{"price": "6.00", "quantity": "1.000", "cost": "6.00", "accumulated": "6.00"}],
                "bid": [{"price": "50.50", "quantity": "-0.122", "cost": "-6.161", "accumulated": "-6.161"},
                        {"price": "5.00", "quantity": "1.000", "cost": "5.00", "accumulated": "-1.161"}],
                "totalAsk": "6", "totalBid": "-1.161"}
        return resp

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        public_url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL, domain=self.domain)
        url = f"{public_url}/{self.base_asset}/{self.quote_asset}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"symbol": "ETH/USDT", "baseCurrency": "620f2019-33c0-423b-8a9d-cde4d7f8ef7f",
                         "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5", "volume24h": "0.000000000000000000",
                         "volume7d": "0.000000000000000000", "change24h": "0.0000", "change7d": "0.0000",
                         "amount24h": "0.000000000000000000", "amount7d": "0.000000000000000000",
                         "lastPrice": "9.000000000000000000", "lastQuantity": "0.040000000000000000", "bestBid": "0",
                         "bestBidQuantity": "0", "bestAsk": "6", "bestAskQuantity": "1.000000000000000000",
                         "updateTimestamp": 1650039232793}

        mock_api.get(regex_url, body=json.dumps(mock_response))

        result: Dict[str, Decimal] = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices(
                trading_pairs=[self.trading_pair], domain=self.domain, throttler=self.throttler)
        )

        val = result[self.trading_pair]
        self.assertEqual(1, len(result))
        self.assertTrue(type(val) in [Decimal, float])
        self.assertEqual(Decimal("9.0"), val)

    @aioresponses()
    def test_get_all_mid_prices(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL, domain=self.domain)

        mock_response: List[Dict[str, Any]] = [
            {
                # Truncated Response
                "symbol": f"{self.base_asset}/{self.quote_asset}",
                "bestBid": "99",
                "bestAsk": "101",
            },
            {
                # Truncated Response for unrecognized pair
                "symbol": "BCC/BTC",  # TODO add guids here (.. if you want)
                "bestBid": "99",
                "bestAsk": "101",
            }
        ]

        mock_api.get(url, body=json.dumps(mock_response))

        result: Dict[str, Decimal] = self.async_run_with_timeout(
            self.data_source.get_all_mid_prices(domain=self.domain)
        )

        self.assertEqual(1, len(result))
        self.assertEqual(100, result[self.trading_pair])

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_api):
        LatokenAPIOrderBookDataSource._trading_pair_symbol_map = {}
        ticker_url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL, domain=self.domain)
        currency_url = utils.public_rest_url(path_url=CONSTANTS.CURRENCY_PATH_URL, domain=self.domain)
        pair_url = utils.public_rest_url(path_url=CONSTANTS.PAIR_PATH_URL, domain=self.domain)

        ticker_list: List[Dict] = [
            {"symbol": "REN/BTC", "baseCurrency": "8de4581d-3778-48e5-975e-511039a2aa6b",
             "quoteCurrency": "92151d82-df98-4d88-9a4d-284fa9eca49f", "volume24h": "0", "volume7d": "0",
             "change24h": "0", "change7d": "0", "amount24h": "0", "amount7d": "0", "lastPrice": "0",
             "lastQuantity": "0", "bestBid": "0", "bestBidQuantity": "0", "bestAsk": "0", "bestAskQuantity": "0",
             "updateTimestamp": 0},
            {"symbol": "NECC/USDT", "baseCurrency": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c",
             "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5", "volume24h": "0", "volume7d": "0",
             "change24h": "0", "change7d": "0", "amount24h": "0", "amount7d": "0", "lastPrice": "0",
             "lastQuantity": "0", "bestBid": "0", "bestBidQuantity": "0", "bestAsk": "0", "bestAskQuantity": "0",
             "updateTimestamp": 0}
        ]
        mock_api.get(ticker_url, body=json.dumps(ticker_list))
        currency_list: List[Dict] = [
            {"id": "8de4581d-3778-48e5-975e-511039a2aa6b", "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "REN", "tag": "REN", "description": "", "logo": "", "decimals": 18,
             "created": 1599223148171, "tier": 3, "assetClass": "ASSET_CLASS_UNKNOWN", "minTransferAmount": 0},
            {"id": "92151d82-df98-4d88-9a4d-284fa9eca49f", "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "Bitcoin", "tag": "BTC", "description": "", "logo": "",
             "decimals": 8, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
             "minTransferAmount": 0},
            {"id": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c", "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "Natural Eco Carbon Coin", "tag": "NECC", "description": "",
             "logo": "", "decimals": 18, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
             "minTransferAmount": 0},
            {"id": "0c3a106d-bde3-4c13-a26e-3fd2394529e5", "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "Tether USD ", "tag": "USDT", "description": "", "logo": "",
             "decimals": 6, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
             "minTransferAmount": 0}
        ]
        mock_api.get(currency_url, body=json.dumps(currency_list))
        # this list is truncated
        pair_list: List[Dict] = [
            {"id": "30a1032d-1e3e-4c28-8ca7-b60f3406fc3e", "status": "PAIR_STATUS_ACTIVE",
             "baseCurrency": "8de4581d-3778-48e5-975e-511039a2aa6b",
             "quoteCurrency": "92151d82-df98-4d88-9a4d-284fa9eca49f",
             "priceTick": "0.000000010000000000", "priceDecimals": 8,
             "quantityTick": "1.000000000000000000", "quantityDecimals": 0,
             "costDisplayDecimals": 8, "created": 1599249032243, "minOrderQuantity": "0",
             "maxOrderCostUsd": "999999999999999999", "minOrderCostUsd": "0",
             "externalSymbol": ""},
            {"id": "3140357b-e0da-41b2-b8f4-20314c46325b", "status": "PAIR_STATUS_ACTIVE",
             "baseCurrency": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c",
             "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5",
             "priceTick": "0.000010000000000000", "priceDecimals": 5,
             "quantityTick": "0.100000000000000000", "quantityDecimals": 1,
             "costDisplayDecimals": 5, "created": 1576052642564, "minOrderQuantity": "0",
             "maxOrderCostUsd": "999999999999999999", "minOrderCostUsd": "0",
             "externalSymbol": ""}
        ]

        mock_api.get(pair_url, body=json.dumps(pair_list))

        result: Dict[str] = self.async_run_with_timeout(
            coroutine=self.data_source.fetch_trading_pairs(domain=self.domain)
        )

        self.assertEqual(2, len(result))
        self.assertIn("REN-BTC", result)
        self.assertIn("NECC-USDT", result)
        self.assertNotIn("LA-BTC", result)

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
        path_url = f"{CONSTANTS.BOOK_PATH_URL}/{self.base_asset}/{self.quote_asset}"
        url = utils.public_rest_url(path_url=path_url, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_snapshot(self.trading_pair)
        )

        self.assertEqual(self._snapshot_response(), result)

    @aioresponses()
    def test_get_snapshot_catch_exception(self, mock_api):
        path_url = f"{CONSTANTS.BOOK_PATH_URL}/{self.base_asset}/{self.quote_asset}"
        url = utils.public_rest_url(path_url=path_url, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_snapshot(self.trading_pair)
            )

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        path_url = f"{CONSTANTS.BOOK_PATH_URL}/{self.base_asset}/{self.quote_asset}"
        url = utils.public_rest_url(path_url=path_url, domain=self.domain)
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

        self.assertGreater(result.snapshot_uid, 1)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        import aiohttp
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, self._successfully_subscribed_event(), message_type=aiohttp.WSMsgType.BINARY)
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, self._subscribed_events(), message_type=aiohttp.WSMsgType.BINARY)
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.text_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(3, len(sent_subscription_messages))

        connect, subscription_book, subscription_trade = sent_subscription_messages

        self.assertTrue(connect.startswith('CONNECT'))
        self.assertTrue(subscription_book.startswith('SUBSCRIBE'))
        self.assertTrue(subscription_trade.startswith('SUBSCRIBE'))
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

    # @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    # @patch("aiohttp.ClientSession.ws_connect")
    def test_subscribe_channels_raises_cancel_exception(self):  # , _, mock_ws: AsyncMock):
        # mock_ws = AsyncMock()
        # cancelled_error = asyncio.CancelledError
        # mock_ws.send.side_effect = cancelled_error
        # self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
        # self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.listening_task)
        mock_ws = AsyncMock()
        mock_ws.subscribe.side_effect = asyncio.CancelledError
        # mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        # self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, None)
        # self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, None)

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
        mock_queue = AsyncMock()
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
