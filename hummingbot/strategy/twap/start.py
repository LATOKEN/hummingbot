from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.twap import (
    TwapTradeStrategy
)
from hummingbot.strategy.twap.twap_config_map import twap_config_map


def start(self):
    try:
        order_step_size = twap_config_map.get("order_step_size").value
        trade_side = twap_config_map.get("trade_side").value
        target_asset_amount = twap_config_map.get("target_asset_amount").value
        order_delay_time = twap_config_map.get("order_delay_time").value
        exchange = twap_config_map.get("connector").value.lower()
        raw_market_trading_pair = twap_config_map.get("trading_pair").value
        order_price = twap_config_map.get("order_price").value
        cancel_order_wait_time = twap_config_map.get("cancel_order_wait_time").value

        try:
            assets: Tuple[str, str] = self._initialize_market_assets(exchange, [raw_market_trading_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(exchange, [raw_market_trading_pair])]

        self._initialize_wallet(token_trading_pairs=list(set(assets)))
        self._initialize_markets(market_names)
        self.assets = set(assets)

        maker_data = [self.markets[exchange], raw_market_trading_pair] + list(assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        is_buy = trade_side == "buy"

        self.strategy = TwapTradeStrategy(market_infos=[MarketTradingPairTuple(*maker_data)],
                                          is_buy=is_buy,
                                          target_asset_amount=target_asset_amount,
                                          order_step_size=order_step_size,
                                          order_price=order_price,
                                          order_delay_time=order_delay_time,
                                          cancel_order_wait_time=cancel_order_wait_time)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
