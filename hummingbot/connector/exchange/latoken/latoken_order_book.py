from typing import Dict, Optional

from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)


class LatokenOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: int,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)

        ask_book = msg.pop("ask")  # need list of tuples for processing correctly in orderbook
        ask_list = []
        for ask_row in ask_book:
            ask_list.append((ask_row['price'], ask_row['quantity']))
        msg["asks"] = ask_list

        bid_book = msg.pop("bid")  # need list of tuples for processing correctly in orderbook
        bid_list = []
        for bid_row in bid_book:
            bid_list.append((bid_row['price'], bid_row['quantity']))
        msg["bids"] = bid_list

        msg["update_id"] = timestamp  # ts in nanosecond

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, msg, timestamp=timestamp / (10 ** 9))  # need float ts

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Creates a diff message with the changes in the order book received from the exchange
        :param msg: the changes in the order book
        :param timestamp: the timestamp of the difference
        :param metadata: a dictionary with extra information to add to the difference data
        :return: a diff message with the changes in the order book notified by the exchange
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            # "first_update_id": msg["U"],
            # "update_id": timestamp,
            "bids": msg["bid"],
            "asks": msg["ask"]
        }, timestamp=timestamp)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)
        ts = msg["timestamp"]
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": f"{msg['baseCurrency']}/{msg['quoteCurrency']}",
            "trade_type": float(TradeType.BUY.value) if msg["makerBuyer"] else float(TradeType.SELL.value),
            "trade_id": msg["id"],
            "update_id": ts,
            "price": msg["price"],
            "amount": msg["quantity"]
        }, timestamp=ts * 1e-3)
