from unittest import TestCase

from hummingbot.connector.exchange.latoken.latoken_order_book import LatokenOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class LatokenOrderBookTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "d8ae67f2-f954-4014-98c8-64b1ac334c64"
        cls.quote_asset = "0c3a106d-bde3-4c13-a26e-3fd2394529e5"
        cls.trading_pair = "ETH-USDT"
        cls.domain = "com"

    def test_snapshot_message_from_exchange(self):
        timestamp_ns = 1650122478008960306
        timestamp_s = timestamp_ns * 1e-9
        snapshot_message = LatokenOrderBook.snapshot_message_from_exchange(
            msg={"ask": [{"price": "6.00", "quantity": "1.000", "cost": "6.00", "accumulated": "6.00"}],
                 "bid": [{"price": "50.50", "quantity": "-0.122", "cost": "-6.161", "accumulated": "-6.161"},
                         {"price": "5.00", "quantity": "1.000", "cost": "5.00", "accumulated": "-1.161"}],
                 "totalAsk": "6", "totalBid": "-1.161"},
            timestamp=timestamp_ns,
            metadata={"trading_pair": self.trading_pair}
        )

        self.assertEqual(self.trading_pair, snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(timestamp_s, snapshot_message.timestamp)
        self.assertEqual(timestamp_s, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(2, len(snapshot_message.bids))
        self.assertEqual(50.5, snapshot_message.bids[0].price)
        self.assertEqual(-.122, snapshot_message.bids[0].amount)
        self.assertEqual(timestamp_s, snapshot_message.bids[0].update_id)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(6.0, snapshot_message.asks[0].price)
        self.assertEqual(1.0, snapshot_message.asks[0].amount)
        self.assertEqual(timestamp_s, snapshot_message.asks[0].update_id)

    def test_diff_message_from_exchange(self):
        timestamp_ns = 1650122478008960306
        timestamp_s = timestamp_ns * 1e-9

        diff_msg = LatokenOrderBook.diff_message_from_exchange(
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
                "timestamp": timestamp_s
            },
            timestamp=timestamp_ns,
            metadata={"trading_pair": self.trading_pair}
        )

        self.assertEqual(self.trading_pair, diff_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(timestamp_s, diff_msg.timestamp)
        self.assertEqual(timestamp_s, diff_msg.update_id)
        self.assertEqual(timestamp_s, diff_msg.first_update_id)
        self.assertEqual(-1, diff_msg.trade_id)
        self.assertEqual(2, len(diff_msg.bids))
        self.assertEqual(54464.69, diff_msg.bids[0].price)
        self.assertEqual(0.0, diff_msg.bids[0].amount)
        self.assertEqual(timestamp_s, diff_msg.bids[0].update_id)
        self.assertEqual(0, len(diff_msg.asks))
        # self.assertEqual(0.0026, diff_msg.asks[0].price)
        # self.assertEqual(100.0, diff_msg.asks[0].amount)
        # self.assertEqual(2, diff_msg.asks[0].update_id)

    def test_trade_message_from_exchange(self):
        timestamp_ns = 1650122478008960306
        timestamp_s = timestamp_ns * 1e-9
        timestamp_latoken = 1649760685161
        trade_update = {'id': '4e278949-00c8-4513-bddd-c69f4ff50fc6', 'timestamp': 1649760685161, 'baseCurrency': 'd8ae67f2-f954-4014-98c8-64b1ac334c64', 'quoteCurrency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5', 'price': '3.24', 'quantity': '10', 'cost': '32.4', 'makerBuyer': False, 'trading_pair': 'HBTEST-USDT', 'body_timestamp': 1650123503012}
        trade_message = LatokenOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": self.trading_pair},
            timestamp=timestamp_ns
        )

        self.assertEqual(self.trading_pair, trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(timestamp_s, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual(timestamp_latoken * 1e-3, trade_message.trade_id)
