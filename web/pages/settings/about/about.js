
import { t } from "../../../assets/js/i18n.js";

let statusInterval = null;
let statusController = null;
let pageInstance = 0;

export function init() {
    destroy();

    const currentInstance = ++pageInstance;

    checkSystemStatus(currentInstance);

    statusInterval = setInterval(() => {
        checkSystemStatus(currentInstance);
    }, 10000);
}

export function destroy() {
    pageInstance += 1;

    if (statusInterval !== null) {
        clearInterval(statusInterval);
        statusInterval = null;
    }

    if (statusController !== null) {
        statusController.abort();
        statusController = null;
    }
}

async function checkSystemStatus(currentInstance) {
    if (statusController !== null) {
        statusController.abort();
    }

    const controller = new AbortController();
    statusController = controller;

    const indicator = document.querySelector("#about-status-indicator");
    const statusText = document.querySelector("#about-status-text");
    const lastCheck = document.querySelector("#about-last-check");

    if (!indicator || !statusText || !lastCheck) {
        return;
    }

    indicator.classList.remove("is-online", "is-offline");
    statusText.textContent = t("dashboard.checking");

    try {
        const response = await fetch("/health", {
            signal: controller.signal,
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error(`Health check failed: ${response.status}`);
        }

        const data = await response.json();

        if (currentInstance !== pageInstance || controller.signal.aborted) {
            return;
        }

        const isOnline = data.status === "ok";

        indicator.classList.add(
            isOnline ? "is-online" : "is-offline"
        );

        statusText.textContent = isOnline
            ? t("dashboard.online")
            : t("dashboard.offline");

        lastCheck.textContent = `${t("dashboard.lastCheck")} ${new Date().toLocaleTimeString()}`;
    } catch (error) {
        if (error.name === "AbortError") {
            return;
        }

        if (currentInstance !== pageInstance) {
            return;
        }

        indicator.classList.add("is-offline");
        statusText.textContent = t("dashboard.offline");
        lastCheck.textContent = `${t("dashboard.lastCheck")} ${new Date().toLocaleTimeString()}`;

        console.error("System status check failed:", error);
    } finally {
        if (statusController === controller) {
            statusController = null;
        }
    }
}
