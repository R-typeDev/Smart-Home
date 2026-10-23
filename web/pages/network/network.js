const API_URL = "/api/network";
const DEVICE_URL = "/network/item/";

export function init() {
    const list = document.getElementById("network-list");
    const message = document.getElementById("network-message");
    const retryButton = document.getElementById("network-retry");

    if (!list || !message || !retryButton) {
        return;
    }

    retryButton.addEventListener("click", loadDevices);

    loadDevices();

    async function loadDevices() {
        list.replaceChildren();

        message.hidden = false;
        message.textContent = "Loading network devices…";
        retryButton.hidden = true;

        try {
            const response = await fetch(API_URL);

            if (!response.ok) {
                throw new Error("Could not load network devices.");
            }

            const devices = await response.json();

            if (!Array.isArray(devices)) {
                throw new Error("Invalid network devices response.");
            }

            if (devices.length === 0) {
                message.textContent = "No network devices have been added yet.";
                return;
            }

            message.hidden = true;

            devices.forEach((device) => {
                list.appendChild(createDeviceRow(device));
            });
        } catch {
            list.replaceChildren();
            message.hidden = false;
            message.textContent =
                "Could not load network devices. Please try again.";
            retryButton.hidden = false;
        }
    }

    function createDeviceRow(device) {
        const row = document.createElement("div");
        row.className = "network-list__item";

        const link = document.createElement("a");
        link.className = "network-list__link";
        link.href = `${DEVICE_URL}${encodeURIComponent(device.id)}`;

        const name = document.createElement("span");
        name.className = "network-list__name";
        name.textContent = device.name || "Unnamed network device";

        const arrow = document.createElement("span");
        arrow.className = "network-list__arrow";
        arrow.setAttribute("aria-hidden", "true");
        arrow.textContent = "→";

        link.append(name, arrow);

        const status = document.createElement("span");
        const enabled = device.enabled === 1 || device.enabled === true;

        status.className = enabled
            ? "network-list__status network-list__status--enabled"
            : "network-list__status network-list__status--disabled";

        status.textContent = enabled ? "Active" : "Disabled";

        row.append(link, status);

        return row;
    }
}