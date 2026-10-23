
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
                clients.flatMap(client =>
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

    async function loadDeviceDetails() {
        if (!deviceId) {
            deviceStatus.textContent = "Device ID is missing.";
            return;
        }

        try {
            const response = await fetch(
                `/api/network/${encodeURIComponent(deviceId)}`
            );

            const result = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(result.detail || `Request failed: ${response.status}`);
            }

            const device = result.device;

            if (!device) {
                throw new Error("Device information was not returned by the API.");
            }

            deviceName.textContent = device.name || "Network device";

            deviceStatus.textContent =
                result.online === true
                    ? "Router is online."
                    : result.online === false
                        ? "Router is offline."
                        : result.integration_supported
                            ? "Connection status unavailable."
                            : "No network status integration is configured for this device.";

            deviceInfo.replaceChildren();

            addInfoRow("ID", device.id);
            addInfoRow("Type", device.type);
            addInfoRow("Manufacturer", device.manufacturer);
            addInfoRow("Model", device.model);
            addInfoRow("Integration", device.integration_id);
            addInfoRow("Enabled", device.enabled === 1 ? "Yes" : "No");

            if (device.type !== "router") {
                clientsSection.hidden = true;
                return;
            }

            clientsSection.hidden = false;
            clientsContainer.replaceChildren();

            if (result.online === false) {
                clientsStatus.textContent =
                    "DHCP clients are unavailable while the router is offline.";
            } else if (result.integration_supported) {
                renderClients(result.dhcp_clients);
            } else {
                clientsStatus.textContent =
                    "DHCP client information is not available for this integration.";
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
