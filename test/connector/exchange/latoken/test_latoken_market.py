import asyncio
import contextlib
import logging
import os
import sys
import time
import unittest
import random
from decimal import Decimal
from os.path import join, realpath
from typing import (
    List,
    Optional,
)
from hummingbot.core.data_type.in_flight_order import OrderState
import conf
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderType,
    TradeType,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderCancelledEvent,
    BuyOrderCompletedEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
)
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.latoken.latoken_exchange import LatokenExchange
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
# logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
logging.basicConfig(level=METRICS_LOG_LEVEL)
API_KEY = conf.latoken_api_key
API_SECRET = conf.latoken_secret_key
trading_pair = "ETH-USDT"
base_asset, quote_asset = trading_pair.split("-")
domain = "tech"


class LatokenExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
    ]

    market: LatokenExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: LatokenExchange = LatokenExchange(
            API_KEY,
            API_SECRET,
            trading_pairs=[trading_pair],
            domain=domain
        )
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../latoken_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        limit_fee: TradeFeeBase = self.market.get_fee(base_asset, quote_asset, OrderType.LIMIT,
                                                      TradeType.BUY, Decimal("1"), Decimal("1"))
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: TradeFeeBase = self.market.get_fee(base_asset, quote_asset, OrderType.MARKET,
                                                       TradeType.BUY, Decimal("1"))
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)

    def test_minimum_order_size(self):
        amount = Decimal("0.0001")
        quantized_amount = self.market.quantize_order_amount(trading_pair, amount)
        self.assertEqual(quantized_amount, Decimal("0"))

    def test_get_balance(self):
        balance = self.market.get_balance(quote_asset)
        self.assertGreater(balance, 10)

    def test_limit_buy(self):
        amount: Decimal = Decimal("0.04")
        current_ask_price: Decimal = self.market.get_price(trading_pair, False)
        # no fill
        bid_price: Decimal = Decimal("0.9") * current_ask_price
        quantize_ask_price: Decimal = self.market.quantize_order_price(
            trading_pair,
            bid_price
        )

        order_id = self.market.buy(
            trading_pair,
            amount,
            OrderType.LIMIT,
            quantize_ask_price
        )

        # Wait for order creation event
        self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))

        # Cancel order. Automatically asserts that order is tracked
        self.market.cancel(trading_pair, order_id)

        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(order_cancelled_event.order_id, order_id)
        # # Reset the logs
        self.market_logger.clear()

    def test_limit_sell(self):
        current_ask_price: Decimal = self.market.get_price(trading_pair, False)
        # for no fill
        ask_price: Decimal = Decimal("1.1") * current_ask_price
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair,
                                                                       ask_price)
        amount: Decimal = Decimal("0.02")
        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT,
                                    quantize_ask_price)
        # Wait for order creation event
        self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))

        # Cancel order. Automatically asserts that order is tracked
        self.market.cancel(trading_pair, order_id)

        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent))

        self.assertEqual(order_cancelled_event.order_id, order_id)

        # Reset the logs
        self.market_logger.clear()

    # WARNING AUTOMATICALLY EXECUTES ORDER
    def test_execute_limit_buy(self):
        amount: Decimal = Decimal("0.04")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair,
                                                                      amount)

        # bid_entries = self.market.order_books[trading_pair].bid_entries()
        ask_entries = self.market.order_books[trading_pair].ask_entries()
        # most_top_bid = next(bid_entries)
        most_top_ask = next(ask_entries)
        # bid_price: Decimal = Decimal(most_top_bid.price)
        # quantize_bid_price = self.market.quantize_order_price(trading_pair, bid_price) * Decimal("1.1")

        ask_price: Decimal = Decimal(most_top_ask.price)
        min_price_increment = self.market.trading_rules[trading_pair].min_price_increment
        ask_price_to_be_lifted = self.market.quantize_order_price(trading_pair, ask_price - min_price_increment)

        order_id_sell = self.market.sell(trading_pair, quantized_amount, OrderType.LIMIT, ask_price_to_be_lifted)
        print(order_id_sell)
        _ = self.run_parallel(
            self.market_logger.wait_for(SellOrderCreatedEvent))

        order_id_buy = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, ask_price_to_be_lifted)

        # [order_completed_event_sell] = self.run_parallel(
        #     self.market_logger.wait_for(SellOrderCompletedEvent))

        order_completed_event_buy, order_completed_event_sell = self.run_parallel(
            self.market_logger.wait_for(BuyOrderCompletedEvent), self.market_logger.wait_for(SellOrderCompletedEvent))

        order_completed_event_buy: BuyOrderCompletedEvent = order_completed_event_buy
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id_buy, order_completed_event_buy.order_id)
        self.assertAlmostEqual(quantized_amount,
                               order_completed_event_buy.base_asset_amount)
        self.assertEqual(base_asset, order_completed_event_buy.base_asset)
        self.assertEqual(quote_asset, order_completed_event_buy.quote_asset)
        self.assertAlmostEqual(base_amount_traded,
                               order_completed_event_buy.base_asset_amount + order_completed_event_sell.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded,
                               order_completed_event_buy.quote_asset_amount + order_completed_event_sell.quote_asset_amount)
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id_buy
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    # WARNING AUTOMATICALLY EXECUTES ORDER
    def test_execute_limit_sell(self):
        amount: Decimal = Decimal("0.04")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair,
                                                                      amount)

        bid_entries = self.market.order_books[trading_pair].bid_entries()
        # ask_entries = self.market.order_books[trading_pair].ask_entries()
        most_top_bid = next(bid_entries)
        # most_top_ask = next(ask_entries)
        # bid_price: Decimal = Decimal(most_top_bid.price)
        # quantize_bid_price = self.market.quantize_order_price(trading_pair, bid_price) * Decimal("1.1")

        bid_price: Decimal = Decimal(most_top_bid.price)
        min_price_increment = self.market.trading_rules[trading_pair].min_price_increment
        bid_price_to_be_lifted = self.market.quantize_order_price(trading_pair, bid_price + min_price_increment)

        order_id_sell = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, bid_price_to_be_lifted)
        print(order_id_sell)
        _ = self.run_parallel(
            self.market_logger.wait_for(BuyOrderCreatedEvent))

        order_id_buy = self.market.sell(trading_pair, quantized_amount, OrderType.LIMIT, bid_price_to_be_lifted)

        # [order_completed_event_sell] = self.run_parallel(
        #     self.market_logger.wait_for(SellOrderCompletedEvent))

        order_completed_event_buy, order_completed_event_sell = self.run_parallel(
            self.market_logger.wait_for(SellOrderCompletedEvent), self.market_logger.wait_for(BuyOrderCompletedEvent))

        order_completed_event_buy: SellOrderCompletedEvent = order_completed_event_buy
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id_buy, order_completed_event_buy.order_id)
        self.assertAlmostEqual(quantized_amount,
                               order_completed_event_buy.base_asset_amount)
        self.assertEqual(base_asset, order_completed_event_buy.base_asset)
        self.assertEqual(quote_asset, order_completed_event_buy.quote_asset)
        self.assertAlmostEqual(base_amount_traded,
                               order_completed_event_buy.base_asset_amount + order_completed_event_sell.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded,
                               order_completed_event_buy.quote_asset_amount + order_completed_event_sell.quote_asset_amount)
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id_buy
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    # needs manual execution
    # def test_execute_limit_sell(self):
    #     amount: Decimal = Decimal(0.02)
    #     quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair,
    #                                                                   amount)
    #     ask_entries = self.market.order_books[trading_pair].ask_entries()
    #     most_top_ask = next(ask_entries)
    #     ask_price: Decimal = Decimal(most_top_ask.price)
    #
    #     quantize_ask_price = self.market.quantize_order_price(trading_pair, ask_price) * Decimal("0.9")
    #
    #     order_id = self.market.sell(trading_pair,
    #                                 quantized_amount,
    #                                 OrderType.LIMIT,
    #                                 quantize_ask_price,
    #                                 )
    #     [order_completed_event] = self.run_parallel(
    #         self.market_logger.wait_for(SellOrderCompletedEvent))
    #
    #     order_completed_event: SellOrderCompletedEvent = order_completed_event
    #     trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
    #                                             if isinstance(t, OrderFilledEvent)]
    #     base_amount_traded: Decimal = sum(t.amount for t in trade_events)
    #     quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)
    #
    #     self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
    #     self.assertEqual(order_id, order_completed_event.order_id)
    #     self.assertAlmostEqual(quantized_amount,
    #                            order_completed_event.base_asset_amount)
    #     self.assertEqual(base_asset, order_completed_event.base_asset)
    #     self.assertEqual(quote_asset, order_completed_event.quote_asset)
    #     self.assertAlmostEqual(base_amount_traded,
    #                            order_completed_event.base_asset_amount)
    #     self.assertAlmostEqual(quote_amount_traded,
    #                            order_completed_event.quote_asset_amount)
    #     self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
    #                          for event in self.market_logger.event_log]))
    #     # Reset the logs
    #     self.market_logger.clear()

    # WARNING NEEDS MANUAL EXECUTIONS IN WEB INTERFACE!!! OTHERWISE THIS CAUSES TIMEOUTS! # TODO fix issue in this unit test, last line before finally fails for now, meaning issue with latoken integration
    def test_orders_saving_and_restoration(self):
        self.tearDownClass()
        self.setUpClass()
        self.setUp()

        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None

        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()
        session = sql.get_new_session()
        try:
            self.assertEqual(0, len(self.market.tracking_states))

            amount: Decimal = Decimal("0.04")
            current_ask_price: Decimal = self.market.get_price(trading_pair, False)
            bid_price: Decimal = Decimal("0.9") * current_ask_price
            quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)
            order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT, quantize_ask_price)

            [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
            order_created_event: BuyOrderCreatedEvent = order_created_event
            self.assertEqual(order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.market.tracking_states))
            self.assertEqual(order_id, list(self.market.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.market)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.market, session=session)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.clock.remove_iterator(self.market)
            for event_tag in self.events:
                self.market.remove_listener(event_tag, self.market_logger)
            self.market: LatokenExchange = LatokenExchange(
                API_KEY,
                API_SECRET,
                trading_pairs=[trading_pair],
                domain=domain
            )
            for event_tag in self.events:
                self.market.add_listener(event_tag, self.market_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
            recorder.start()

            saved_market_states = recorder.get_market_states(config_path, self.market, session=session)
            self.clock.add_iterator(self.market)
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            self.market.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states))
            # Cancel the order and verify that the change is saved.
            self.run_parallel(asyncio.sleep(5.0))
            self.market.cancel(trading_pair, order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market, session=session)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            session.close()
            recorder.stop()
            self.setUpClass()

    def test_cancel_all(self):
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal("0.04")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.9"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.1"))

        order_ids = []
        order_count = 1  # order_count = 100
        time_out_open_orders = 10
        time_out_cancellations = 20  # seconds
        for i in range(order_count):
            x = self.market.trading_rules[trading_pair].min_price_increment * random.randint(0, 9) * quantize_bid_price
            print(f"to be fixed {x}")  # TODO fix this
            order_id_buy = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)
            order_id_sell = self.market.sell(trading_pair, quantized_amount, OrderType.LIMIT, quantize_ask_price)
            order_ids.append(order_id_buy)
            order_ids.append(order_id_sell)

        self.run_parallel(asyncio.sleep(time_out_open_orders))

        all_orders_opened = [self.market.in_flight_orders[order_id] for order_id in order_ids]
        are_all_orders_opened = [order.current_state == OrderState.OPEN for order in all_orders_opened]
        self.assertTrue(all(are_all_orders_opened))
        are_all_orders_with_exchange_id = [order.exchange_order_id is not None for order in all_orders_opened]
        self.assertTrue(all(are_all_orders_with_exchange_id))
        log = logging.getLogger("test_cancel_all")

        log.debug(f"{time.time()} STARTING TO CANCEL ALL")
        [cancellation_results] = self.run_parallel(self.market.cancel_all(time_out_cancellations))
        log.debug(f"{time.time()} CANCELLED ALL (?)")
        # all_failing_order_ids = [order_id not in self.market.all_orders for order_id in order_ids]
        # failing_order_ids = [order_id for order_id in order_ids if order_id not in self.market.all_orders]
        # failing_order_ids = [self.market.all_orders[order_id].exchange_order_id is None for order_id in order_ids]
        are_all_orders_cancelled = [self.market.all_orders[order_id].current_state == OrderState.CANCELLED for order_id in order_ids]
        self.assertTrue(all(are_all_orders_cancelled))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)
