from decimal import Decimal


# https://github.com/LATOKEN/latoken-api-v2-python-client/blob/main/latoken/client.py
AUTH_PART = "/v2/auth"
# https://api.latoken.com/doc/v2/
LATOKEN_REST_URL = "https://api.latoken.com"
LATOKEN_REST_AUTH_URL = LATOKEN_REST_URL + AUTH_PART
# https://api.latoken.com/doc/ws/#section/Authorization-Using-API-Key-Signature
LATOKEN_WS_URI = "wss://api.latoken.com/stomp"
LATOKEN_WS_AUTH_URI = LATOKEN_WS_URI + AUTH_PART

# https://latoken.com/fees
TAKER_FEE = Decimal("0.0049")
MAKER_FEE = Decimal("0.0049")
# AFF_CODE = "-dxCUrjvc" ?


class SubmitOrder:
    OID = 0

    def __init__(self, oid):
        self.oid = str(oid)

    @classmethod
    def parse(cls, order_snapshot):
        return cls(order_snapshot[cls.OID])


# https://latoken.zendesk.com/hc/en-us/articles/4405700683922-LATOKEN-Order-status
class OrderStatus:
    ACTIVE = "ACTIVE"
    CANCELED = "CANCELED"
    PARTIALLY = "PARTIALLY"  # not sure about latoken implementation
    EXECUTED = "EXECUTED"


class ContentEventType:
    ORDER_UPDATE = "ou"
    TRADE_UPDATE = "tu"
    TRADE_EXECUTE = "te"
    WALLET_SNAPSHOT = "ws"
    WALLET_UPDATE = "wu"
    HEART_BEAT = "hb"
    AUTH = "auth"
    INFO = "info"
