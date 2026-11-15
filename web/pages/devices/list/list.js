import { t } from "../../../assets/js/i18n.js";

const API_URL = "/api/devices";
const DEVICE_URL = "/devices/item/";

export function init() {
    const list = document.getElementById("devices-list");
    const message = document.getElementById("devices-message");
    const retryButton = document.getElementById("devices-retry");

    if (!list || !message || !retryButton) {
        return;
    }

    retryButton.addEventListener("click", loadDevices);

    loadDevices();

    async function loadDevices() {
        list.replaceChildren();
        message.hidden = false;
        message.textContent = t("devices.loading");
        retryButton.hidden = true;

        try {
            const response = await fetch(API_URL);

            if (!response.ok) {
                throw new Error("Could not load devices.");
            }

            const devices = await response.json();

            if (!Array.isArray(devices)) {
                throw new Error("Invalid devices response.");
            }

            if (devices.length === 0) {
                message.textContent = t("devices.empty");
                return;
            }

            message.hidden = true;

            devices.forEach((device) => {
                list.appendChild(createDeviceRow(device));
            });
        } catch {
            list.replaceChildren();
            message.hidden = false;
            message.textContent = t("devices.loadError");
            retryButton.hidden = false;
        }
    }

    function createDeviceRow(device) {
        const row = document.createElement("div");
        row.className = "devices-list__item";

        const link = document.createElement("a");
        link.className = "devices-list__link";
        link.href = `${DEVICE_URL}${encodeURIComponent(device.id)}`;

        const name = document.createElement("span");
        name.className = "devices-list__name";
        name.textContent = device.name || t("devices.unnamed");

        const arrow = document.createElement("span");
        arrow.className = "devices-list__arrow";
        arrow.setAttribute("aria-hidden", "true");
        arrow.textContent = "→";

        link.append(name, arrow);

        const status = document.createElement("span");
        const enabled = device.enabled === 1 || device.enabled === true;

        status.className = enabled
            ? "devices-list__status devices-list__status--enabled"
            : "devices-list__status devices-list__status--disabled";

        status.textContent = enabled
            ? t("devices.active")
            : t("devices.disabled");

        row.append(link, status);

        return row;
    }
}