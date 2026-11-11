
import {
    getLanguage,
    loadModuleTranslations
} from "/assets/js/i18n.js";

const API = "/api/integrations/tuya_cloud/connections";
const DEVICES_API = "/api/integrations/tuya_cloud/devices";
const REGISTER_API = "/api/devices/discovery/register";

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

function uiText(ru, en) {
    return getLanguage() === "ru" ? ru : en;
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
        throw new Error(data.detail || `HTTP ${response.status}`);
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

function getDeviceRegistrationInfo(device) {
    const registeredDevice = device.registered_device;

    if (!registeredDevice) {
        return {
            registered: false,
            cloudConnected: false,
            sources: []
        };
    }

    const sources = registeredDevice.sources || [];

    return {
        registered: true,
        cloudConnected: sources.some(
            source => source.integration_id === "tuya_cloud"
        ),
        sources
    };
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
        const registration = getDeviceRegistrationInfo(device);

        let registrationHtml = "";

        if (registration.cloudConnected) {
            registrationHtml = `
                <span class="cloud-device-registered">
                    ${escapeHtml(uiText("Добавлено", "Added"))}
                </span>
            `;
        } else {
            registrationHtml = `
                <button
                    type="button"
                    class="cloud-button cloud-button-primary cloud-device-add"
                    data-cloud-add-device="${escapeHtml(device.id)}"
                >
                    ${escapeHtml(uiText("Добавить", "Add"))}
                </button>
            `;
        }

        const sourceNames = registration.sources
            .map(source => source.source_name)
            .filter(Boolean);

        return `
            <article class="cloud-device">
                <div class="cloud-device-icon">
                    <img
                        src="/assets/icons/Cloud.png"
                        alt="Tuya Cloud"
                        width="24"
                        height="24"
                    >
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

                    ${registration.registered && sourceNames.length
                        ? `<span class="cloud-device-category">
                            ${escapeHtml(uiText("Источники", "Sources"))}:
                            ${escapeHtml(sourceNames.join(", "))}
                           </span>`
                        : ""}
                </div>

                <div class="cloud-device-actions">
                    <span class="cloud-device-status ${online ? "is-online" : "is-offline"}">
                        ${escapeHtml(
                            online
                                ? translate("online")
                                : translate("offline")
                        )}
                    </span>

                    ${registrationHtml}
                </div>
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
            `${DEVICES_API}?instance_id=${encodeURIComponent(connection.id)}`
        );

        const devices = response.devices;

        if (!Array.isArray(devices)) {
            throw new Error("Unexpected Tuya devices response.");
        }

        renderDevices(elements.devices, devices);

        elements.deviceCount.textContent =
            response.devices_total ?? devices.length;

        lastSync = Date.now();
        elements.lastSync.textContent = formatDate(lastSync);
    }

    async function addDevice(externalId, button) {
        if (!connection || !externalId || button.disabled) {
            return;
        }

        const originalText = button.textContent;

        button.disabled = true;
        button.textContent = uiText("Добавление...", "Adding...");

        try {
            await request(REGISTER_API, {
                method: "POST",
                body: JSON.stringify({
                    integration_id: "tuya_cloud",
                    instance_id: connection.id,
                    external_id: externalId
                })
            });

            await loadDevices();

            showMessage(
                uiText(
                    "Устройство добавлено в Smart Home.",
                    "Device added to Smart Home."
                ),
                "success"
            );
        } catch (error) {
            button.disabled = false;
            button.textContent = originalText;

            showMessage(
                `${uiText("Не удалось добавить устройство:", "Could not add device:")} ${error.message}`,
                "error"
            );
        }
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
                connection = null;
                showMessage(translate("noConnection"), "warning");

                elements.deviceCount.textContent = "0";
                elements.devices.innerHTML = `
                    <div class="cloud-empty">
                        ${escapeHtml(translate("notConfigured"))}
                    </div>
                `;
                return;
            }

            connection = connections.find(item => item.configured)
                || connections[0];

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

    elements.devices.addEventListener("click", event => {
        const button = event.target.closest("[data-cloud-add-device]");

        if (!button) {
            return;
        }

        addDevice(
            button.dataset.cloudAddDevice,
            button
        );
    });

    elements.testButton.addEventListener("click", testConnection);
    elements.refreshButton.addEventListener("click", refreshDevices);

    await loadTranslations();

    elements.lastSync.textContent = translate("lastSyncNever");

    await loadPage();

    window.addEventListener("language:changed", updateLanguage);
}
