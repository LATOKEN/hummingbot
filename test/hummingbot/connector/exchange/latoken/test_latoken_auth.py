import asyncio
import hashlib
import hmac
from copy import copy
from unittest import TestCase
from unittest.mock import MagicMock

from typing_extensions import Awaitable

from urllib.parse import urlencode, urlsplit
from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


# https://api.latoken.com/doc/v2/#operation/getBalancesByUser


class LatokenAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "26f73f0b-05d7-4007-bf82-dc7b36cef9ee"
        self._secret_key = "MMGIyMjhjMDgtZDJmOS00MDYwLWFmMjUtNDc0OTI1ODg3MGI5"

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate_get(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()  # possibly not useful  for latoken rest
        mock_time_provider.time.return_value = now

        params = {'zeros': 'true'}
        full_params = copy(params)
        auth_account_url = 'https://api.latoken.com/v2/auth/account'
        auth = LatokenAuth(api_key=self._api_key, secret_key=self._secret_key, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, url=auth_account_url, params=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        # full_params.update({"timestamp": 1234567890000})
        endpoint = urlsplit(request.url).path
        encoded_params = urlencode(full_params)
        expected_rest_signature_get = hmac.new(
            self._secret_key.encode("utf-8"),  # differs a bit from the official latoken api where they use b string
            ('GET' + endpoint + encoded_params).encode('ascii'),
            hashlib.sha512
        )
        # self.assertEqual(now * 1e3, configured_request.params["timestamp"])
        # self.assertEqual(expected_signature, configured_request.params["signature"])
        self.assertEqual({"X-LA-APIKEY": self._api_key,
                          "X-LA-SIGNATURE": expected_rest_signature_get.hexdigest(),
                          "X-LA-DIGEST": hashlib.sha512}, configured_request.headers)

    # todo implement function definitions
    def test_rest_authenticate_post(self):
        pass

    def test_ws_authenticate_get(self):
        pass

    def test_ws_authenticate_post(self):
        pass
