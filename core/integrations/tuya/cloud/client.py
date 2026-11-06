
import hashlib
import hmac
import json
import time
import uuid

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TUYA_REGIONS = {
    "us": "https://openapi.tuyaus.com",
    "us_east": "https://openapi-ueaz.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "eu_west": "https://openapi-weaz.tuyaeu.com",
    "in": "https://openapi.tuyain.com",
    "sg": "https://openapi-sg.iotbing.com",
}


class TuyaCloudClient:
    """Client for the Tuya Cloud OpenAPI."""

    def __init__(
        self,
        access_id: str,
        access_secret: str,
        region: str,
        timeout: int = 15,
    ) -> None:
        if not access_id or not access_secret:
            raise ValueError("Tuya Cloud credentials are required.")

        if region not in TUYA_REGIONS:
            raise ValueError(f"Unsupported Tuya region: {region}")

        self.access_id = access_id
        self.access_secret = access_secret
        self.base_url = TUYA_REGIONS[region]
        self.timeout = timeout

        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at = 0

    @staticmethod
    def _body_hash(body: bytes) -> str:
        return hashlib.sha256(body).hexdigest()

    def _make_signature(
        self,
        method: str,
        path: str,
        body: bytes,
        timestamp: str,
        nonce: str,
        access_token: str | None = None,
    ) -> str:
        string_to_sign = "\n".join([
            method.upper(),
            self._body_hash(body),
            "",
            path,
        ])

        if access_token:
            sign_source = (
                self.access_id
                + access_token
                + timestamp
                + nonce
                + string_to_sign
            )
        else:
            sign_source = (
                self.access_id
                + timestamp
                + nonce
                + string_to_sign
            )

        return hmac.new(
            self.access_secret.encode("utf-8"),
            sign_source.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()

    def _send(
        self,
        method: str,
        path: str,
        query: dict | None = None,
        payload: dict | None = None,
        access_token: str | None = None,
    ) -> dict:
        if query:
            path += "?" + urlencode(sorted(query.items()))

        body = (
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            if payload is not None
            else b""
        )

        timestamp = str(int(time.time() * 1000))
        nonce = uuid.uuid4().hex

        signature = self._make_signature(
            method=method,
            path=path,
            body=body,
            timestamp=timestamp,
            nonce=nonce,
            access_token=access_token,
        )

        headers = {
            "client_id": self.access_id,
            "sign": signature,
            "sign_method": "HMAC-SHA256",
            "t": timestamp,
            "nonce": nonce,
            "lang": "en",
        }

        if access_token:
            headers["access_token"] = access_token

        if body:
            headers["Content-Type"] = "application/json"

        request = Request(
            url=self.base_url + path,
            data=body if body else None,
            headers=headers,
            method=method.upper(),
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_data = response.read()

        except HTTPError as error:
            response_data = error.read()

        except (URLError, TimeoutError) as error:
            raise RuntimeError(
                f"Tuya Cloud connection failed: {error}"
            ) from error

        try:
            result = json.loads(response_data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "Tuya Cloud returned an invalid response."
            ) from error

        if not isinstance(result, dict):
            raise RuntimeError("Unexpected Tuya Cloud response.")

        if not result.get("success", False):
            code = result.get("code", "unknown")
            message = result.get("msg", "Unknown API error")
            raise RuntimeError(
                f"Tuya Cloud API error {code}: {message}"
            )

        return result

    def _request_token(self) -> None:
        result = self._send(
            method="GET",
            path="/v1.0/token",
            query={"grant_type": 1},
        )

        token_data = result.get("result") or {}

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = int(token_data.get("expire_time", 0))

        if not access_token or expires_in <= 0:
            raise RuntimeError(
                "Tuya Cloud did not return a valid access token."
            )

        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expires_at = time.time() + expires_in - 60

    def _get_token(self) -> str:
        if (
            self._access_token
            and time.time() < self._token_expires_at
        ):
            return self._access_token

        if self._refresh_token:
            try:
                result = self._send(
                    method="GET",
                    path=f"/v1.0/token/{self._refresh_token}",
                )

                token_data = result.get("result") or {}
                access_token = token_data.get("access_token")
                expires_in = int(token_data.get("expire_time", 0))

                if access_token and expires_in > 0:
                    self._access_token = access_token
                    self._refresh_token = (
                        token_data.get("refresh_token")
                        or self._refresh_token
                    )
                    self._token_expires_at = (
                        time.time() + expires_in - 60
                    )
                    return access_token

            except RuntimeError:
                self._access_token = None
                self._refresh_token = None

        self._request_token()

        if not self._access_token:
            raise RuntimeError("Tuya Cloud authorization failed.")

        return self._access_token

    def request(
        self,
        method: str,
        path: str,
        query: dict | None = None,
        payload: dict | None = None,
    ) -> dict:
        token = self._get_token()

        return self._send(
            method=method,
            path=path,
            query=query,
            payload=payload,
            access_token=token,
        )

    def get_user_devices(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        if not user_id:
            raise ValueError("Tuya user ID is required.")

        return self.request(
            method="GET",
            path=f"/v1.0/users/{user_id}/devices",
            query={
                "page_no": page,
                "page_size": page_size,
            },
        )

    def get_device(self, device_id: str) -> dict:
        return self.request(
            method="GET",
            path=f"/v1.0/devices/{device_id}",
        )

    def get_device_status(self, device_id: str) -> dict:
        return self.request(
            method="GET",
            path=f"/v1.0/iot-03/devices/{device_id}/status",
        )

    def send_commands(
        self,
        device_id: str,
        commands: list[dict],
    ) -> dict:
        if not commands:
            raise ValueError("At least one device command is required.")

        return self.request(
            method="POST",
            path=f"/v1.0/iot-03/devices/{device_id}/commands",
            payload={"commands": commands},
        )
