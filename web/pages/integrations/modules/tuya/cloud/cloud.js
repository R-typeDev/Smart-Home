
import {
    getLanguage,
    loadModuleTranslations
} from "/assets/js/i18n.js";

const API = "/api/integrations/tuya_cloud/connections";
const STATUS_API = "/api/integrations/tuya_cloud/status";
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

function getDeviceId(device) {
    return device.external_id ||
        device.id ||
        device.device_id ||
        "";
}

function getDeviceName(device) {
    return device.name ||
        device.product_name ||
        getDeviceId(device) ||
        translate("device");
}

function isDeviceOnline(device) {
    const value =
        device.online ??
        device.is_online ??
        device.metadata?.online;

    if (typeof value === "boolean") {
        return value;
    }

    if (typeof value === "number") {
        return value === 1;
    }

    if (typeof value === "string") {
        return ["true", "1", "online"].includes(
            value.trim().toLowerCase()
        );
    }

    return false;
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
        const online = isDeviceOnline(device);
        const registration = getDeviceRegistrationInfo(device);
        const externalId = getDeviceId(device);

        const registrationHtml = registration.cloudConnected
            ? `
                <span class="cloud-device-registered">
                    ${escapeHtml(uiText("Добавлено", "Added"))}
                </span>
            `
            : `
                <button
                    type="button"
                    class="cloud-button cloud-button-primary cloud-device-add"
                    data-cloud-add-device="${escapeHtml(externalId)}"
                >
                    ${escapeHtml(uiText("Добавить", "Add"))}
                </button>
            `;

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
                        ${escapeHtml(externalId || "—")}
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
    let integrationEnabled = false;
    let lastSync = null;
    let loading = false;

    function showMessage(message, type = "info") {
        elements.message.textContent = message;
        elements.message.className = `cloud-notice is-${type}`;
        elements.message.hidden = false;
    }

    function clearMessage() {
        elements.message.hidden = true;
        elements.message.textContent = "";
    }

    function isAvailable() {
        return Boolean(
            integrationEnabled &&
            connection &&
            connection.enabled &&
            connection.configured
        );
    }

    function setLoading(value) {
        loading = value;

        const unavailable = !integrationEnabled ||
            !connection ||
            !connection.enabled ||
            loading;

        elements.testButton.disabled = unavailable;
        elements.refreshButton.disabled = unavailable;
    }

    function renderConnection() {
        if (!connection) {
            return;
        }

        const settings = connection.settings || {};
        const region = settings.region?.value || "";
        const userId = settings.user_id?.value || "";

        elements.connectionName.textContent =
            connection.name || "Tuya Cloud";

        elements.region.textContent =
            REGION_NAMES[region] || region || "—";

        elements.userId.textContent = maskUserId(userId);

        elements.enabled.textContent = connection.enabled
            ? translate("enabled")
            : translate("disabled");

        elements.status.textContent = !integrationEnabled ||
            !connection.enabled
            ? translate("disabled")
            : connection.configured
                ? translate("connected")
                : translate("disconnected");

        elements.status.className =
            integrationEnabled &&
            connection.enabled &&
            connection.configured
                ? "cloud-status is-connected"
                : "cloud-status is-disconnected";

        setLoading(loading);
    }

    function renderDisabledState() {
        elements.deviceCount.textContent = "0";

        elements.devices.innerHTML = `
            <div class="cloud-empty">
                ${escapeHtml(
                    uiText(
                        "Интеграция Tuya Cloud выключена. Включите её в настройках, чтобы загрузить устройства.",
                        "Tuya Cloud integration is disabled. Enable it in settings to load devices."
                    )
                )}
            </div>
        `;

        showMessage(
            uiText(
                "Интеграция Tuya Cloud выключена.",
                "Tuya Cloud integration is disabled."
            ),
            "warning"
        );
    }

    async function loadDevices() {
        if (!isAvailable()) {
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
        if (
            !isAvailable() ||
            !externalId ||
            button.disabled
        ) {
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
        if (!isAvailable()) {
            return;
        }

        clearMessage();
        setLoading(true);

        try {
            const result = await request(
                `${API}/${encodeURIComponent(connection.id)}/test`,
                { method: "POST" }
            );

            if (result.success || result.connected) {
                showMessage(
                    result.message || translate("testSuccess"),
                    "success"
                );
                await loadDevices();
            } else {
                showMessage(
                    result.message || translate("connectionError"),
                    "error"
                );
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
        if (!isAvailable()) {
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
            const status = await request(STATUS_API);

            integrationEnabled = Boolean(
                status.implemented &&
                status.enabled &&
                status.active
            );

            const connections = await request(API);

            if (!Array.isArray(connections) || connections.length === 0) {
                connection = null;
                renderConnection();

                showMessage(translate("noConnection"), "warning");

                elements.deviceCount.textContent = "0";
                elements.devices.innerHTML = `
                    <div class="cloud-empty">
                        ${escapeHtml(translate("notConfigured"))}
                    </div>
                `;
                return;
            }

            connection =
                connections.find(item => item.enabled && item.configured) ||
                connections.find(item => item.enabled) ||
                connections[0];

            renderConnection();

            if (!integrationEnabled || !connection.enabled) {
                renderDisabledState();
                return;
            }

            if (!connection.configured) {
                showMessage(translate("notConfigured"), "warning");

                elements.deviceCount.textContent = "0";
                elements.devices.innerHTML = `
                    <div class="cloud-empty">
                        ${escapeHtml(translate("notConfigured"))}
                    </div>
                `;
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

            if (!integrationEnabled || (connection && !connection.enabled)) {
                renderDisabledState();
            } else if (isAvailable()) {
                await loadDevices();
            } else if (!connection) {
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
