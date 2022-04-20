from decimal import Decimal
from hummingbot.connector.trading_rule import TradingRule
from enum import Enum, auto


class LatokenCommissionType(Enum):
    PERCENT = auto()
    ABSOLUTE = auto()  # TODO review this


class LatokenTakeType(Enum):
    PROPORTION = auto()
    ABSOLUTE = auto()


fee_type = {"FEE_SCHEME_TYPE_PERCENT_QUOTE": LatokenCommissionType.PERCENT}
fee_take = {"FEE_SCHEME_TAKE_PROPORTION": LatokenTakeType.PROPORTION}


class LatokenTradingRule(TradingRule):
    def __init__(
            self,
            trading_pair: str,
            min_order_size: Decimal,
            min_price_increment: Decimal,
            min_base_amount_increment: Decimal,
            min_quote_amount_increment: Decimal,
            min_notional_size: Decimal,
            min_order_value: Decimal,
            fee_schema
    ):
        super().__init__(
            trading_pair=trading_pair,
            min_order_size=min_order_size,
            min_price_increment=min_price_increment,
            min_base_amount_increment=min_base_amount_increment,
            min_quote_amount_increment=min_quote_amount_increment,
            min_notional_size=min_notional_size,
            min_order_value=min_order_value,
        )
        if fee_schema is not None:
            self.maker_fee = Decimal(fee_schema["makerFee"])
            self.taker_fee = Decimal(fee_schema["takerFee"])
            self.type = fee_type[fee_schema["type"]]
            self.take = fee_take[fee_schema["take"]]
