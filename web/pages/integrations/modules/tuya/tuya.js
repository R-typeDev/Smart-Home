import { initPlatformCatalog } from "/assets/js/integrations-catalog.js";

export function init() {
    initPlatformCatalog(
        document.querySelector("[data-platform-integrations]"),
        "tuya"
    );
}
