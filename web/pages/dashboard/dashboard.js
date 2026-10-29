
import { t } from "../../assets/js/i18n.js";

let statusTimer = null;
let activeController = null;
let pageInstance = 0;
let languageChangeHandler = null;

const cards = [
    { id: "system", title: "System", description: "Application health" },
    { id: "network", title: "Network", description: "Network status" },
    { id: "devices", title: "Devices", description: "Connected devices" },
    { id: "energy", title: "Energy", description: "Energy consumption" },
    { id: "integrations", title: "Integrations", description: "Connected services" },
    { id: "climate", title: "Climate", description: "Temperature and humidity" },
    { id: "security", title: "Security", description: "Security status" },
    { id: "events", title: "Events", description: "Recent events" }
];

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

    const grid = document.getElementById("dashboard-grid");

    if (!grid) {
        return;
    }

    const currentInstance = ++pageInstance;
    const checkInterval = 10000;

    grid.replaceChildren();

    for (const card of cards) {
        const element = document.createElement("section");
        element.className = "dashboard-card";
        element.dataset.cardId = card.id;

        const title = document.createElement("h2");
        title.className = "dashboard-card__title";
        title.textContent = card.id === "system"
            ? t("dashboard.systemStatus")
            : card.title;

        const description = document.createElement("p");
        description.className = "dashboard-card__description";
        description.textContent = card.description;

        element.append(title, description);

        if (card.id === "system") {
            const status = document.createElement("div");
            status.className = "system-status";

            const indicator = document.createElement("span");
            indicator.className = "system-status__indicator";
            indicator.id = "system-status-indicator";
            indicator.setAttribute("role", "status");
            indicator.setAttribute("aria-label", t("dashboard.checking"));

            const content = document.createElement("div");
            content.className = "system-status__content";

            const message = document.createElement("p");
            message.className = "system-status__message";
            message.id = "system-status-message";
            message.dataset.i18n = "dashboard.checking";
            message.setAttribute("aria-live", "polite");
            message.textContent = t("dashboard.checking");

            const footer = document.createElement("p");
            footer.className = "system-status__last-check";

            const label = document.createElement("span");
            label.dataset.i18n = "dashboard.lastCheck";
            label.textContent = t("dashboard.lastCheck");

            const time = document.createElement("time");
            time.id = "system-status-last-check";
            time.textContent = "—";

            footer.append(
                label,
                document.createTextNode(" "),
                time
            );

            content.append(message, footer);
            status.append(indicator, content);
            element.append(status);
        }

        grid.append(element);
    }

    let currentStatus = "checking";

    function updateStatus(status) {
        currentStatus = status;

        const statusKeys = {
            checking: "dashboard.checking",
            online: "dashboard.online",
            offline: "dashboard.offline"
        };

        const indicator = document.getElementById(
            "system-status-indicator"
        );

        const message = document.getElementById(
            "system-status-message"
        );

        if (!indicator || !message) {
            return;
        }

        const key = statusKeys[status];

        indicator.className = [
            "system-status__indicator",
            status === "online" ? "online" : "",
            status === "offline" ? "offline" : ""
        ].filter(Boolean).join(" ");

        indicator.setAttribute("aria-label", t(key));
        message.dataset.i18n = key;
        message.textContent = t(key);
    }

    languageChangeHandler = () => {
        const systemTitle = grid.querySelector(
            '[data-card-id="system"] .dashboard-card__title'
        );

        const lastCheckLabel = grid.querySelector(
            '[data-card-id="system"] .system-status__last-check span'
        );

        if (systemTitle) {
            systemTitle.textContent = t("dashboard.systemStatus");
        }

        if (lastCheckLabel) {
            lastCheckLabel.textContent = t("dashboard.lastCheck");
        }

        updateStatus(currentStatus);
    };

    window.addEventListener(
        "language:changed",
        languageChangeHandler
    );

    async function checkStatus() {
        const indicator = document.getElementById(
            "system-status-indicator"
        );

        const lastCheck = document.getElementById(
            "system-status-last-check"
        );

        if (
            currentInstance !== pageInstance ||
            !grid.isConnected ||
            !indicator ||
            !lastCheck
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
                grid.isConnected
            ) {
                const checkedAt = new Date();
                const time = document.getElementById(
                    "system-status-last-check"
                );

                if (time) {
                    time.dateTime = checkedAt.toISOString();
                    time.textContent =
                        checkedAt.toLocaleTimeString();
                }

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
