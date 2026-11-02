
import tinytuya


class TuyaPlugIntegration:
    """Local integration for a Tuya Wi-Fi smart plug."""

    def __init__(
        self,
        device_id: str,
        ip_address: str,
        local_key: str,
        version: str = "3.5",
    ) -> None:
        if not all([device_id, ip_address, local_key]):
            raise RuntimeError(
                "Tuya plug configuration is incomplete."
            )

        self.device = tinytuya.OutletDevice(
            device_id,
            ip_address,
            local_key,
        )
        self.device.set_version(float(version))
        self.device.set_socketPersistent(False)
        self.device.set_socketTimeout(5)

    @staticmethod
    def _validate_response(result: dict) -> dict:
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected response from Tuya plug.")

        if "Error" in result or "Err" in result:
            raise RuntimeError("Tuya plug returned an error.")

        return result

    def get_status(self) -> dict:
        """Return the current status reported by the plug."""
        return self._validate_response(self.device.status())

    def turn_on(self) -> dict:
        """Turn the smart plug on."""
        return self._validate_response(self.device.turn_on())

    def turn_off(self) -> dict:
        """Turn the smart plug off."""
        return self._validate_response(self.device.turn_off())
