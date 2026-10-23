const STATUS_REFRESH_INTERVAL = 5000;

export async function init() {
    const elements = {
        name: document.querySelector("#device-name"),
        description: document.querySelector("#device-description"),
        id: document.querySelector("#device-id"),
        externalId: document.querySelector("#device-external-id"),
        type: document.querySelector("#device-type"),
        manufacturer: document.querySelector("#device-manufacturer"),
        model: document.querySelector("#device-model"),
        integration: document.querySelector("#device-integration"),
        enabled: document.querySelector("#device-enabled"),
        connection: document.querySelector("#device-connection"),
        powerItem: document.querySelector("#device-power-item"),
        power: document.querySelector("#device-power"),
        controls: document.querySelector("#device-controls"),
        powerToggle: document.querySelector("#device-power-toggle"),
        controlMessage: document.querySelector("#device-control-message"),
        error: document.querySelector("#device-error"),
    };

    if (Object.values(elements).some((element) => !element)) {
        console.error("Device page elements are missing.");
        return;
    }

    const match = window.location.pathname.match(
        /^\/devices\/item\/([^/]+)\/?$/
    );

    if (!match) {
        showError("Invalid device URL.");
        return;
    }

    let deviceId;

    try {
        deviceId = decodeURIComponent(match[1]);
    } catch {
        showError("Invalid device ID.");
        return;
    }

    let device;
    let refreshTimer = null;
    let controlInProgress = false;

    elements.error.hidden = true;
    elements.controls.hidden = true;
    elements.description.hidden = false;
    elements.description.textContent = "Loading device information...";

    try {
        const response = await fetch(
            `/api/devices/${encodeURIComponent(deviceId)}`
        );

        if (!response.ok) {
            if (response.status === 404) {
                throw new Error("Device not found.");
            }

            throw new Error(
                `Could not load device information (HTTP ${response.status}).`
            );
        }

        device = await response.json();

        renderDevice();
        await refreshStatus();

        refreshTimer = window.setInterval(
            refreshStatus,
            STATUS_REFRESH_INTERVAL
        );

        elements.powerToggle.addEventListener("click", togglePower);
    } catch (error) {
        showError(
            error instanceof Error
                ? error.message
                : "An unexpected error occurred."
        );
    }

    function renderDevice() {
        elements.name.textContent = device.name || "Unnamed device";
        elements.id.textContent = device.id || "—";
        elements.externalId.textContent = device.external_id || "—";
        elements.type.textContent = device.type || "—";
        elements.manufacturer.textContent = device.manufacturer || "—";
        elements.model.textContent = device.model || "—";
        elements.integration.textContent = device.integration_id || "—";

        elements.enabled.textContent =
            Number(device.enabled) === 1 ? "Enabled" : "Disabled";

        elements.description.hidden = true;

        if (supportsPowerControl()) {
            elements.powerItem.hidden = false;
            elements.controls.hidden = false;
            elements.power.textContent = "Unknown";
            elements.powerToggle.textContent = "Loading...";
            elements.powerToggle.disabled = true;
        } else {
            elements.powerItem.hidden = true;
            elements.controls.hidden = true;
        }
    }

    function supportsPowerControl() {
        return (
            Number(device.enabled) === 1 &&
            Boolean(device.external_id) &&
            String(device.integration_id || "").toLowerCase() === "tuya" &&
            String(device.type || "").toLowerCase() === "smart_plug"
        );
    }

    async function refreshStatus() {
        try {
            const response = await fetch(
                `/api/devices/${encodeURIComponent(deviceId)}/status`
            );

            if (!response.ok) {
                throw new Error(
                    `Could not load device status (HTTP ${response.status}).`
                );
            }

            const status = await response.json();

            elements.connection.textContent =
                status.online === true
                    ? "Online"
                    : status.online === false
                      ? "Offline"
                      : "Unknown";

            if (!supportsPowerControl()) {
                return;
            }

            if (typeof status.power === "boolean") {
                elements.power.textContent = status.power ? "On" : "Off";
                elements.powerToggle.textContent = status.power
                    ? "Turn off"
                    : "Turn on";

                elements.powerToggle.disabled =
                    status.online !== true || controlInProgress;
            } else {
                elements.power.textContent = "Unknown";
                elements.powerToggle.textContent = "Power unavailable";
                elements.powerToggle.disabled = true;
            }

            elements.controlMessage.textContent = "";
        } catch (error) {
            elements.connection.textContent = "Unknown";

            if (supportsPowerControl()) {
                elements.power.textContent = "Unknown";
                elements.powerToggle.textContent = "Status unavailable";
                elements.powerToggle.disabled = true;
            }

            elements.controlMessage.textContent =
                error instanceof Error
                    ? error.message
                    : "Could not refresh device status.";
        }
    }

    async function togglePower() {
        if (
            !supportsPowerControl() ||
            controlInProgress ||
            elements.powerToggle.disabled
        ) {
            return;
        }

        const currentPower = elements.power.textContent;

        if (currentPower !== "On" && currentPower !== "Off") {
            return;
        }

        const action = currentPower === "On" ? "off" : "on";

        controlInProgress = true;
        elements.powerToggle.disabled = true;
        elements.powerToggle.textContent = "Please wait...";
        elements.controlMessage.textContent = "";

        try {
            const response = await fetch(
                `/api/devices/${encodeURIComponent(deviceId)}/${action}`,
                { method: "POST" }
            );

            if (!response.ok) {
                throw new Error(
                    `Could not ${action === "on" ? "turn on" : "turn off"} device (HTTP ${response.status}).`
                );
            }

            await refreshStatus();
        } catch (error) {
            elements.controlMessage.textContent =
                error instanceof Error
                    ? error.message
                    : "Could not change device power.";
        } finally {
            controlInProgress = false;
            await refreshStatus();
        }
    }

    function showError(message) {
        elements.name.textContent = "Device";
        elements.description.hidden = false;
        elements.description.textContent =
            "Could not load device information.";
        elements.error.textContent = message;
        elements.error.hidden = false;
        elements.controls.hidden = true;

        if (refreshTimer !== null) {
            window.clearInterval(refreshTimer);
        }
    }
}