import os
import socket
import time
import unittest
from unittest.mock import patch

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
from hummingbot.connector.exchange.latoken import latoken_utils as utils
from typing import (
    Dict,
    List,
)


class LatokenUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.domain = "com"
        cls.endpoint = CONSTANTS.DOMAIN_TO_ENDPOINT[cls.domain]
        cls.base_asset = "ETH"
        cls.quote_asset = "USDT"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        # cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_public_rest_url(self):
        path_url = "/auth/account"
        expected_url = CONSTANTS.REST_URL.format(self.endpoint, self.domain) + CONSTANTS.PUBLIC_API_VERSION + path_url
        self.assertEqual(expected_url, utils.public_rest_url(path_url, self.domain))

    def test_private_rest_url(self):
        path_url = "/auth/account"
        expected_url = CONSTANTS.REST_URL.format(self.endpoint, self.domain) + CONSTANTS.PRIVATE_API_VERSION + path_url
        self.assertEqual(expected_url, utils.private_rest_url(path_url, self.domain))

    @classmethod
    def get_mapping(cls):
        ticker_list: List[Dict] = [
            {"symbol": "REN/BTC", "baseCurrency": "8de4581d-3778-48e5-975e-511039a2aa6b",
             "quoteCurrency": "92151d82-df98-4d88-9a4d-284fa9eca49f", "volume24h": "0", "volume7d": "0",
             "change24h": "0", "change7d": "0", "amount24h": "0", "amount7d": "0", "lastPrice": "0",
             "lastQuantity": "0", "bestBid": "0", "bestBidQuantity": "0", "bestAsk": "0", "bestAskQuantity": "0",
             "updateTimestamp": 0},
            {"symbol": "NECC/USDT", "baseCurrency": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c",
             "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5", "volume24h": "0", "volume7d": "0",
             "change24h": "0", "change7d": "0", "amount24h": "0", "amount7d": "0", "lastPrice": "0",
             "lastQuantity": "0", "bestBid": "0", "bestBidQuantity": "0", "bestAsk": "0", "bestAskQuantity": "0",
             "updateTimestamp": 0}
        ]
        currency_list: List[Dict] = [
            {"id": "8de4581d-3778-48e5-975e-511039a2aa6b", "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "REN", "tag": "REN", "description": "", "logo": "", "decimals": 18,
             "created": 1599223148171, "tier": 3, "assetClass": "ASSET_CLASS_UNKNOWN", "minTransferAmount": 0},
            {"id": "92151d82-df98-4d88-9a4d-284fa9eca49f", "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "Bitcoin", "tag": "BTC", "description": "", "logo": "",
             "decimals": 8, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
             "minTransferAmount": 0},
            {"id": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c", "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "Natural Eco Carbon Coin", "tag": "NECC", "description": "",
             "logo": "", "decimals": 18, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
             "minTransferAmount": 0},
            {"id": "0c3a106d-bde3-4c13-a26e-3fd2394529e5", "status": "CURRENCY_STATUS_ACTIVE",
             "type": "CURRENCY_TYPE_CRYPTO", "name": "Tether USD ", "tag": "USDT", "description": "", "logo": "",
             "decimals": 6, "created": 1572912000000, "tier": 1, "assetClass": "ASSET_CLASS_UNKNOWN",
             "minTransferAmount": 0}
        ]
        pair_list: List[Dict] = [
            {"id": "30a1032d-1e3e-4c28-8ca7-b60f3406fc3e", "status": "PAIR_STATUS_ACTIVE",
             "baseCurrency": "8de4581d-3778-48e5-975e-511039a2aa6b",
             "quoteCurrency": "92151d82-df98-4d88-9a4d-284fa9eca49f",
             "priceTick": "0.000000010000000000", "priceDecimals": 8,
             "quantityTick": "1.000000000000000000", "quantityDecimals": 0,
             "costDisplayDecimals": 8, "created": 1599249032243, "minOrderQuantity": "0",
             "maxOrderCostUsd": "999999999999999999", "minOrderCostUsd": "0",
             "externalSymbol": ""},
            {"id": "3140357b-e0da-41b2-b8f4-20314c46325b", "status": "PAIR_STATUS_ACTIVE",
             "baseCurrency": "ad48cd21-4834-4b7d-ad32-10d8371bbf3c",
             "quoteCurrency": "0c3a106d-bde3-4c13-a26e-3fd2394529e5",
             "priceTick": "0.000010000000000000", "priceDecimals": 5,
             "quantityTick": "0.100000000000000000", "quantityDecimals": 1,
             "costDisplayDecimals": 5, "created": 1576052642564, "minOrderQuantity": "0",
             "maxOrderCostUsd": "999999999999999999", "minOrderCostUsd": "0",
             "externalSymbol": ""}
        ]
        return utils.create_full_mapping(ticker_list, currency_list, pair_list)

    def test_is_exchange_information_valid(self):
        full_mapping = self.get_mapping()  # we accept only data from our SPOT account for trading, other balances are omitted
        # invalid_info_1 = {
        #     "status": "BREAK",
        #     "permissions": ["MARGIN"],
        # }
        #
        #
        # self.assertFalse(utils.is_exchange_information_valid(invalid_info_1))
        #
        # invalid_info_2 = {
        #     "status": "BREAK",
        #     "permissions": ["SPOT"],
        # }
        #
        # self.assertFalse(utils.is_exchange_information_valid(invalid_info_2))
        #
        # invalid_info_3 = {
        #     "status": "TRADING",
        #     "permissions": ["MARGIN"],
        # }
        #
        # self.assertFalse(utils.is_exchange_information_valid(invalid_info_3))
        #
        # invalid_info_4 = {
        #     "status": "TRADING",
        #     "permissions": ["SPOT"],
        # }

        self.assertTrue(all([utils.is_exchange_information_valid(map) for map in full_mapping]))

    @patch("hummingbot.connector.exchange.latoken.latoken_utils.get_tracking_nonce")
    def test_client_order_id_generation(self, nonce_mock):
        nonce = int(time.time() * 1e6)
        nonce_mock.return_value = nonce
        client_instance_id = hex(abs(hash(f"{socket.gethostname()}{os.getpid()}")))[2:6]

        client_order_id = utils.get_new_client_order_id(is_buy=True, trading_pair=self.hb_trading_pair)
        expected_id = (f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}-{'B'}"
                       f"{self.base_asset[0]}{self.base_asset[-1]}{self.quote_asset[0]}{self.quote_asset[-1]}"
                       f"{client_instance_id}{nonce}")
        self.assertEqual(expected_id, client_order_id)

        client_order_id = utils.get_new_client_order_id(is_buy=False, trading_pair=self.hb_trading_pair)
        expected_id = (f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}-{'S'}"
                       f"{self.base_asset[0]}{self.base_asset[-1]}{self.quote_asset[0]}{self.quote_asset[-1]}"
                       f"{client_instance_id}{nonce}")
        self.assertEqual(expected_id, client_order_id)
