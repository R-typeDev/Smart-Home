
const STATUS_REFRESH_INTERVAL = 5000;

const COMMAND_LABELS = {
    turn_on: "Turn on",
    turn_off: "Turn off",
    toggle: "Toggle",
};

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
    let commands = {};
    let currentPower = null;
    let refreshTimer = null;
    let controlInProgress = false;
    let commandContainer = null;
    let deviceOnline = null;

    elements.error.hidden = true;
    elements.controls.hidden = true;
    elements.powerItem.hidden = true;
    elements.description.hidden = false;
    elements.description.textContent = "Loading device information...";
    elements.powerToggle.hidden = true;

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

        await loadCommands();
        await refreshStatus();

        refreshTimer = window.setInterval(
            refreshStatus,
            STATUS_REFRESH_INTERVAL
        );
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
    }

    async function loadCommands() {
        const response = await fetch(
            `/api/devices/${encodeURIComponent(deviceId)}/commands`
        );

        if (!response.ok) {
            throw new Error(
                `Could not load device commands (HTTP ${response.status}).`
            );
        }

        const result = await response.json();
        commands = result.commands || {};

        renderCommands();
    }

    function renderCommands() {
        commandContainer?.remove();

        commandContainer = document.createElement("div");
        commandContainer.className = "device-command-list";

        const hasOn = Object.hasOwn(commands, "turn_on");
        const hasOff = Object.hasOwn(commands, "turn_off");

        if (hasOn && hasOff) {
            const button = document.createElement("button");

            button.type = "button";
            button.dataset.command = "power-toggle";

            button.addEventListener("click", () => {
                if (currentPower === null) {
                    return;
                }

                const commandId = currentPower ? "turn_off" : "turn_on";
                executeCommand(commandId, commands[commandId]);
            });

            commandContainer.appendChild(button);
        }

        for (const [commandId, definition] of Object.entries(commands)) {
            if (
                hasOn &&
                hasOff &&
                (commandId === "turn_on" || commandId === "turn_off")
            ) {
                continue;
            }

            const button = document.createElement("button");

            button.type = "button";
            button.dataset.command = commandId;
            button.textContent =
                definition.label ||
                definition.name ||
                COMMAND_LABELS[commandId] ||
                commandId;

            button.addEventListener("click", () => {
                executeCommand(commandId, definition);
            });

            commandContainer.appendChild(button);
        }

        elements.controls.insertBefore(
            commandContainer,
            elements.powerToggle
        );

        elements.controls.hidden =
            commandContainer.childElementCount === 0;

        updateCommandButtons();
        updatePowerButton();
    }

    function updateCommandButtons() {
        if (!commandContainer) {
            return;
        }

        for (const button of commandContainer.querySelectorAll("button")) {
            button.disabled =
                controlInProgress ||
                Number(device.enabled) !== 1 ||
                deviceOnline === false;
        }

        updatePowerButton();
    }

    function updatePowerButton() {
        const button = commandContainer?.querySelector(
            '[data-command="power-toggle"]'
        );

        if (!button) {
            return;
        }

        button.textContent =
            currentPower === null
                ? "Loading status..."
                : currentPower
                  ? "Turn off"
                  : "Turn on";

        button.disabled =
            currentPower === null ||
            controlInProgress ||
            Number(device.enabled) !== 1 ||
            deviceOnline === false;
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

            deviceOnline = status.online;

            elements.connection.textContent =
                status.online === true
                    ? "Online"
                    : status.online === false
                      ? "Offline"
                      : "Unknown";

            if (typeof status.power === "boolean") {
                currentPower = status.power;
                elements.powerItem.hidden = false;
                elements.power.textContent = status.power ? "On" : "Off";
            } else {
                currentPower = null;
                elements.powerItem.hidden = true;
            }

            updateCommandButtons();
            elements.controlMessage.textContent = "";
        } catch (error) {
            deviceOnline = null;
            currentPower = null;

            elements.connection.textContent = "Unknown";
            updateCommandButtons();

            elements.controlMessage.textContent =
                error instanceof Error
                    ? error.message
                    : "Could not refresh device status.";
        }
    }

    async function executeCommand(commandId, definition) {
        if (
            controlInProgress ||
            Number(device.enabled) !== 1 ||
            deviceOnline === false
        ) {
            return;
        }

        controlInProgress = true;
        updateCommandButtons();
        elements.controlMessage.textContent = "Executing command...";

        try {
            const parameters = definition.parameters || {};
            const options = { method: "POST" };

            if (Object.keys(parameters).length > 0) {
                options.headers = {
                    "Content-Type": "application/json",
                };
                options.body = JSON.stringify(parameters);
            }

            const response = await fetch(
                `/api/devices/${encodeURIComponent(deviceId)}/commands/${encodeURIComponent(commandId)}`,
                options
            );

            if (!response.ok) {
                const details = await response.json().catch(() => null);
                const message =
                    typeof details?.detail === "string"
                        ? details.detail
                        : `HTTP ${response.status}`;

                throw new Error(
                    `Could not execute "${commandId}": ${message}`
                );
            }

            elements.controlMessage.textContent = "Command executed.";

            await refreshStatus();
        } catch (error) {
            elements.controlMessage.textContent =
                error instanceof Error
                    ? error.message
                    : "Could not execute device command.";
        } finally {
            controlInProgress = false;
            updateCommandButtons();
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
        elements.powerItem.hidden = true;

        if (refreshTimer !== null) {
            window.clearInterval(refreshTimer);
        }
    }
}
