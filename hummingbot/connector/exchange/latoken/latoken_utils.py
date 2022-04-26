import os
import socket
from decimal import Decimal
from typing import Any, Dict
# from hummingbot.core.utils.async_utils import safe_gather
import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod,
    RESTRequest,
    RESTResponse,
    # WSRequest,
)
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.data_type.in_flight_order import OrderState

CENTRALIZED = True
EXAMPLE_PAIR = "LA-USDT"
DEFAULT_FEES = [0.1, 0.1]

# Order States for REST
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "ORDER_STATUS_PLACED": OrderState.OPEN,
    "ORDER_STATUS_CLOSED": OrderState.FILLED,
    "ORDER_STATUS_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "ORDER_STATUS_CANCELLED": OrderState.CANCELLED,
    "ORDER_STATUS_REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}


# Order States for WS
def get_order_status_ws(change_type: str, status: str, quantity: Decimal, filled: Decimal, delta_filled: Decimal):

    order_state = None  # None is not used to update order in hbot order mgmt
    if status == "ORDER_STATUS_PLACED":
        if change_type == 'ORDER_CHANGE_TYPE_PLACED':
            order_state = OrderState.OPEN
        elif change_type == "ORDER_CHANGE_TYPE_FILLED" and delta_filled > Decimal(0):
            order_state = OrderState.FILLED if quantity == filled else OrderState.PARTIALLY_FILLED
        # elif change_type == 'ORDER_CHANGE_TYPE_UNCHANGED':
        #     order_state = None
    # elif status == "ORDER_STATUS_CLOSED":
    #     if change_type == "ORDER_CHANGE_TYPE_CLOSED" or change_type == "ORDER_CHANGE_TYPE_UNCHANGED":
    #         order_state = None  # don't handle this for now, this is a confirmation from Latoken for fill
    elif status == "ORDER_STATUS_CANCELLED":
        if change_type == 'ORDER_CHANGE_TYPE_PLACED':
            order_state = OrderState.PENDING_CANCEL
        if change_type == "ORDER_CHANGE_TYPE_CANCELLED":
            order_state = OrderState.CANCELLED
        # elif change_type == 'ORDER_CHANGE_TYPE_UNCHANGED':
        #     order_state = None
    elif status == "ORDER_STATUS_REJECTED":
        if change_type == "ORDER_CHANGE_TYPE_REJECTED":  # TODO review this
            order_state = OrderState.FAILED
    elif status == "ORDER_STATUS_NOT_PROCESSED":
        if change_type == "ORDER_CHANGE_TYPE_REJECTED":  # TODO review this
            order_state = OrderState.FAILED
    elif status == "ORDER_STATUS_UNKNOWN":
        if change_type == "ORDER_CHANGE_TYPE_REJECTED":  # TODO review this
            order_state = OrderState.FAILED

    return order_state


def get_order_status_rest(status: str, filled: Decimal, quantity: Decimal):
    new_state = ORDER_STATE[status]
    if new_state == OrderState.FILLED and quantity != filled:
        new_state = OrderState.PARTIALLY_FILLED
    return new_state


# async def get_currency_data(logger, domain, rest_assistant, local_throttler, currencies) -> dict:
#     requests = []
#     currency_lists = None
#     for currency in currencies:
#         url = public_rest_url(path_url=f"{CONSTANTS.CURRENCY_PATH_URL}/{currency}", domain=domain)
#         headers = {"Content-Type": "application/x-www-form-urlencoded"}
#         request = RESTRequest(method=RESTMethod.GET, url=url, headers=headers, is_auth_required=False)
#         requests.append(request)
#         try:
#             async with local_throttler.execute_task(limit_id=CONSTANTS.GLOBAL_RATE_LIMIT):
#                 responses = await safe_gather(*requests, return_exceptions=True)
#                 currency_lists = [await response.json() for response in responses]
#         except Exception as ex:
#             logger.error(f"There was an error requesting ({ex})")
#
#     currency_mapping = {currency_json["tag"]: currency_json["id"] for currency_json in currency_lists}
#     return currency_mapping


async def get_data(logger, domain, rest_assistant, local_throttler, path_url) -> list:
    url = public_rest_url(path_url=path_url, domain=domain)
    request = RESTRequest(method=RESTMethod.GET, url=url)

    data = []
    try:
        async with local_throttler.execute_task(limit_id=CONSTANTS.GLOBAL_RATE_LIMIT):
            response: RESTResponse = await rest_assistant.call(request=request)
            if response.status == 200:
                data.extend(await response.json())
    except Exception as ex:
        logger.error(f"There was an error requesting {path_url} ({ex})")

    return data


def create_full_mapping(ticker_list, currency_list, pair_list):
    ticker_dict = {f"{ticker['baseCurrency']}/{ticker['quoteCurrency']}": ticker for ticker in ticker_list}
    # pair_dict = {f"{pair['baseCurrency']}/{pair['quoteCurrency']}": pair for pair in pair_list}
    currency_dict = {currency["id"]: currency for currency in currency_list}

    for pt in pair_list:
        key = f"{pt['baseCurrency']}/{pt['quoteCurrency']}"
        is_valid = key in ticker_dict
        pt["is_valid"] = is_valid
        pt["id"] = ticker_dict[key] if is_valid else {"id": key}
        base_id = pt["baseCurrency"]
        if base_id in currency_dict:
            pt["baseCurrency"] = currency_dict[base_id]
        quote_id = pt["quoteCurrency"]
        if quote_id in currency_dict:
            pt["quoteCurrency"] = currency_dict[quote_id]

    return pair_list


def get_book_side(book):
    return tuple((row['price'], row['quantity']) for row in book)


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

    return pair_data["is_valid"] and pair_data["status"] == 'PAIR_STATUS_ACTIVE' and \
        isinstance(pair_base, dict) and isinstance(pair_quote, dict) and \
        pair_base["status"] == 'CURRENCY_STATUS_ACTIVE' and pair_base["type"] == 'CURRENCY_TYPE_CRYPTO' and \
        pair_quote["status"] == 'CURRENCY_STATUS_ACTIVE' and pair_quote["type"] == 'CURRENCY_TYPE_CRYPTO'


# def is_pair_valid(pair_data: Dict[str, Any]) -> bool:
#     return pair_data["status"] == 'PAIR_STATUS_ACTIVE'


def public_rest_url(path_url: str, domain: str = "com") -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Latoken domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    endpoint = CONSTANTS.DOMAIN_TO_ENDPOINT[domain]
    return CONSTANTS.REST_URL.format(endpoint, domain) + CONSTANTS.PUBLIC_API_VERSION + path_url


def private_rest_url(path_url: str, domain: str = "com") -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the Latoken domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    endpoint = CONSTANTS.DOMAIN_TO_ENDPOINT[domain]
    return CONSTANTS.REST_URL.format(endpoint, domain) + CONSTANTS.PRIVATE_API_VERSION + path_url


def ws_url(domain: str = "com") -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the Latoken domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    endpoint = CONSTANTS.DOMAIN_TO_ENDPOINT[domain]
    return CONSTANTS.WSS_URL.format(endpoint, domain)


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


OTHER_DOMAINS = []
OTHER_DOMAINS_PARAMETER = {}
OTHER_DOMAINS_EXAMPLE_PAIR = {}
OTHER_DOMAINS_DEFAULT_FEES = {}
OTHER_DOMAINS_KEYS = {}
