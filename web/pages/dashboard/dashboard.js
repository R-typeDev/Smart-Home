
import { t } from "../../assets/js/i18n.js";

let statusTimer = null;
let activeController = null;
let pageInstance = 0;
let languageChangeHandler = null;

export function init() {
    if (statusTimer !== null) {
        clearTimeout(statusTimer);
        statusTimer = null;
    }

    if (activeController !== null) {
        activeController.abort();
        activeController = null;
    }

    if (languageChangeHandler !== null) {
        window.removeEventListener(
            "language:changed",
            languageChangeHandler
        );
        languageChangeHandler = null;
    }

    const indicator = document.getElementById(
        "system-status-indicator"
    );
    const message = document.getElementById(
        "system-status-message"
    );
    const lastCheck = document.getElementById(
        "system-status-last-check"
    );

    if (!indicator || !message || !lastCheck) {
        return;
    }

    const currentInstance = ++pageInstance;
    const checkInterval = 10000;
    let currentStatus = "checking";

    function updateStatus(status) {
        currentStatus = status;

        const statusClasses = {
            checking: "",
            online: "online",
            offline: "offline"
        };

        const statusKeys = {
            checking: "dashboard.checking",
            online: "dashboard.online",
            offline: "dashboard.offline"
        };

        const key = statusKeys[status];

        indicator.className = [
            "system-status__indicator",
            statusClasses[status]
        ].filter(Boolean).join(" ");

        indicator.setAttribute("aria-label", t(key));

        message.dataset.i18n = key;
        message.textContent = t(key);
    }

    languageChangeHandler = () => {
        updateStatus(currentStatus);
    };

    window.addEventListener(
        "language:changed",
        languageChangeHandler
    );

    async function checkStatus() {
        if (
            currentInstance !== pageInstance ||
            !indicator.isConnected
        ) {
            return;
        }

        const controller = new AbortController();
        activeController = controller;

        try {
            const response = await fetch("/health", {
                method: "GET",
                cache: "no-store",
                signal: controller.signal,
                headers: {
                    Accept: "application/json"
                }
            });

            if (!response.ok) {
                throw new Error("Health check failed");
            }

            const data = await response.json();

            if (
                data.status !== "ok" ||
                currentInstance !== pageInstance
            ) {
                throw new Error("System is not healthy");
            }

            updateStatus("online");
        } catch (error) {
            if (
                error.name === "AbortError" ||
                currentInstance !== pageInstance
            ) {
                return;
            }

            updateStatus("offline");
        } finally {
            if (activeController === controller) {
                activeController = null;
            }

            if (
                currentInstance === pageInstance &&
                indicator.isConnected
            ) {
                const checkedAt = new Date();

                lastCheck.dateTime =
                    checkedAt.toISOString();

                lastCheck.textContent =
                    checkedAt.toLocaleTimeString();

                statusTimer = setTimeout(
                    checkStatus,
                    checkInterval
                );
            }
        }
    }

    updateStatus("checking");
    checkStatus();
}
