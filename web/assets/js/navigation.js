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

const integrationPages = {
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
    const [pathname, hash = ""] = path.split("#");

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

    if (/^\/devices\/item\/[^/]+\/?$/.test(pathname)) {
        return {
            path: pathname.replace(/\/$/, ""),
            page: {
                name: "device-detail",
                html: "/pages/devices/device.html",
                js: "/pages/devices/device.js",
                css: "/pages/devices/device.css"
            }
        };
    }

    if (/^\/network\/item\/[^/]+\/?$/.test(pathname)) {
        return {
            path: pathname.replace(/\/$/, ""),
            page: {
                name: "network-device-detail",
                html: "/pages/network/network-device.html",
                js: "/pages/network/network-device.js",
                css: "/pages/network/network-device.css"
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