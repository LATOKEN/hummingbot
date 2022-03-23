from hummingbot.core.api_throttler.data_types import RateLimit  # ,LinkedLimitWeightPair,
from hummingbot.core.data_type.in_flight_order import OrderState

HBOT_ORDER_ID_PREFIX = "latoken-hbot"  # not sure how to interpret this for latoken

# Base URL
REST_URL = "https://backoffice-qa-equity.dev3.nekotal.{}"
WSS_URL = "wss://backoffice-qa-equity.dev3.nekotal.{}/stomp"
DOMAIN = "tech"

# REST_URL = "https://api.latoken.{}"
# WSS_URL = "wss://api.latoken.{}/stomp"
# DOMAIN = "com"


PUBLIC_API_VERSION = "/v2"
PRIVATE_API_VERSION = "/v2"

# Public API endpoints or BinanceClient function
# TICKER_PRICE_CHANGE_PATH_URL = "/ticker/24hr"
TICKER_PATH_URL = "/ticker"
CURRENCY_PATH_URL = "/currency"
PAIR_PATH_URL = "/pair"
PING_PATH_URL = "/time"
BOOK_PATH_URL = "/book"
SNAPSHOT_PATH_URL = "/depth"  # todo remove from unit test
SERVER_TIME_PATH_URL = "/time"

# Private API endpoints or BinanceClient function
ACCOUNTS_PATH_URL = "/auth/account"
# MY_TRADES_PATH_URL = "/trade"
TRADES_FOR_PAIR_PATH_URL = "/auth/trade/pair"
# ORDER_PATH_URL = "/order"
ORDER_PLACE_PATH_URL = "/auth/order/place"
ORDER_CANCEL_PATH_URL = "/auth/order/cancel"
GET_ORDER_PATH_URL = "/auth/order/getOrder"
LATOKEN_USER_STREAM_PATH_URL = "/auth/user"  # https://api.latoken.com/doc/ws/#section/Accounts

WS_HEARTBEAT_TIME_INTERVAL = 30
#
# Latoken params

SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

TIME_IN_FORCE_GTC = 'GTC'  # Good till cancelled
TIME_IN_FORCE_IOC = 'IOC'  # Immediate or cancel
TIME_IN_FORCE_FOK = 'FOK'  # Fill or kill

# Rate Limit Type
# REQUEST_WEIGHT = "REQUEST_WEIGHT"
# ORDERS = "ORDERS"
# ORDERS_24HR = "ORDERS_24HR"
ACCOUNT = "/auth/account"
TIME = "/time"

# WS (streams)
# Public
BOOK_STREAM = '/v1/book/{symbol}'
TRADES_STREAM = '/v1/trade/{symbol}'
CURRENCIES_STREAM = '/v1/currency'  # All available currencies
PAIRS_STREAM = '/v1/pair'  # All available pairs
TICKER_ALL_STREAM = '/v1/ticker'
TICKERS_PAIR_STREAM = '/v1/ticker/{base}/{quote}'  # 24h and 7d volume and change + last price for pairs
RATES_STREAM = '/v1/rate/{base}/{quote}'
RATES_QUOTE_STREAM = '/v1/rate/{quote}'

# Private
ORDERS_STREAM = '/user/{user}/v1/order'
ACCOUNTS_STREAM = '/user/{user}/v1/account/total'  # Returns all accounts of a user including empty ones
ACCOUNT_STREAM = '/user/{user}/v1/account'
TRANSACTIONS_STREAM = '/user/{user}/v1/transaction'  # Returns external transactions (deposits and withdrawals)
TRANSFERS_STREAM = '/user/{user}/v1/transfers'  # Returns internal transfers on the platform (inter_user, ...)


# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "ORDER_STATUS_PLACED": OrderState.OPEN,
    "ORDER_STATUS_CLOSED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "ORDER_STATUS_CANCELLED": OrderState.CANCELLED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

# # Websocket event types
DIFF_EVENT_TYPE = "depthUpdate"
TRADE_EVENT_TYPE = "trade"

GLOBAL_RATE_LIMIT = "global"

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=GLOBAL_RATE_LIMIT, limit=5, time_interval=ONE_SECOND),
    RateLimit(limit_id=ACCOUNT, limit=5, time_interval=ONE_SECOND),
    RateLimit(limit_id=TIME, limit=5, time_interval=ONE_SECOND),
    RateLimit(limit_id=TICKER_PATH_URL, limit=5, time_interval=ONE_SECOND),
    RateLimit(limit_id=CURRENCY_PATH_URL, limit=5, time_interval=ONE_SECOND),
    RateLimit(limit_id=PAIR_PATH_URL, limit=5, time_interval=ONE_SECOND),
    RateLimit(limit_id=BOOK_PATH_URL, limit=5, time_interval=ONE_SECOND),
    # RateLimit(limit_id=MY_TRADES_PATH_URL, limit=5, time_interval=ONE_SECOND),
    RateLimit(limit_id=TRADES_FOR_PAIR_PATH_URL, limit=5, time_interval=ONE_SECOND),
    # RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    # RateLimit(limit_id=ORDERS, limit=10, time_interval=ONE_SECOND),
    # RateLimit(limit_id=ORDERS_24HR, limit=100000, time_interval=ONE_DAY),

    # # Weighted Limits
    # RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 40)]),
    # RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[(LinkedLimitWeightPair(REQUEST_WEIGHT, 10))]),
    # RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 50)]),
    # RateLimit(limit_id=BINANCE_USER_STREAM_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    # RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    # RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    # RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    # RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    # RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
    #                          LinkedLimitWeightPair(ORDERS, 1),
    #                          LinkedLimitWeightPair(ORDERS_24HR, 1)]),
]
