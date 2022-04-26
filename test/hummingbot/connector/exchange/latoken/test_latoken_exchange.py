import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable, NamedTuple, Optional
from unittest import TestCase
from unittest.mock import patch, AsyncMock  # AsyncMock,
from typing import (
    Dict,
    List,
)

import ujson
import ast
import hummingbot.connector.exchange.latoken.latoken_utils as utils
from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.latoken import latoken_constants as CONSTANTS, latoken_utils
from hummingbot.connector.exchange.latoken.latoken_api_order_book_data_source import LatokenAPIOrderBookDataSource
from hummingbot.connector.exchange.latoken.latoken_exchange import LatokenExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import OrderState, InFlightOrder
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
)
from hummingbot.core.network_iterator import NetworkStatus


class LatokenExchangeTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "d8ae67f2-f954-4014-98c8-64b1ac334c64"
        cls.quote_asset = "0c3a106d-bde3-4c13-a26e-3fd2394529e5"
        cls.trading_pair = "ETH-USDT"
        cls.exchange_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = "tech"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None

        self.exchange = LatokenExchange(
            latoken_api_key="latoken_api_key",
            latoken_api_secret="latoken_api_secret",
            domain=self.domain,
            trading_pairs=[self.trading_pair],
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._latoken_time_synchronizer.logger().setLevel(1)
        self.exchange._latoken_time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        LatokenAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({f"{self.base_asset}/{self.quote_asset}": self.trading_pair})
        }

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        LatokenAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def _validate_auth_credentials_for_request(self, request_call_tuple: NamedTuple):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call_tuple,
            params_key="data"
        )

    def _validate_auth_credentials_for_post_request(self, request_call_tuple: NamedTuple):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call_tuple,
            params_key="data"
        )

    def _validate_auth_credentials_taking_parameters_from_argument(self, request_call_tuple: NamedTuple,
                                                                   params_key: str):
        json_object = request_call_tuple.kwargs[params_key]
        if json_object is not None:
            request_params = ast.literal_eval(json_object._value.decode("UTF-8"))
            if request_params is not None:
                if 'baseCurrency' in request_params:  # placeorder
                    self.assertIn("timestamp", request_params)
                elif len(request_params) == 1 and "id" in request_params:  # cancelorder
                    self.assertIn("id", request_params)  # todo other logic in our version, e.g. no timestamp for REST
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("X-LA-SIGNATURE", request_headers)
        self.assertIn("X-LA-APIKEY", request_headers)
        self.assertEqual("latoken_api_key", request_headers["X-LA-APIKEY"])

    def test_supported_order_types(self):  # todo needs to be verified from docs
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.LIMIT, supported_types)

    @aioresponses()
    def test_check_network_successful(self, mock_api):
        url = latoken_utils.public_rest_url(CONSTANTS.PING_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps({}))

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, status)

    @aioresponses()
    def test_check_network_unsuccessful(self, mock_api):
        url = latoken_utils.private_rest_url(CONSTANTS.PING_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=404)

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.NOT_CONNECTED, status)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        url = latoken_utils.private_rest_url(CONSTANTS.PING_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    @aioresponses()
    def test_create_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = latoken_utils.private_rest_url(CONSTANTS.ORDER_PLACE_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        creation_response = {
            "id": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
            "message": "order accepted for placing",
            "status": "SUCCESS",
            "error": "...",
            "errors": {
                "property1": "...",
                "property2": "..."
            }
        }

        mock_api.post(regex_url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_post_request(order_request[1][0])
        request_data = ast.literal_eval(order_request[1][0].kwargs["data"]._value.decode("UTF-8"))
        self.assertEqual(self.exchange_trading_pair, f"{request_data['baseCurrency']}/{request_data['quoteCurrency']}")
        self.assertEqual(CONSTANTS.SIDE_BUY, request_data["side"])
        self.assertEqual(LatokenExchange.latoken_order_type(OrderType.LIMIT), request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual("OID1", request_data["clientOrderId"])

        self.assertIn("OID1", self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual("OID1", create_event.order_id)
        self.assertEqual("XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX", create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created LIMIT BUY order OID1 for {Decimal('100.000000')} {self.trading_pair}."
            )
        )

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = latoken_utils.private_rest_url(CONSTANTS.ORDER_PLACE_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_post_request(order_request[1][0])

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='OID1', exchange_order_id=None)"
            )
        )

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = latoken_utils.private_rest_url(CONSTANTS.ORDER_PLACE_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("0.0001"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("0.0000001")))
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID2",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "WARNING",
                "Buy order amount 0 is lower than the minimum order size 0.01. The order will not be created."
            )
        )
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='OID1', exchange_order_id=None)"
            )
        )

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        exchange_order_id = "12345678-1234-1244-1244-123456789012"
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]

        url = latoken_utils.private_rest_url(CONSTANTS.ORDER_CANCEL_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "id": exchange_order_id,
            "message": "cancellation request successfully submitted",
            "status": "SUCCESS",
            "error": "",
            "errors": {}
        }

        mock_api.post(regex_url, body=json.dumps(response), callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_request(cancel_request[1][0])
        # request_params = cancel_request[1][0].kwargs["data"]
        # self.assertEqual(exchange_order_id, request_params["id"])
        # self.assertEqual(order.client_order_id, request_params["origClientOrderId"])

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully cancelled order {order.client_order_id}."
            )
        )

    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]

        url = latoken_utils.private_rest_url(CONSTANTS.ORDER_CANCEL_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400, callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_request(cancel_request[1][0])

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"There was an error when requesting cancellation of order {order.client_order_id}"
            )
        )

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        exchange_order_id = "4XXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"  # startswith 4!!!
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order1 = self.exchange.in_flight_orders["OID1"]

        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="5",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("90"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID2", self.exchange.in_flight_orders)
        order2 = self.exchange.in_flight_orders["OID2"]

        url = latoken_utils.private_rest_url(CONSTANTS.ORDER_CANCEL_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "id": exchange_order_id,
            "message": "cancellation request successfully submitted",
            "status": "SUCCESS",
            "error": "",
            "errors": {}
        }

        mock_api.post(regex_url, body=json.dumps(response))
        mock_api.post(regex_url, status=400)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        self.assertEqual(2, len(cancellation_results))
        self.assertEqual(CancellationResult(order1.client_order_id, True), cancellation_results[0])
        self.assertEqual(CancellationResult(order2.client_order_id, False), cancellation_results[1])

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order1.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully cancelled order {order1.client_order_id}."
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [0, 0, 0]

        url = latoken_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"serverTime": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(response["serverTime"] * 1e-3, self.exchange._latoken_time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        request_sent_event = asyncio.Event()

        url = latoken_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"code": -1121, "msg": "Dummy error"}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self._is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = latoken_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url,
                     exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = latoken_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response_balances = [
            {"id": "1e200836-a037-4475-825e-f202dd0b0e92",
             "status": "ACCOUNT_STATUS_ACTIVE",
             "type": "ACCOUNT_TYPE_SPOT",
             "timestamp": 1566408522980,
             "currency": "92151d82-df98-4d88-9a4d-284fa9eca49f",
             "available": "10",
             "blocked": "5"},
            {"id": "1e200836-a037-4475-825e-f202dd0b0e93",
             "status": "ACCOUNT_STATUS_ACTIVE",
             "type": "ACCOUNT_TYPE_SPOT",
             "timestamp": 1566408522980,
             "currency": "0d02fdfc-9555-4cd9-8398-006003033a9e",
             "available": "2000",
             "blocked": "0"}
        ]

        mock_api.get(regex_url, body=json.dumps(response_balances))

        first_currency_url = latoken_utils.private_rest_url(f"{CONSTANTS.CURRENCY_PATH_URL}/{response_balances[0]['currency']}", self.domain)
        first_currency_regex_url = re.compile(f"^{first_currency_url}".replace(".", r"\.").replace("?", r"\?"))
        first_currency = {"id": "92151d82-df98-4d88-9a4d-284fa9eca49f", "status": "CURRENCY_STATUS_ACTIVE",
                          "type": "CURRENCY_TYPE_CRYPTO", "name": "Bitcoin", "tag": "BTC", "description": "",
                          "logo": "", "decimals": 8,
                          "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
                          "minTransferAmount": 0}
        mock_api.get(first_currency_regex_url, body=json.dumps(first_currency))

        second_currency_url = latoken_utils.private_rest_url(f"{CONSTANTS.CURRENCY_PATH_URL}/{response_balances[1]['currency']}", self.domain)
        second_currency_regex_url = re.compile(f"^{second_currency_url}".replace(".", r"\.").replace("?", r"\?"))
        second_currency = {"id": "0d02fdfc-9555-4cd9-8398-006003033a9e", "status": "CURRENCY_STATUS_ACTIVE",
                           "type": "CURRENCY_TYPE_CRYPTO", "name": "LITECOIN", "tag": "LTC", "description": "",
                           "logo": "", "decimals": 8, "created": 1572912000000, "tier": 1,
                           "assetClass": "ASSET_CLASS_UNKNOWN", "minTransferAmount": 0}
        mock_api.get(second_currency_regex_url, body=json.dumps(second_currency))

        self.async_run_with_timeout(self.exchange._update_balances(), timeout=10)

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("2000"), available_balances["LTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])
        self.assertEqual(Decimal("2000"), total_balances["LTC"])

        second_response_balances = [
            {"id": "1e200836-a037-4475-825e-f202dd0b0e92",
             "status": "ACCOUNT_STATUS_ACTIVE",
             "type": "ACCOUNT_TYPE_SPOT",
             "timestamp": 1566408522980,
             "currency": "92151d82-df98-4d88-9a4d-284fa9eca49f",
             "available": "10",
             "blocked": "5"},
        ]

        mock_api.get(regex_url, body=json.dumps(second_response_balances))
        mock_api.get(first_currency_regex_url, body=json.dumps(first_currency))
        self.async_run_with_timeout(self.exchange._update_balances(), timeout=10)

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn("LTC", available_balances)
        self.assertNotIn("LTC", total_balances)
        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])

    @aioresponses()
    def test_update_balances_logs_errors(self, mock_api):
        url = latoken_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=401)
        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertTrue(
            self._is_logged("ERROR", "Error getting account balances from server")
        )

    @aioresponses()
    def test_update_order_fills_from_trades_triggers_filled_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = latoken_utils.private_rest_url(f"{CONSTANTS.TRADES_FOR_PAIR_PATH_URL}/{self.base_asset}/{self.quote_asset}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "id": order.exchange_order_id,
            "isMakerBuyer": False,
            "direction": "TRADE_DIRECTION_BUY",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "price": "10000.00",
            "quantity": "18.0000",
            "cost": "180000.000",
            "fee": "0.175584",
            "order": "98cea832-8e3f-4053-acaa-96d521f9411d",
            "timestamp": 1568396094704,
            "makerBuyer": False
        }

        trade_fill_non_tracked_order = {
            "id": "UNTRACKED_ORDER",
            "isMakerBuyer": False,
            "direction": "TRADE_DIRECTION_BUY",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "price": "10000.00",
            "quantity": "18.0000",
            "cost": "180000.000",
            "fee": "0.175584",
            "order": "98cea832-8e3f-4053-acaa-96d521f9411d",
            "timestamp": 1568396094704,
            "makerBuyer": False
        }
        mock_response = [trade_fill, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange.add_exchange_order_ids_from_market_recorder(
            {str(trade_fill_non_tracked_order["id"]): "OID99"})

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        trades_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        request_params = trades_request[1][0].kwargs["params"]
        self.assertEqual('100', request_params["limit"])
        self._validate_auth_credentials_for_request(trades_request[1][0])

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill["quantity"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(order.quote_asset, Decimal(trade_fill["fee"]))],
                         fill_event.trade_fee.flat_fees)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(float(trade_fill_non_tracked_order["timestamp"]) * 1e-3, fill_event.timestamp)
        self.assertEqual("OID99", fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(TradeType.BUY, fill_event.trade_type)
        self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["quantity"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(
                self.trading_pair.split('-')[-1],
                Decimal(trade_fill_non_tracked_order["fee"]))],
            fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        ))

    @aioresponses()
    def test_update_order_fills_request_parameters(self, mock_api):
        self.exchange._set_current_timestamp(0)
        self.exchange._last_poll_timestamp = -1

        url = latoken_utils.private_rest_url(f"{CONSTANTS.TRADES_FOR_PAIR_PATH_URL}/{self.base_asset}/{self.quote_asset}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = []
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        trades_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))

        request_params = trades_request[1][0].kwargs["params"]
        self.assertEqual('100', request_params["limit"])
        self.assertNotIn("startTime", request_params)
        self._validate_auth_credentials_for_request(trades_request[1][0])

        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        self.exchange._last_trades_poll_latoken_timestamp = 10
        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        trades_request = next(((key, value) for key, value in mock_api.requests.items() if key[1].human_repr().startswith(url)))
        request_params = trades_request[1][0].kwargs["params"]
        self.assertEqual('100', request_params["limit"])
        # self.assertEqual(10 * 1e3, request_params["startTime"])
        self._validate_auth_credentials_for_request(trades_request[1][0])

    @aioresponses()
    def test_update_order_fills_from_trades_with_repeated_fill_triggers_only_one_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        url = latoken_utils.private_rest_url(f"{CONSTANTS.TRADES_FOR_PAIR_PATH_URL}/{self.base_asset}/{self.quote_asset}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill_non_tracked_order = {
            "id": "UNTRACKED_ORDER",
            "isMakerBuyer": False,
            "direction": "TRADE_DIRECTION_BUY",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "price": "10000.00",
            "quantity": "18.0000",
            "cost": "180000.000",
            "fee": "0.175584",
            "order": "98cea832-8e3f-4053-acaa-96d521f9411d",
            "timestamp": 1568396094704,
            "makerBuyer": False
        }

        mock_response = [trade_fill_non_tracked_order, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange.add_exchange_order_ids_from_market_recorder(
            {str(trade_fill_non_tracked_order["id"]): "OID99"})

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        trades_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        request_params = trades_request[1][0].kwargs["params"]
        self.assertEqual('100', request_params["limit"])
        self._validate_auth_credentials_for_request(trades_request[1][0])

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(float(trade_fill_non_tracked_order["timestamp"]) * 1e-3, fill_event.timestamp)
        self.assertEqual("OID99", fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(TradeType.BUY, fill_event.trade_type)
        self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["quantity"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(self.trading_pair.split('-')[-1],
                        Decimal(trade_fill_non_tracked_order["fee"]))],
            fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        ))

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        client_order_id = "OID1"
        exchange_order_id = "100234"

        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        url = latoken_utils.private_rest_url(f"{CONSTANTS.GET_ORDER_PATH_URL}/{order.exchange_order_id}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "id": exchange_order_id,
            "side": "BUY",
            "condition": "GTC",
            "type": "LIMIT",
            "status": "ORDER_STATUS_CLOSED",  # TODO review this
            # "changeType": "ORDER_CHANGE_TYPE_FILLED",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "clientOrderId": client_order_id,
            "price": "10000.0",
            "quantity": "1.0",
            "cost": "100000.0",
            "filled": "1.0",  # note that filled == quantity filled!!
            "trader": "12345678-fca5-43ed-b0ea-b40fb48d3b0d",
            "timestamp": 3800014433,
            "creator": "USER",
            "creatorId": ""
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))
        # Simulate the order has been filled with a TradeUpdate
        order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        self.async_run_with_timeout(order.wait_until_completely_filled())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self.assertTrue(order_request[0][1].human_repr().endswith(order.exchange_order_id))
        self._validate_auth_credentials_for_request(order_request[1][0])

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(Decimal(0), buy_event.base_asset_amount)
        self.assertEqual(Decimal(0), buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    @aioresponses()
    def test_update_order_status_when_cancelled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        client_order_id = "OID1"
        exchange_order_id = "100234"

        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[client_order_id]

        url = latoken_utils.private_rest_url(f"{CONSTANTS.GET_ORDER_PATH_URL}/{order.exchange_order_id}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "id": exchange_order_id,
            "side": "BUY",
            "condition": "GTC",
            "type": "LIMIT",
            "status": "ORDER_STATUS_CANCELLED",
            "changeType": "ORDER_CHANGE_TYPE_CANCELLED",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "clientOrderId": client_order_id,
            "price": "10000.0",
            "quantity": "1.0",
            "cost": "100000.0",
            "filled": "230.0",
            "trader": "12345678-fca5-43ed-b0ea-b40fb48d3b0d",
            "timestamp": 3800014433,
            "creator": "USER",
            "creatorId": ""
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        # request_params = order_request[1][0].kwargs["params"]
        self.assertTrue(order_request[0][1].human_repr().endswith(order.exchange_order_id))
        self._validate_auth_credentials_for_request(order_request[1][0])

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged("INFO", f"Successfully cancelled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_update_order_status_when_failed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        client_order_id = "OID1"
        exchange_order_id = "100234"

        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = latoken_utils.private_rest_url(f"{CONSTANTS.GET_ORDER_PATH_URL}/{order.exchange_order_id}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "id": exchange_order_id,
            "side": "BUY",
            "condition": "GTC",
            "type": "LIMIT",
            "status": "ORDER_STATUS_REJECTED",
            # "changeType": "ORDER_CHANGE_TYPE_CANCELLED",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "clientOrderId": client_order_id,
            "price": "10000.0",
            "quantity": "1.0",
            "cost": "100000.0",
            "filled": "230.0",
            "trader": "12345678-fca5-43ed-b0ea-b40fb48d3b0d",
            "timestamp": 3800014433,
            "creator": "USER",
            "creatorId": ""
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        # request_params = order_request[1][0].kwargs["params"]
        self.assertTrue(order_request[0][1].human_repr().endswith(order.exchange_order_id))
        self._validate_auth_credentials_for_request(order_request[1][0])

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
                f" update_timestamp={float(order_status['timestamp'])* 1e-3}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order.client_order_id}', exchange_order_id='{order.exchange_order_id}')")
        )

    @aioresponses()
    def test_update_order_status_marks_order_as_failure_after_three_errors(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        client_order_id = "OID1"
        exchange_order_id = "100234"

        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = latoken_utils.private_rest_url(f"{CONSTANTS.GET_ORDER_PATH_URL}/{order.exchange_order_id}", self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=401)

        for i in range(self.exchange.MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES):
            self.async_run_with_timeout(self.exchange._update_order_status())

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        ticker_url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL, domain=self.domain)
        currency_url = utils.public_rest_url(path_url=CONSTANTS.CURRENCY_PATH_URL, domain=self.domain)
        pair_url = utils.public_rest_url(path_url=CONSTANTS.PAIR_PATH_URL, domain=self.domain)
        fee_schema_url = utils.public_rest_url(path_url=f"{CONSTANTS.FEES_PATH_URL}/{self.exchange_trading_pair }", domain=self.domain)

        ticker_list: List[Dict] = [
            {"symbol": self.trading_pair, "baseCurrency": self.base_asset,
             "quoteCurrency": self.quote_asset, "volume24h": "0", "volume7d": "0",
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
            {"id": self.base_asset, "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "REN", "tag": "REN", "description": "", "logo": "", "decimals": 18,
             "created": 1599223148171, "tier": 3, "assetClass": "ASSET_CLASS_UNKNOWN", "minTransferAmount": 0},
            {"id": self.quote_asset, "status": "CURRENCY_STATUS_ACTIVE",
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
             "baseCurrency": self.base_asset,
             "quoteCurrency": self.quote_asset,
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

        fee_schema = {
            "makerFee": "0.002200000000000000",
            "takerFee": "0.002800000000000000",
            "type": "FEE_SCHEME_TYPE_PERCENT_QUOTE",
            "take": "FEE_SCHEME_TAKE_PROPORTION"
        }

        mock_api.get(fee_schema_url, body=json.dumps(fee_schema))

        self.async_run_with_timeout(self.exchange._update_trading_rules())
        mapping = utils.create_full_mapping(ticker_list, currency_list, pair_list)
        trading_rule = self.exchange.trading_rules[self.trading_pair]
        self.assertEqual(self.trading_pair, trading_rule.trading_pair)
        self.assertEqual(mapping[0]["id"]["symbol"], self.trading_pair)
        self.assertEqual(Decimal(mapping[0]["minOrderQuantity"]),
                         trading_rule.min_notional_size)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        ticker_url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PATH_URL, domain=self.domain)
        currency_url = utils.public_rest_url(path_url=CONSTANTS.CURRENCY_PATH_URL, domain=self.domain)
        pair_url = utils.public_rest_url(path_url=CONSTANTS.PAIR_PATH_URL, domain=self.domain)
        # minOrderQuantity removed to cause error
        ticker_list: List[Dict] = [
            {"symbol": self.trading_pair,
             "baseCurrency": self.base_asset,
             "quoteCurrency": self.quote_asset, "volume24h": "0", "volume7d": "0",
             "change24h": "0", "change7d": "0", "amount24h": "0", "amount7d": "0", "lastPrice": "0",
             "lastQuantity": "0", "bestBid": "0", "bestBidQuantity": "0", "bestAsk": "0", "bestAskQuantity": "0",
             "updateTimestamp": 0},
            # {"symbol": "NECC/USDT", "baseCurrency": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c",
            #  "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5", "volume24h": "0", "volume7d": "0",
            #  "change24h": "0", "change7d": "0", "amount24h": "0", "amount7d": "0", "lastPrice": "0",
            #  "lastQuantity": "0", "bestBid": "0", "bestBidQuantity": "0", "bestAsk": "0", "bestAskQuantity": "0",
            #  "updateTimestamp": 0}
        ]
        mock_api.get(ticker_url, body=json.dumps(ticker_list))
        currency_list: List[Dict] = [
            {"id": self.base_asset, "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "REN", "tag": "REN", "description": "", "logo": "", "decimals": 18,
             "created": 1599223148171, "tier": 3, "assetClass": "ASSET_CLASS_UNKNOWN", "minTransferAmount": 0},
            {"id": self.quote_asset, "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "Bitcoin", "tag": "BTC", "description": "", "logo": "",
             "decimals": 8, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
             "minTransferAmount": 0},
            # {"id": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c", "status": "CURRENCY_STATUS_ACTIVE",
            #  "type": "CURRENCY_TYPE_CRYPTO", "name": "Natural Eco Carbon Coin", "tag": "NECC", "description": "",
            #  "logo": "", "decimals": 18, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
            #  "minTransferAmount": 0},
            # {"id": "0c3a106d-bde3-4c13-a26e-3fd2394529e5", "status": "CURRENCY_STATUS_ACTIVE",
            #  "type": "CURRENCY_TYPE_CRYPTO", "name": "Tether USD ", "tag": "USDT", "description": "", "logo": "",
            #  "decimals": 6, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
            #  "minTransferAmount": 0}
        ]
        mock_api.get(currency_url, body=json.dumps(currency_list))
        # this list is truncated
        pair_list: List[Dict] = [
            {"id": "30a1032d-1e3e-4c28-8ca7-b60f3406fc3e", "status": "PAIR_STATUS_ACTIVE",
             "baseCurrency": self.base_asset,
             "quoteCurrency": self.quote_asset,
             "priceTick": "0.000000010000000000", "priceDecimals": 8,
             "quantityTick": "1.000000000000000000", "quantityDecimals": 0,
             "costDisplayDecimals": 8, "created": 1599249032243,
             # "minOrderQuantity": "0",
             "maxOrderCostUsd": "999999999999999999", "minOrderCostUsd": "0",
             "externalSymbol": ""},
            # {"id": "3140357b-e0da-41b2-b8f4-20314c46325b", "status": "PAIR_STATUS_ACTIVE",
            #  "baseCurrency": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c",
            #  "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5",
            #  "priceTick": "0.000010000000000000", "priceDecimals": 5,
            #  "quantityTick": "0.100000000000000000", "quantityDecimals": 1,
            #  "costDisplayDecimals": 5, "created": 1576052642564, "minOrderQuantity": "0",
            #  "maxOrderCostUsd": "999999999999999999", "minOrderCostUsd": "0",
            #  "externalSymbol": ""}
        ]

        mock_api.get(pair_url, body=json.dumps(pair_list))

        self.async_run_with_timeout(self.exchange._update_trading_rules())
        pairs = latoken_utils.create_full_mapping(ticker_list, currency_list, pair_list)

        self.assertEqual(0, len(self.exchange.trading_rules))
        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {pairs[0]}. Skipping.")
        )

    def test_user_stream_update_for_new_order(self):
        client_order_id = "OID1"
        exchange_order_id = "100234"

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[client_order_id]
        event_message = {'cmd': 'MESSAGE',
                         'headers': {'destination': '/user/2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f/v1/order',
                                     'message-id': '1cfd6907-c566-4a08-aad7-272f2610cefa', 'content-length': '654',
                                     'subscription': '3'},
                         'body': '{"payload":[{"id":"' + exchange_order_id + '","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f","changeType":"ORDER_CHANGE_TYPE_PLACED","status":"ORDER_STATUS_PLACED","side":"ORDER_SIDE_BUY","condition":"ORDER_CONDITION_GOOD_TILL_CANCELLED","type":"ORDER_TYPE_LIMIT","baseCurrency":"' + self.base_asset + '","quoteCurrency":"' + self.quote_asset + '","clientOrderId":"' + client_order_id + '","price":"3.2","quantity":"10","cost":"32.000000000000000000","filled":"0","deltaFilled":"0","timestamp":1650271892385,"creator":"ORDER_CREATOR_USER","creatorId":""}],"nonce":1,"timestamp":1650271892393}'}

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, event.timestamp)
        self.assertEqual(order.order_type, event.type)
        self.assertEqual(order.trading_pair, event.trading_pair)
        self.assertEqual(order.amount, event.amount)
        self.assertEqual(order.price, event.price)
        self.assertEqual(order.client_order_id, event.order_id)
        self.assertEqual(order.exchange_order_id, event.exchange_order_id)
        self.assertTrue(order.is_open)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created {order.order_type.name.upper()} {order.trade_type.name.upper()} order "
                f"{order.client_order_id} for {order.amount} {order.trading_pair}."
            )
        )

    def test_user_stream_update_for_cancelled_order(self):
        client_order_id = "OID1"
        exchange_order_id = "100234"
        price = "100.0"
        amount = "10"
        changeType = "ORDER_CHANGE_TYPE_CANCELLED"
        status = "ORDER_STATUS_CANCELLED"
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
        )
        order = self.exchange.in_flight_orders[client_order_id]

        filled = "10"
        delta_filled = filled
        cost = "32.000000000000000000"
        # quote = self.trading_pair.split('-')[-1]
        event_message = {'cmd': 'MESSAGE',
                         'headers': {'destination': '/user/2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f/v1/order',
                                     'message-id': '1cfd6907-c566-4a08-aad7-272f2610cefa', 'content-length': '654',
                                     'subscription': '3'}, 'body': '{"payload":[{"id":"' + exchange_order_id + '","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f","changeType":"' + changeType + '","status":"' + status + '","side":"ORDER_SIDE_BUY","condition":"ORDER_CONDITION_GOOD_TILL_CANCELLED","type":"ORDER_TYPE_LIMIT","baseCurrency":"' + self.base_asset + '","quoteCurrency":"' + self.quote_asset + '","clientOrderId":"' + client_order_id + '","price":"' + price + '","quantity":"' + amount + '","cost":"' + cost + '","filled":"' + filled + '","deltaFilled":"' + delta_filled + '","timestamp":1650271892385,"creator":"ORDER_CREATOR_USER","creatorId":""}],"nonce":1,"timestamp":1650271892393}'}

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self._is_logged("INFO", f"Successfully cancelled order {order.client_order_id}.")
        )

    def test_user_stream_update_for_order_fill(self):
        client_order_id = "OID1"
        exchange_order_id = "100234"
        price = "100.0"
        amount = "10"
        changeType = "ORDER_CHANGE_TYPE_FILLED"
        status = "ORDER_STATUS_PLACED"
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
        )
        order = self.exchange.in_flight_orders[client_order_id]
        filled = "10"
        delta_filled = filled
        cost = "32.000000000000000000"
        quote = self.trading_pair.split('-')[-1]
        event_message = {'cmd': 'MESSAGE',
                         'headers': {'destination': '/user/2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f/v1/order',
                                     'message-id': '1cfd6907-c566-4a08-aad7-272f2610cefa', 'content-length': '654',
                                     'subscription': '3'},
                         'body': '{"payload":[{"id":"' + exchange_order_id + '","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f","changeType":"' + changeType + '","status":"' + status + '","side":"ORDER_SIDE_BUY","condition":"ORDER_CONDITION_GOOD_TILL_CANCELLED","type":"ORDER_TYPE_LIMIT","baseCurrency":"' + self.base_asset + '","quoteCurrency":"' + self.quote_asset + '","clientOrderId":"' + client_order_id + '","price":"' + price + '","quantity":"' + amount + '","cost":"' + cost + '","filled":"' + filled + '","deltaFilled":"' + delta_filled + '","timestamp":1650271892385,"creator":"ORDER_CREATOR_USER","creatorId":""}],"nonce":1,"timestamp":1650271892393}'}

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(price), fill_event.price)
        self.assertEqual(Decimal(amount), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            # TokenAmount(quote, Decimal(cost))],
            TokenAmount(quote, Decimal("0.0"))],
            fill_event.trade_fee.flat_fees)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(Decimal(delta_filled) * Decimal(price), buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    def test_user_stream_update_for_order_failure(self):
        client_order_id = "OID1"
        exchange_order_id = "100234"
        price = "100.0"
        amount = "10"
        changeType = "ORDER_CHANGE_TYPE_REJECTED"
        status = "ORDER_STATUS_REJECTED"
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
        )
        order = self.exchange.in_flight_orders[client_order_id]

        filled = "10"
        delta_filled = filled
        cost = "32.000000000000000000"
        # quote = self.trading_pair.split('-')[-1]
        event_message = {'cmd': 'MESSAGE',
                         'headers': {'destination': '/user/2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f/v1/order',
                                     'message-id': '1cfd6907-c566-4a08-aad7-272f2610cefa', 'content-length': '654',
                                     'subscription': '3'},
                         'body': '{"payload":[{"id":"' + exchange_order_id + '","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f","changeType":"' + changeType + '","status":"' + status + '","side":"ORDER_SIDE_BUY","condition":"ORDER_CONDITION_GOOD_TILL_CANCELLED","type":"ORDER_TYPE_LIMIT","baseCurrency":"' + self.base_asset + '","quoteCurrency":"' + self.quote_asset + '","clientOrderId":"' + client_order_id + '","price":"' + price + '","quantity":"' + amount + '","cost":"' + cost + '","filled":"' + filled + '","deltaFilled":"' + delta_filled + '","timestamp":1650271892385,"creator":"ORDER_CREATOR_USER","creatorId":""}],"nonce":1,"timestamp":1650271892393}'}

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_failure)
        self.assertTrue(order.is_done)

    @aioresponses()
    def test_user_stream_balance_update(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        base, _ = self.trading_pair.split('-')
        # event_message = {'cmd': 'MESSAGE', 'headers': {'destination': '/user/2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f/v1/account', 'message-id': 'eb428773-8eaa-40ae-a3e3-b6eb2d1454ae', 'content-length': '3597', 'subscription': '0'}, 'body': '{"payload":[{"id":"6b4d1e11-1d0b-418c-a660-b9a30ef56529","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_WALLET","timestamp":1648225456689,"currency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","available":"0.000000000000000000","blocked":"0.000000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"120bd79c-b373-4b19-8a85-ff2f7ac6851f","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_WALLET","timestamp":1648565813047,"currency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","available":"100000.000000000000000000","blocked":"0.000000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"7f7cb388-29cf-42b9-82ff-d2d5f4ab5d37","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_SPOT","timestamp":1650143903923,"currency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","available":"188.000000000000000000","blocked":"967.000000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"5d5906d8-c57f-47aa-95ad-fac4c80244e9","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_SPOT","timestamp":1650143891138,"currency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5","available":"15490.880457640000000000","blocked":"7233.979512760000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"a056534b-8221-47a8-8065-e011785ae16c","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_WALLET","timestamp":1649941334078,"currency":"91d59537-6c02-4fab-bb7a-2935a94e3c76","available":"0.000000000000000000","blocked":"0.000000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"21b42250-b1b4-4f27-926d-07ede443a3c2","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_WALLET","timestamp":1649762158395,"currency":"f6873f7e-c962-403f-a586-5d5630b4370c","available":"1.000000000000000000","blocked":"0.000000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"25e58464-a178-4f0f-867a-6f05b0485583","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_WALLET","timestamp":1649772494710,"currency":"c442748c-882e-43c9-9ec4-9a6dd22531ab","available":"1.000000000000000000","blocked":"0.000000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"bdc1e6d1-cf8d-44b9-a73b-24f94a7702a9","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_WALLET","timestamp":1649941354504,"currency":"67e03c14-cb58-4840-9e64-46db83187a17","available":"0.000000000000000000","blocked":"0.000000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"1768cbd7-2776-4ff7-8808-22d3cb1f1942","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_SPOT","timestamp":1649865650502,"currency":"92151d82-df98-4d88-9a4d-284fa9eca49f","available":"0","blocked":"0","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"44d36460-46dc-4828-a17c-63b1a047b054","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_SPOT","timestamp":1650120265819,"currency":"620f2019-33c0-423b-8a9d-cde4d7f8ef7f","available":"34.001000000000000000","blocked":"0.999000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"892aeef9-0221-4a30-b7e6-23db08d0ea1f","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_WALLET","timestamp":1649946354097,"currency":"620f2019-33c0-423b-8a9d-cde4d7f8ef7f","available":"15.000000000000000000","blocked":"0.000000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"},{"id":"432c56bf-f8a2-4967-b3d2-63f48d7d9bb4","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_WALLET","timestamp":1650025854715,"currency":"92151d82-df98-4d88-9a4d-284fa9eca49f","available":"5.000000000000000000","blocked":"0.000000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"}],"nonce":0,"timestamp":1650265966821}'}
        event_message = {'cmd': 'MESSAGE',
                         'headers': {'destination': '/user/2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f/v1/account',
                                     'message-id': 'eb428773-8eaa-40ae-a3e3-b6eb2d1454ae', 'content-length': '3597',
                                     'subscription': '0'},
                         'body': '{"payload":[{"id":"6b4d1e11-1d0b-418c-a660-b9a30ef56529","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_SPOT","timestamp":1648225456689,"currency":"d8ae67f2-f954-4014-98c8-64b1ac334c64","available":"10.000000000000000000","blocked":"1.000000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"}],"nonce":0,"timestamp":1650265966821}'}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]

        body = ujson.loads(event_message["body"])
        currency_url = utils.public_rest_url(path_url=f"{CONSTANTS.CURRENCY_PATH_URL}/{body['payload'][0]['currency']}", domain=self.domain)
        currency_list: Dict = {"id": "d8ae67f2-f954-4014-98c8-64b1ac334c64",
                               "currency": "92151d82-df98-4d88-9a4d-284fa9eca49f", "status": "CURRENCY_STATUS_ACTIVE",
                               "type": "CURRENCY_TYPE_CRYPTO", "name": base, "tag": base, "description": "", "logo": "",
                               "decimals": 18,
                               "created": 1599223148171, "tier": 3, "assetClass": "ASSET_CLASS_UNKNOWN",
                               "minTransferAmount": 0}

        mock_api.get(currency_url, body=json.dumps(currency_list))
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), self.exchange.available_balances[base])
        self.assertEqual(Decimal("11"), self.exchange.get_balance(base))

    def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
        ))
        orders.append(InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="EOID2",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            initial_state=OrderState.CANCELLED,
            creation_timestamp=1640001112.223,
        ))
        orders.append(InFlightOrder(
            client_order_id="OID3",
            exchange_order_id="EOID3",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            initial_state=OrderState.FILLED,
            creation_timestamp=1640001112.223,
        ))
        orders.append(InFlightOrder(
            client_order_id="OID4",
            exchange_order_id="EOID4",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            initial_state=OrderState.FAILED,
            creation_timestamp=1640001112.223,
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn("OID1", self.exchange.in_flight_orders)
        self.assertNotIn("OID2", self.exchange.in_flight_orders)
        self.assertNotIn("OID3", self.exchange.in_flight_orders)
        self.assertNotIn("OID4", self.exchange.in_flight_orders)
