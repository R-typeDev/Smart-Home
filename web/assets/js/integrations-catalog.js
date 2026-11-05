
import {
    applyTranslations,
    getLanguage,
    t
} from "/assets/js/i18n.js";

const CATALOG_URL = "/api/integrations/catalog";

const STATUS_KEYS = {
    enabled: "integrations.statusEnabled",
    disabled: "integrations.statusDisabled",
    not_implemented: "integrations.statusNotImplemented",
    error: "integrations.statusError"
};

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}

async function getCatalog() {
    const response = await fetch(CATALOG_URL);

    if (!response.ok) {
        throw new Error(`Catalog request failed: ${response.status}`);
    }

    return response.json();
}

function getMethodCountLabel(count) {
    let key;

    if (getLanguage() === "ru") {
        const lastTwoDigits = count % 100;
        const lastDigit = count % 10;

        if (lastTwoDigits >= 11 && lastTwoDigits <= 14) {
            key = "integrations.connectionMethodsMany";
        } else if (lastDigit === 1) {
            key = "integrations.connectionMethod";
        } else if (lastDigit >= 2 && lastDigit <= 4) {
            key = "integrations.connectionMethodsFew";
        } else {
            key = "integrations.connectionMethodsMany";
        }
    } else {
        key = count === 1
            ? "integrations.connectionMethod"
            : "integrations.connectionMethods";
    }

    return `${count} ${t(key)}`;
}

function renderStatus(status) {
    const key = STATUS_KEYS[status] ?? STATUS_KEYS.error;

    return `
        <span class="integration-status"
              data-i18n="${key}">
            ${escapeHtml(status)}
        </span>
    `;
}

function renderToggle(method, showLabel = true) {
    if (!method.implemented) {
        return "";
    }

    const enabled = method.enabled === true;

    return `
        <button
            type="button"
            class="integration-toggle"
            role="switch"
            aria-checked="${enabled}"
            aria-label="${enabled ? "Disable" : "Enable"}"
            data-integration-toggle="${escapeHtml(method.id)}"
            data-enabled="${enabled}">
            <span class="integration-toggle__track">
                <span class="integration-toggle__thumb"></span>
            </span>
            ${showLabel ? `
                <span class="integration-toggle__label"
                      data-i18n="${enabled
                          ? "integrations.disable"
                          : "integrations.enable"}">
                    ${enabled ? "Disable" : "Enable"}
                </span>
            ` : ""}
        </button>
    `;
}

function renderPlatformCard(platform) {
    const methods = platform.methods.map(method => `
        <div class="integration-method-row">
            <a class="integration-method"
               href="${escapeHtml(method.route)}"
               data-route="${escapeHtml(method.route)}">
                <span class="integration-method__info">
                    <span class="integration-method__name"
                          data-i18n="${escapeHtml(method.name_key)}">
                        ${escapeHtml(method.id)}
                    </span>
                    ${renderStatus(method.status)}
                </span>
            </a>
            ${renderToggle(method, false)}
        </div>
    `).join("");

    return `
        <article class="integration-card">
            <a class="integration-card__main"
               href="${escapeHtml(platform.route)}"
               data-route="${escapeHtml(platform.route)}">

                <div class="integration-card__header">
                    <div class="integration-card__brand">
                        <img
                            class="integration-logo"
                            src="${escapeHtml(platform.logo)}"
                            alt="${escapeHtml(platform.id)}"
                        >

                        <div class="integration-card__identity">
                            <h3 data-i18n="${escapeHtml(platform.name_key)}">
                                ${escapeHtml(platform.id)}
                            </h3>

                            <p data-i18n="${escapeHtml(platform.description_key)}">
                                ${escapeHtml(platform.id)}
                            </p>
                        </div>
                    </div>

                    <span class="integration-card__count">
                        ${getMethodCountLabel(platform.methods.length)}
                    </span>
                </div>
            </a>

            <div class="integration-methods">
                ${methods}
            </div>
        </article>
    `;
}

function renderMethodCard(method, platform) {
    const icon = method.connection_type === "cloud" ? "\u2601" : "\u2301";

    return `
        <article class="integration-card integration-method-card">
            <a class="integration-card__main"
               href="${escapeHtml(method.route)}"
               data-route="${escapeHtml(method.route)}">

                <div class="integration-card__header">
                    <img
                        class="integration-logo"
                        src="${escapeHtml(platform.logo)}"
                        alt="${escapeHtml(platform.id)}"
                    >

                    ${renderStatus(method.status)}
                </div>

                <div class="integration-method-card__type">
                    <span aria-hidden="true">${icon}</span>
                    <span data-i18n="${method.connection_type === "cloud"
                        ? "integrations.cloudConnection"
                        : "integrations.localConnection"}">
                        ${escapeHtml(method.connection_type)}
                    </span>
                </div>

                <h3 data-i18n="${escapeHtml(method.name_key)}">
                    ${escapeHtml(method.id)}
                </h3>

                <p data-i18n="${escapeHtml(method.description_key)}">
                    ${escapeHtml(method.id)}
                </p>
            </a>

            ${renderToggle(method)}
        </article>
    `;
}

async function refresh(container, renderer) {
    try {
        const catalog = await getCatalog();
        renderer(container, catalog);
        applyTranslations(container);
    } catch (error) {
        console.error("Failed to load integration catalog:", error);

        container.innerHTML = `
            <p class="integration-catalog-error"
               data-i18n="integrations.catalogError">
                Failed to load integrations.
            </p>
        `;

        applyTranslations(container);
    }
}

function renderPlatforms(container, catalog) {
    container.innerHTML = catalog
        .map(renderPlatformCard)
        .join("");
}

function renderPlatformMethods(container, catalog, platformId) {
    const platform = catalog.find(item => item.id === platformId);

    if (!platform) {
        container.innerHTML = "";
        return;
    }

    container.innerHTML = platform.methods
        .map(method => renderMethodCard(method, platform))
        .join("");
}

function bindToggle(container, renderer) {
    container.addEventListener("click", async event => {
        const button = event.target.closest("[data-integration-toggle]");

        if (!button || button.disabled) {
            return;
        }

        const integrationId = button.dataset.integrationToggle;
        const nextEnabled = button.dataset.enabled !== "true";

        button.disabled = true;

        try {
            const response = await fetch(
                `/api/integrations/${encodeURIComponent(integrationId)}/enabled`,
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        enabled: nextEnabled
                    })
                }
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            await refresh(container, renderer);
        } catch (error) {
            console.error(
                `Failed to change integration ${integrationId}:`,
                error
            );

            await refresh(container, renderer);
        }
    });
}

export function initIntegrationsCatalog(container) {
    if (!container) return;

    bindToggle(container, renderPlatforms);

    let catalog = [];

    const render = async () => {
        try {
            catalog = await getCatalog();
            renderPlatforms(container, catalog);
            applyTranslations(container);
        } catch (error) {
            console.error("Failed to load integration catalog:", error);

            container.innerHTML = `
                <p class="integration-catalog-error"
                   data-i18n="integrations.catalogError">
                    Failed to load integrations.
                </p>
            `;

            applyTranslations(container);
        }
    };

    window.addEventListener("language:changed", () => {
        if (container.isConnected && catalog.length) {
            renderPlatforms(container, catalog);
            applyTranslations(container);
        }
    });

    render();
}

export function initPlatformCatalog(container, platformId) {
    if (!container) return;

    const renderer = (target, catalog) => {
        renderPlatformMethods(target, catalog, platformId);
    };

    bindToggle(container, renderer);
    refresh(container, renderer);
}
