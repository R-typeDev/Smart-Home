
let translations = {};
let currentLanguage = "en";

export function getLanguage() {
    return currentLanguage;
}

export function t(key) {
    return key.split(".").reduce(
        (value, part) => value?.[part],
        translations
    ) ?? key;
}

export function applyTranslations(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((element) => {
        element.textContent = t(element.dataset.i18n);
    });

    root.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
        element.placeholder = t(element.dataset.i18nPlaceholder);
    });

    document.documentElement.lang = currentLanguage;

    const path = location.pathname.replace(/\/+$/, "") || "/dashboard";
    let pageKey = path.replace(/^\/+/, "");

    if (/^devices\/item\/[^/]+$/.test(pageKey)) {
        pageKey = "devices";
    } else if (/^network\/item\/[^/]+$/.test(pageKey)) {
        pageKey = "network";
    } else {
        pageKey = pageKey.split("/")[0] || "dashboard";
    }

    let metadata = t(`pageMeta.${pageKey}`);

    if (!metadata || typeof metadata !== "object") {
        metadata = t("pageMeta.dashboard");
    }

    const appName = t("app.name");
    const title = metadata.title || "Dashboard";

    document.title = `${title} | ${appName}`;

    let description = document.querySelector(
        'meta[name="description"]'
    );

    if (!description) {
        description = document.createElement("meta");
        description.name = "description";
        document.head.append(description);
    }

    description.content = metadata.description || "";
}

export async function setLanguage(language) {
    const selectedLanguage = ["en", "ru"].includes(language)
        ? language
        : "en";

    const response = await fetch(
        `/locales/${selectedLanguage}.json`
    );

    if (!response.ok) {
        throw new Error(
            `Could not load language: ${selectedLanguage}`
        );
    }

    translations = await response.json();
    currentLanguage = selectedLanguage;

    localStorage.setItem(
        "smart-home-language",
        selectedLanguage
    );

    const selector = document.querySelector("#language-select");

    if (selector) {
        selector.value = selectedLanguage;
    }

    applyTranslations();

    window.dispatchEvent(
        new CustomEvent("language:changed", {
            detail: { language: selectedLanguage }
        })
    );
}

export async function initI18n() {
    const savedLanguage = localStorage.getItem(
        "smart-home-language"
    );

    const initialLanguage = savedLanguage === "ru" ? "ru" : "en";
    const selector = document.querySelector("#language-select");

    if (selector) {
        selector.value = initialLanguage;

        selector.addEventListener("change", async () => {
            try {
                await setLanguage(selector.value);
            } catch (error) {
                console.error("Language change failed:", error);
                selector.value = currentLanguage;
            }
        });
    }

    try {
        await setLanguage(initialLanguage);
    } catch (error) {
        console.error(
            "Localization initialization failed:",
            error
        );
    }
}
