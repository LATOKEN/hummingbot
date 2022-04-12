from typing import Dict, Optional

from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)
from hummingbot.connector.exchange.latoken.latoken_utils import get_book_side


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
        timestamp_ms = timestamp * 1e-9  # there is no timestamp per order book level, so this is not really useful in stoikov, if you want to use snapshots for real-time data
        msg["asks"] = get_book_side(msg.pop("ask"))
        msg["bids"] = get_book_side(msg.pop("bid"))
        msg["update_id"] = timestamp_ms  # ts in nanosecond
        # tuple(sorted([('abc', 121), ('abc', 231), ('abc', 148), ('abc', 221)],
        #        key=lambda x: x[1])) # not sure asks or bids need to be presorted by price
        # order_book command does how to have correct sorting
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, msg, timestamp=timestamp_ms)  # need float ts

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: int,
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
        timestamp_ms = timestamp * 1e-9
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "first_update_id": msg["timestamp"] * 1e-3,  # could also use msg['headers']['message-id'] ?
            "update_id": timestamp_ms,
            "bids": get_book_side(msg["bid"]),
            "asks": get_book_side(msg["ask"])
        }, timestamp=timestamp_ms)

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, any],
                                    timestamp: int,
                                    metadata: Optional[Dict] = None):
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param timestamp: the timestamp of the trade
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)
        timestamp_ms = timestamp * 1e-9
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["trading_pair"],
            "trade_type": float(TradeType.BUY.value) if msg["makerBuyer"] else float(TradeType.SELL.value),
            "trade_id": msg["timestamp"] * 1e-3,  # could also use msg['headers']['message-id'] ?
            "update_id": timestamp_ms,  # do we need body_timestamp here???
            "price": msg["price"],
            "amount": msg["quantity"]
        }, timestamp=timestamp_ms)
