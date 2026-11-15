export function init() {
    const deviceName = document.getElementById("network-device-name");
    const deviceStatus = document.getElementById("network-device-status");
    const deviceInfo = document.getElementById("network-device-info");

    const clientsSection = document.getElementById("network-clients-section");
    const clientsStatus = document.getElementById("network-clients-status");
    const clientsContainer = document.getElementById("network-clients");

    if (
        !deviceName ||
        !deviceStatus ||
        !deviceInfo ||
        !clientsSection ||
        !clientsStatus ||
        !clientsContainer
    ) {
        console.error("Network device page elements are missing.");
        return;
    }

    const pathParts = window.location.pathname.split("/").filter(Boolean);
    const itemIndex = pathParts.indexOf("item");
    const deviceId = itemIndex >= 0 ? pathParts[itemIndex + 1] : null;

    function addInfoRow(label, value) {
        if (value === null || value === undefined || value === "") {
            return;
        }

        const term = document.createElement("dt");
        term.textContent = label;

        const description = document.createElement("dd");
        description.textContent = String(value);

        deviceInfo.append(term, description);
    }

    function renderClients(clients) {
        clientsContainer.replaceChildren();

        if (!Array.isArray(clients) || clients.length === 0) {
            clientsStatus.textContent = "No DHCP clients found.";
            return;
        }

        const columns = [
            ...new Set(
                clients.flatMap((client) =>
                    client && typeof client === "object"
                        ? Object.keys(client)
                        : ["Device"]
                )
            )
        ];

        const table = document.createElement("table");
        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");

        for (const column of columns) {
            const th = document.createElement("th");
            th.scope = "col";
            th.textContent = column;
            headerRow.appendChild(th);
        }

        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");

        for (const client of clients) {
            const row = document.createElement("tr");

            for (const column of columns) {
                const cell = document.createElement("td");

                const value =
                    client && typeof client === "object"
                        ? client[column]
                        : client;

                cell.textContent =
                    value === null || value === undefined
                        ? ""
                        : String(value);

                row.appendChild(cell);
            }

            tbody.appendChild(row);
        }

        table.appendChild(tbody);
        clientsContainer.appendChild(table);

        clientsStatus.textContent = `Connected clients: ${clients.length}`;
    }

    async function fetchJson(url) {
        const response = await fetch(url);
        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
            const error = new Error(
                result.detail || `Request failed: ${response.status}`
            );

            error.status = response.status;
            throw error;
        }

        return result;
    }

    async function loadDeviceDetails() {
        if (!deviceId) {
            deviceStatus.textContent = "Device ID is missing.";
            return;
        }

        const baseUrl = `/api/devices/${encodeURIComponent(deviceId)}`;

        try {
            const device = await fetchJson(baseUrl);

            deviceName.textContent = device.name || "Network device";

            deviceInfo.replaceChildren();

            addInfoRow("ID", device.id);
            addInfoRow("Type", device.type);
            addInfoRow("Manufacturer", device.manufacturer);
            addInfoRow("Model", device.model);
            addInfoRow("Integration", device.integration_id);
            addInfoRow(
                "Enabled",
                device.enabled === 1 || device.enabled === true ? "Yes" : "No"
            );

            if (
                device.type !== "router" &&
                device.type !== "access_point" &&
                device.type !== "switch"
            ) {
                deviceStatus.textContent =
                    "This device is not a network device.";
                clientsSection.hidden = true;
                return;
            }

            if (device.enabled !== 1 && device.enabled !== true) {
                deviceStatus.textContent = "Device is disabled.";
                clientsSection.hidden = true;
                return;
            }

            let state = null;

            try {
                state = await fetchJson(`${baseUrl}/state`);

                deviceStatus.textContent =
                    state.online === true
                        ? "Device is online."
                        : state.online === false
                            ? "Device is offline."
                            : "Device state is unavailable.";
            } catch (error) {
                console.error("Could not load device state:", error);
                deviceStatus.textContent = "Device state is unavailable.";
            }

            if (device.type !== "router") {
                clientsSection.hidden = true;
                return;
            }

            clientsSection.hidden = false;
            clientsContainer.replaceChildren();
            clientsStatus.textContent = "Loading connected devices…";

            if (state && state.online === false) {
                clientsStatus.textContent =
                    "DHCP clients are unavailable while the router is offline.";
                return;
            }

            try {
                const result = await fetchJson(`${baseUrl}/clients`);
                renderClients(result.clients);
            } catch (error) {
                console.error("Could not load DHCP clients:", error);

                clientsContainer.replaceChildren();

                clientsStatus.textContent =
                    error.status === 409
                        ? "DHCP client information is not supported by this device."
                        : "Could not load DHCP clients.";
            }
        } catch (error) {
            console.error("Could not load network device:", error);

            deviceStatus.textContent =
                `Could not load device details: ${error.message}`;

            clientsSection.hidden = true;
        }
    }

    loadDeviceDetails();
}