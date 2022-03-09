import hashlib
import hmac
from collections import OrderedDict

from typing import (
    Any,
    Dict
)
from urllib.parse import urlencode, urlsplit
from time import time
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTMethod, WSRequest


class LatokenAuth(AuthBase):

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider  # not used atm

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = {}

        if request.headers is not None:
            headers.update(request.headers)

        if request.method == RESTMethod.POST:
            request_params = self.add_auth_to_params(params=request.data)  # probably not necessary
            request.data = request_params
            headers.update({'Content-Type': 'application/json'})  # for now not sure if this must be set on a higher level
        else:
            request_params = self.add_auth_to_params(params=request.params)
            request.params = request_params

        endpoint = urlsplit(request.url).path
        signature = self._generate_signature(method=str(request.method),
                                             endpoint=endpoint,
                                             params=request_params)

        headers.update(self.header_for_authentication(signature))
        request.headers = headers

        return request

    @staticmethod
    def add_auth_to_params(params: Dict[str, Any]):
        # timestamp = int(self.time_provider.time() * 1e3)
        request_params = OrderedDict(params or {})
        # request_params["timestamp"] = timestamp
        # signature = self._generate_signature(params=request_params)
        # request_params["signature"] = signature
        return request_params

    def header_for_authentication(self, signature) -> Dict[str, str]:
        return {"X-LA-APIKEY": self.api_key,
                "X-LA-SIGNATURE": signature,
                "X-LA-DIGEST": hashlib.sha512}

    def _generate_signature(self, method, endpoint, params: Dict[str, Any]) -> str:
        encoded_params = urlencode(params)
        digest = hmac.new(self.secret_key.encode("utf8"),
                          (method + endpoint + encoded_params).encode('ascii'),
                          hashlib.sha512).hexdigest()
        return digest

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        # following should be OK for websocket header

        timestamp = str(int(float(time()) * 1000))
        signature = hmac.new(
            self.secret_key.encode("utf8"),
            timestamp.encode('ascii'),
            hashlib.sha512
        )

        headers = {"X-LA-APIKEY": self.api_key,
                   "X-LA-SIGNATURE": signature.hexdigest(),
                   "X-LA-DIGEST": hashlib.sha512,
                   "X-LA-SIGDATA": timestamp}

        request.payload = dict(request.payload).update(headers)  # not sure about this line
        return request  # pass-through

    def generate_auth_payload(self, param):
        pass
