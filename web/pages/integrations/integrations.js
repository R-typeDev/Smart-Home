import { initIntegrationsCatalog } from "/assets/js/integrations-catalog.js";

export function init() {
    initIntegrationsCatalog(
        document.querySelector("[data-integrations-catalog]")
    );
}
