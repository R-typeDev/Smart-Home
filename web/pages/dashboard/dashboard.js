
let statusTimer = null;
let activeController = null;
let pageInstance = 0;

export function init() {
    if (statusTimer !== null) {
        clearTimeout(statusTimer);
        statusTimer = null;
    }

    if (activeController !== null) {
        activeController.abort();
        activeController = null;
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

            indicator.className =
                "system-status__indicator online";

            indicator.setAttribute(
                "aria-label",
                "System online"
            );

            message.dataset.i18n = "dashboard.online";
            message.textContent = "System is running";
        } catch (error) {
            if (
                error.name === "AbortError" ||
                currentInstance !== pageInstance
            ) {
                return;
            }

            indicator.className =
                "system-status__indicator offline";

            indicator.setAttribute(
                "aria-label",
                "System offline"
            );

            message.dataset.i18n = "dashboard.offline";
            message.textContent = "System unavailable";
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

    checkStatus();
}
