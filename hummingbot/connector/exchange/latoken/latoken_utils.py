import os
import socket
from typing import Any, Dict

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce


CENTRALIZED = True
EXAMPLE_PAIR = "LA-USDT"
DEFAULT_FEES = [0.1, 0.1]


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    """
    Creates a client order id for a new order
    :param is_buy: True if the order is a buy order, False otherwise
    :param trading_pair: the trading pair the order will be operating with
    :return: an identifier for the new order to be used in the client
    """
    side = "B" if is_buy else "S"
    base, quote = trading_pair.split("-")
    base_str = f"{base[0]}{base[-1]}"
    quote_str = f"{quote[0]}{quote[-1]}"
    client_instance_id = hex(abs(hash(f"{socket.gethostname()}{os.getpid()}")))[2:6]
    return f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}-{side}{base_str}{quote_str}{client_instance_id}{get_tracking_nonce()}"


def is_exchange_information_valid(pair_data: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param pair_data: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """

    # pair_details = pair_data["id"]
    pair_base = pair_data["baseCurrency"]
    pair_quote = pair_data["quoteCurrency"]
    return pair_data["is_valid"] and pair_data["status"] == 'PAIR_STATUS_ACTIVE' \
        and pair_base["status"] == 'CURRENCY_STATUS_ACTIVE' and pair_base["type"] == 'CURRENCY_TYPE_CRYPTO' \
        and pair_quote["status"] == 'CURRENCY_STATUS_ACTIVE' and pair_quote["type"] == 'CURRENCY_TYPE_CRYPTO'


def is_pair_valid(pair_data: Dict[str, Any]) -> bool:
    return pair_data["status"] == 'PAIR_STATUS_ACTIVE'


def public_rest_url(path_url: str, domain: str = "com") -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Binance domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URL.format(domain) + CONSTANTS.PUBLIC_API_VERSION + path_url


def private_rest_url(path_url: str, domain: str = "com") -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the Binance domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URL.format(domain) + CONSTANTS.PRIVATE_API_VERSION + path_url


KEYS = {
    "latoken_api_key":
        ConfigVar(key="latoken_api_key",
                  prompt="Enter your Latoken API key >>> ",
                  required_if=using_exchange("latoken"),
                  is_secure=True,
                  is_connect_key=True),
    "latoken_api_secret":
        ConfigVar(key="latoken_api_secret",
                  prompt="Enter your Latoken API secret >>> ",
                  required_if=using_exchange("latoken"),
                  is_secure=True,
                  is_connect_key=True),
}
