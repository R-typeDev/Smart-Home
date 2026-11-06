
import {
    getLanguage,
    loadModuleTranslations
} from "/assets/js/i18n.js";

const API = "/api/integrations/tuya_cloud/connections";

const LANGUAGES_PATH =
    "/pages/integrations/modules/tuya/cloud/languages";

const REGION_NAMES = {
    us: "US",
    us_east: "US East",
    eu: "Europe",
    eu_west: "Europe West",
    in: "India",
    sg: "Singapore"
};

let translations = {};

async function loadTranslations() {
    translations = await loadModuleTranslations(LANGUAGES_PATH);
}

function translate(key) {
    return translations[key] ?? key;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);
}

async function request(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers
        }
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(
            data.detail || `HTTP ${response.status}`
        );
    }

    return data;
}

function formatDate(timestamp) {
    if (!timestamp) {
        return translate("lastSyncNever");
    }

    return new Date(timestamp).toLocaleString(
        getLanguage() === "ru" ? "ru-RU" : "en-US"
    );
}

function maskUserId(userId) {
    if (!userId) {
        return "—";
    }

    if (userId.length <= 8) {
        return "••••";
    }

    return `${userId.slice(0, 4)}••••${userId.slice(-4)}`;
}

function getDeviceName(device) {
    return device.name ||
        device.product_name ||
        device.id ||
        translate("device");
}

function renderDevices(container, devices) {
    if (!Array.isArray(devices) || devices.length === 0) {
        container.innerHTML = `
            <div class="cloud-empty">
                ${escapeHtml(translate("noDevices"))}
            </div>
        `;
        return;
    }

    container.innerHTML = devices.map(device => {
        const online = device.online === true;

        return `
            <article class="cloud-device">
                <div class="cloud-device-icon">
                    <span>⌂</span>
                </div>

                <div class="cloud-device-info">
                    <strong class="cloud-device-name">
                        ${escapeHtml(getDeviceName(device))}
                    </strong>

                    <span class="cloud-device-id">
                        ${escapeHtml(translate("deviceId"))}:
                        ${escapeHtml(device.id || "—")}
                    </span>

                    <span class="cloud-device-category">
                        ${escapeHtml(translate("category"))}:
                        ${escapeHtml(device.category || "—")}
                    </span>
                </div>

                <span class="cloud-device-status ${online ? "is-online" : "is-offline"}">
                    ${escapeHtml(
                        online
                            ? translate("online")
                            : translate("offline")
                    )}
                </span>
            </article>
        `;
    }).join("");
}

export async function init() {
    const root = document.querySelector("[data-tuya-cloud]");

    if (!root) {
        return;
    }

    const elements = {
        message: root.querySelector("[data-cloud-message]"),
        connectionName: root.querySelector("[data-cloud-connection-name]"),
        status: root.querySelector("[data-cloud-status]"),
        region: root.querySelector("[data-cloud-region]"),
        userId: root.querySelector("[data-cloud-user-id]"),
        enabled: root.querySelector("[data-cloud-enabled]"),
        lastSync: root.querySelector("[data-cloud-last-sync]"),
        deviceCount: root.querySelector("[data-cloud-device-count]"),
        devices: root.querySelector("[data-cloud-devices]"),
        testButton: root.querySelector("[data-cloud-test]"),
        refreshButton: root.querySelector("[data-cloud-refresh]")
    };

    let connection = null;
    let lastSync = null;

    function showMessage(message, type = "info") {
        elements.message.textContent = message;
        elements.message.className = `cloud-notice is-${type}`;
        elements.message.hidden = false;
    }

    function clearMessage() {
        elements.message.hidden = true;
        elements.message.textContent = "";
    }

    function setLoading(loading) {
        elements.testButton.disabled = loading;
        elements.refreshButton.disabled = loading;
    }

    function renderConnection() {
        if (!connection) {
            return;
        }

        const settings = connection.settings || {};
        const region = settings.region?.value || "";
        const userId = settings.user_id?.value || "";

        elements.connectionName.textContent = connection.name || "Tuya Cloud";
        elements.region.textContent = REGION_NAMES[region] || region || "—";
        elements.userId.textContent = maskUserId(userId);

        elements.enabled.textContent = connection.enabled
            ? translate("enabled")
            : translate("disabled");

        elements.status.textContent = connection.configured
            ? translate("connected")
            : translate("disconnected");

        elements.status.className = connection.configured
            ? "cloud-status is-connected"
            : "cloud-status is-disconnected";
    }

    async function loadDevices() {
        if (!connection) {
            return;
        }

        elements.devices.innerHTML = `
            <div class="cloud-empty">
                ${escapeHtml(translate("loading"))}
            </div>
        `;

        const response = await request(
            `${API}/${encodeURIComponent(connection.id)}/devices`
        );

        const devices = response.result || [];

        if (!Array.isArray(devices)) {
            throw new Error("Unexpected Tuya devices response.");
        }

        renderDevices(elements.devices, devices);

        elements.deviceCount.textContent = devices.length;
        lastSync = Date.now();
        elements.lastSync.textContent = formatDate(lastSync);
    }

    async function testConnection() {
        if (!connection) {
            return;
        }

        clearMessage();
        setLoading(true);

        try {
            const result = await request(
                `${API}/${encodeURIComponent(connection.id)}/test`,
                { method: "POST" }
            );

            if (result.connected) {
                showMessage(translate("testSuccess"), "success");
                await loadDevices();
            }
        } catch (error) {
            showMessage(
                `${translate("connectionError")} ${error.message}`,
                "error"
            );
        } finally {
            setLoading(false);
        }
    }

    async function refreshDevices() {
        if (!connection) {
            return;
        }

        clearMessage();
        setLoading(true);

        try {
            await loadDevices();
            showMessage(translate("devicesUpdated"), "success");
        } catch (error) {
            showMessage(
                `${translate("loadError")} ${error.message}`,
                "error"
            );
        } finally {
            setLoading(false);
        }
    }

    async function loadPage() {
        setLoading(true);

        try {
            const connections = await request(API);

            if (!Array.isArray(connections) || connections.length === 0) {
                showMessage(translate("noConnection"), "warning");
                elements.devices.innerHTML = `
                    <div class="cloud-empty">
                        ${escapeHtml(translate("notConfigured"))}
                    </div>
                `;
                return;
            }

            connection = connections[0];

            renderConnection();

            if (!connection.configured) {
                showMessage(translate("notConfigured"), "warning");
                return;
            }

            await loadDevices();

        } catch (error) {
            showMessage(
                `${translate("loadError")} ${error.message}`,
                "error"
            );
        } finally {
            setLoading(false);
        }
    }

    async function updateLanguage() {
        try {
            await loadTranslations();
            renderConnection();

            if (connection?.configured) {
                await loadDevices();
            } else {
                await loadPage();
            }

            elements.lastSync.textContent = formatDate(lastSync);
        } catch (error) {
            console.error("Tuya Cloud language update failed:", error);
        }
    }

    elements.testButton.addEventListener("click", testConnection);
    elements.refreshButton.addEventListener("click", refreshDevices);

    await loadTranslations();

    elements.lastSync.textContent = translate("lastSyncNever");

    await loadPage();

    window.addEventListener("language:changed", updateLanguage);
}
