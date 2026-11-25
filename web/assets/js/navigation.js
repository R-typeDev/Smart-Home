
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
        html: "/pages/devices/list/list.html",
        js: "/pages/devices/list/list.js",
        css: "/pages/devices/list/list.css"
    },

    "/devices/add": {
        name: "device-add",
        html: "/pages/devices/add/add.html",
        js: "/pages/devices/add/add.js",
        css: "/pages/devices/add/add.css"
    },

    "/network": {
        name: "network-overview",
        html: "/pages/network/overview/overview.html",
        js: "/pages/network/overview/overview.js",
        css: "/pages/network/overview/overview.css"
    },

    "/network/topology": {
        name: "network-topology",
        html: "/pages/network/topology/topology.html",
        js: "/pages/network/topology/topology.js",
        css: "/pages/network/topology/topology.css"
    },

    "/network/devices": {
        name: "network-devices",
        html: "/pages/network/devices/devices.html",
        js: "/pages/network/devices/devices.js",
        css: "/pages/network/devices/devices.css"
    },

    "/network/connections": {
        name: "network-connections",
        html: "/pages/network/connections/connections.html",
        js: "/pages/network/connections/connections.js",
        css: "/pages/network/connections/connections.css"
    },

    "/network/diagnostics": {
        name: "network-diagnostics",
        html: "/pages/network/diagnostics/diagnostics.html",
        js: "/pages/network/diagnostics/diagnostics.js",
        css: "/pages/network/diagnostics/diagnostics.css"
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
    },

    "/settings/general": {
        name: "settings-general",
        html: "/pages/settings/general/general.html",
        js: "/pages/settings/general/general.js",
        css: "/pages/settings/general/general.css"
    },

    "/settings/dashboard": {
        name: "settings-dashboard",
        html: "/pages/settings/dashboard/dashboard-settings.html",
        js: "/pages/settings/dashboard/dashboard-settings.js",
        css: "/pages/settings/dashboard/dashboard-settings.css"
    },

    "/settings/appearance": {
        name: "settings-appearance",
        html: "/pages/settings/appearance/appearance.html",
        js: "/pages/settings/appearance/appearance.js",
        css: "/pages/settings/appearance/appearance.css"
    },

    "/settings/system": {
        name: "settings-system",
        html: "/pages/settings/system/system.html",
        js: "/pages/settings/system/system.js",
        css: "/pages/settings/system/system.css"
    },

    "/settings/system/logs": {
        name: "system-logs",
        html: "/pages/settings/system/system-logs/system-logs.html",
        js: "/pages/settings/system/system-logs/system-logs.js",
        css: "/pages/settings/system/system-logs/system-logs.css"
    },

    "/settings/system/event-logs": {
        name: "event-logs",
        html: "/pages/settings/system/event-logs/event-logs.html",
        js: "/pages/settings/system/event-logs/event-logs.js",
        css: "/pages/settings/system/event-logs/event-logs.css"
    },

    "/settings/system/activity-logs": {
        name: "activity-logs",
        html: "/pages/settings/system/activity-logs/activity-logs.html",
        js: "/pages/settings/system/activity-logs/activity-logs.js",
        css: "/pages/settings/system/activity-logs/activity-logs.css"
    },

    "/settings/system/device-logs": {
        name: "device-logs",
        html: "/pages/settings/system/device-logs/device-logs.html",
        js: "/pages/settings/system/device-logs/device-logs.js",
        css: "/pages/settings/system/device-logs/device-logs.css"
    },

    "/settings/storage": {
        name: "settings-storage",
        html: "/pages/settings/storage/storage.html",
        js: "/pages/settings/storage/storage.js",
        css: "/pages/settings/storage/storage.css"
    },

    "/settings/about": {
        name: "settings-about",
        html: "/pages/settings/about/about.html",
        js: "/pages/settings/about/about.js",
        css: "/pages/settings/about/about.css"
    }
};

const integrationPages = {
    "#tplink": {
        name: "tplink",
        html: "/pages/integrations/modules/tplink/tplink.html",
        js: "/pages/integrations/modules/tplink/tplink.js",
        css: "/pages/integrations/modules/tplink/tplink.css"
    },

    "#tuya": {
        name: "tuya",
        html: "/pages/integrations/modules/tuya/tuya.html",
        js: "/pages/integrations/modules/tuya/tuya.js",
        css: "/pages/integrations/modules/tuya/tuya.css"
    },

    "#tuya/cloud": {
        name: "tuya-cloud",
        html: "/pages/integrations/modules/tuya/cloud/cloud.html",
        js: "/pages/integrations/modules/tuya/cloud/cloud.js",
        css: "/pages/integrations/modules/tuya/cloud/cloud.css"
    },

    "#tuya/local": {
        name: "tuya-local",
        html: "/pages/integrations/modules/tuya/local/local.html",
        js: "/pages/integrations/modules/tuya/local/local.js",
        css: "/pages/integrations/modules/tuya/local/local.css"
    },

    "#tplink/router": {
        name: "tplink-router",
        html: "/pages/integrations/modules/tplink/router/router.html",
        js: "/pages/integrations/modules/tplink/router/router.js",
        css: "/pages/integrations/modules/tplink/router/router.css"
    }
};

function resolveRoute(path) {
    const [rawPathname, hash = ""] = path.split("#");

    const pathname = rawPathname.length > 1
        ? rawPathname.replace(/\/+$/, "")
        : rawPathname;

    if (pathname === "/integrations" && hash) {
        const integrationPage = integrationPages[`#${hash}`];

        if (integrationPage) {
            return {
                path: `${pathname}#${hash}`,
                page: integrationPage
            };
        }
    }

    if (pages[pathname]) {
        return {
            path: pathname,
            page: pages[pathname]
        };
    }

    if (/^\/devices\/item\/[^/]+$/.test(pathname)) {
        return {
            path: pathname,
            page: {
                name: "device-item",
                html: "/pages/devices/item/item.html",
                js: "/pages/devices/item/item.js",
                css: "/pages/devices/item/item.css"
            }
        };
    }

    if (/^\/network\/item\/[^/]+$/.test(pathname)) {
        return {
            path: pathname,
            page: {
                name: "network-item",
                html: "/pages/network/item/item.html",
                js: "/pages/network/item/item.js",
                css: "/pages/network/item/item.css"
            }
        };
    }

    return {
        path: "/dashboard",
        page: pages["/dashboard"]
    };
}

async function navigate(path, updateHistory = true) {
    const route = resolveRoute(path);

    if (updateHistory) {
        history.pushState({}, "", route.path);
    }

    document.querySelectorAll("a[data-route]").forEach((link) => {
        if (link.dataset.route === route.path) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    });

    await loadPage(route.page);
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
        navigate(location.pathname + location.hash, false);
    });

    window.addEventListener("language:changed", () => {
        applyTranslations();
    });

    const route = resolveRoute(location.pathname + location.hash);

    if (location.pathname + location.hash !== route.path) {
        history.replaceState({}, "", route.path);
    }

    navigate(route.path, false);
}
