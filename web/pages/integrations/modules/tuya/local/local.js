
import {
    getLanguage,
    loadModuleTranslations
} from "/assets/js/i18n.js";

const API = "/api/integrations/tuya_local/devices";
const LANGUAGES_PATH =
    "/pages/integrations/modules/tuya/local/languages";

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
        throw new Error(data.detail || `HTTP ${response.status}`);
    }

    return data;
}

function formatDate(timestamp) {
    if (!timestamp) {
        return translate("lastTestNever");
    }

    return new Date(timestamp).toLocaleString(
        getLanguage() === "ru" ? "ru-RU" : "en-US"
    );
}

function getDeviceName(device) {
    return device.name || device.id || translate("device");
}

function renderDevices(container, devices, onTest) {
    if (!Array.isArray(devices) || devices.length === 0) {
        container.innerHTML = `
            <div class="local-empty">
                ${escapeHtml(translate("noDevices"))}
            </div>
        `;
        return;
    }

    container.innerHTML = devices.map(device => {
        const available =
            device.enabled &&
            device.connection_enabled &&
            device.integration_enabled;

        let unavailableReason = "";

        if (!device.integration_enabled) {
            unavailableReason = translate("integrationDisabled");
        } else if (!device.connection_enabled) {
            unavailableReason = translate("connectionDisabled");
        } else if (!device.enabled) {
            unavailableReason = translate("sourceDisabled");
        }

        return `
            <article class="local-device" data-device-id="${escapeHtml(device.id)}">
                <div class="local-device-icon">⌂</div>

                <div class="local-device-info">
                    <strong class="local-device-name">
                        ${escapeHtml(getDeviceName(device))}
                    </strong>

                    <span class="local-device-meta">
                        ${escapeHtml(translate("ipAddress"))}:
                        ${escapeHtml(device.ip_address || "—")}
                    </span>

                    <span class="local-device-meta">
                        ${escapeHtml(translate("protocolVersion"))}:
                        ${escapeHtml(device.version || "—")}
                    </span>

                    <span class="local-device-meta">
                        ${escapeHtml(translate("linked"))}
                    </span>

                    ${unavailableReason ? `
                        <span class="local-device-warning">
                            ${escapeHtml(unavailableReason)}
                        </span>
                    ` : ""}
                </div>

                <div class="local-device-controls">
                    <span class="local-device-status ${available ? "is-ready" : "is-disabled"}">
                        ${escapeHtml(
                            available
                                ? translate("enabled")
                                : translate("disabled")
                        )}
                    </span>

                    <button
                        type="button"
                        class="local-button local-button-primary"
                        data-local-test="${escapeHtml(device.id)}"
                        ${available ? "" : "disabled"}
                    >
                        ${escapeHtml(translate("test"))}
                    </button>

                    <span class="local-device-result" data-local-result="${escapeHtml(device.id)}"></span>
                </div>
            </article>
        `;
    }).join("");

    container.querySelectorAll("[data-local-test]").forEach(button => {
        button.addEventListener("click", () => {
            onTest(button.dataset.localTest, button);
        });
    });
}

export async function init() {
    const root = document.querySelector("[data-tuya-local]");

    if (!root) {
        return;
    }

    const elements = {
        message: root.querySelector("[data-local-message]"),
        summary: root.querySelector("[data-local-summary]"),
        status: root.querySelector("[data-local-status]"),
        deviceCount: root.querySelector("[data-local-device-count]"),
        count: root.querySelector("[data-local-count]"),
        protocol: root.querySelector("[data-local-protocol]"),
        keyStatus: root.querySelector("[data-local-key-status]"),
        lastTest: root.querySelector("[data-local-last-test]"),
        devices: root.querySelector("[data-local-devices]"),
        refreshButton: root.querySelector("[data-local-refresh]")
    };

    let devices = [];
    let lastTest = null;

    function showMessage(message, type = "info") {
        elements.message.textContent = message;
        elements.message.className = `local-notice is-${type}`;
        elements.message.hidden = false;
    }

    function clearMessage() {
        elements.message.hidden = true;
        elements.message.textContent = "";
    }

    function setLoading(loading) {
        elements.refreshButton.disabled = loading;
    }

    function renderSummary() {
        const total = devices.length;

        const available = devices.filter(device =>
            device.enabled &&
            device.connection_enabled &&
            device.integration_enabled
        ).length;

        elements.deviceCount.textContent = total;
        elements.count.textContent = total;

        elements.summary.textContent =
            `${available} / ${total}`;

        elements.status.textContent = total > 0
            ? translate("connected")
            : translate("disconnected");

        elements.status.className = total > 0
            ? "local-status is-connected"
            : "local-status is-disconnected";

        elements.keyStatus.textContent = total > 0
            ? translate("localKeySaved")
            : "—";

        elements.protocol.textContent = "Tuya LAN";
        elements.lastTest.textContent = formatDate(lastTest);
    }

    async function testDevice(deviceId, button) {
        const originalText = button.textContent;
        const resultElement = root.querySelector(
            `[data-local-result="${CSS.escape(deviceId)}"]`
        );

        button.disabled = true;
        button.textContent = translate("testing");

        if (resultElement) {
            resultElement.textContent = "";
            resultElement.className = "local-device-result";
        }

        try {
            const result = await request(
                `${API}/${encodeURIComponent(deviceId)}/test`,
                { method: "POST" }
            );

            lastTest = Date.now();
            elements.lastTest.textContent = formatDate(lastTest);

            const powerText = result.power === true
                ? translate("powerOn")
                : result.power === false
                    ? translate("powerOff")
                    : translate("unknown");

            if (resultElement) {
                resultElement.textContent =
                    `${translate("online")} · ${powerText}`;
                resultElement.classList.add("is-success");
            }

            showMessage(translate("testSuccess"), "success");

        } catch (error) {
            if (resultElement) {
                resultElement.textContent = translate("offline");
                resultElement.classList.add("is-error");
            }

            showMessage(
                `${translate("testError")} ${error.message}`,
                "error"
            );

        } finally {
            button.disabled = false;
            button.textContent = translate("test");
        }
    }

    async function loadDevices() {
        const response = await request(API);

        if (!Array.isArray(response)) {
            throw new Error("Unexpected Tuya Local response.");
        }

        devices = response;

        renderSummary();

        renderDevices(
            elements.devices,
            devices,
            testDevice
        );
    }

    async function refreshDevices() {
        clearMessage();
        setLoading(true);

        try {
            await loadDevices();
            showMessage(translate("refreshSuccess"), "success");
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
            await loadDevices();

            if (devices.length === 0) {
                showMessage(translate("noSource"), "warning");
            }
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
            await loadPage();
        } catch (error) {
            console.error("Tuya Local language update failed:", error);
        }
    }

    elements.refreshButton.addEventListener("click", refreshDevices);

    elements.lastTest.textContent = translate("lastTestNever");

    await loadTranslations();
    await loadPage();

    window.addEventListener("language:changed", updateLanguage);
}
