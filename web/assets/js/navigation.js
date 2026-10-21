import { loadPage } from "./component-loader.js";
import { applyTranslations } from "./i18n.js";

const pages = {
    "/dashboard": {
        name: "dashboard",
        html: "/pages/dashboard/dashboard.html",
        js: "/pages/dashboard/dashboard.js",
        css: "/pages/dashboard/dashboard.css"
    },
    "/devices": {
        name: "devices",
        html: "/pages/devices/devices.html",
        js: "/pages/devices/devices.js",
        css: "/pages/devices/devices.css"
    },
    "/network": {
        name: "network",
        html: "/pages/network/network.html",
        js: "/pages/network/network.js",
        css: "/pages/network/network.css"
    },
    "/integrations": {
        name: "integrations",
        html: "/pages/integrations/integrations.html",
        js: "/pages/integrations/integrations.js",
        css: "/pages/integrations/integrations.css"
    },
    "/settings": {
        name: "settings",
        html: "/pages/settings/settings.html",
        js: "/pages/settings/settings.js",
        css: "/pages/settings/settings.css"
    }
};

async function navigate(path, updateHistory = true) {
    const route = pages[path] ? path : "/dashboard";

    if (updateHistory) {
        history.pushState({}, "", route);
    }

    document.querySelectorAll("a[data-route]").forEach((link) => {
        if (link.dataset.route === route) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    });

    await loadPage(pages[route]);
    applyTranslations();
}

export function startNavigation() {
    document.addEventListener("click", (event) => {
        const link = event.target.closest("a[data-route]");

        if (
            !link ||
            event.ctrlKey ||
            event.metaKey ||
            event.shiftKey ||
            event.altKey ||
            event.button !== 0
        ) {
            return;
        }

        event.preventDefault();
        navigate(link.dataset.route);
    });

    window.addEventListener("popstate", () => {
        navigate(location.pathname, false);
    });

    window.addEventListener("language:changed", () => {
        applyTranslations();
    });

    const path = pages[location.pathname]
        ? location.pathname
        : "/dashboard";

    if (location.pathname !== path) {
        history.replaceState({}, "", path);
    }

    navigate(path, false);
}
