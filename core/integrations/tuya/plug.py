
import os

import tinytuya


class TuyaPlugIntegration:
    """Local integration for a Tuya Wi-Fi smart plug."""

    def __init__(self) -> None:
        self.device_id = os.getenv("TUYA_PLUG_ID")
        self.local_key = os.getenv("TUYA_PLUG_LOCAL_KEY")
        self.ip_address = os.getenv("TUYA_PLUG_IP")
        self.version = os.getenv("TUYA_PLUG_VERSION", "3.5")

        if not all(
            [self.device_id, self.local_key, self.ip_address]
        ):
            raise RuntimeError(
                "Tuya plug configuration is incomplete. "
                "Check TUYA_PLUG_ID, TUYA_PLUG_LOCAL_KEY "
                "and TUYA_PLUG_IP in .env."
            )

        self.device = tinytuya.OutletDevice(
            self.device_id,
            self.ip_address,
            self.local_key,
        )
        self.device.set_version(float(self.version))
        self.device.set_socketPersistent(False)
        self.device.set_socketTimeout(5)

    def get_status(self) -> dict:
        """Return the current status reported by the plug."""
        result = self.device.status()

        if not isinstance(result, dict):
            raise RuntimeError("Unexpected response from Tuya plug.")

        if "Error" in result or "Err" in result:
            raise RuntimeError(
                f"Tuya plug returned an error: {result}"
            )

        return result

    def turn_on(self) -> dict:
        """Turn the smart plug on."""
        result = self.device.turn_on()
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected response from Tuya plug.")
        if "Error" in result or "Err" in result:
            raise RuntimeError("Tuya plug returned an error.")
        return result

    def turn_off(self) -> dict:
        """Turn the smart plug off."""
        result = self.device.turn_off()
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected response from Tuya plug.")
        if "Error" in result or "Err" in result:
            raise RuntimeError("Tuya plug returned an error.")
        return result
