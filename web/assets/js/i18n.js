
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

// Loads translations belonging to an individual module.
export async function loadModuleTranslations(modulePath) {
    const response = await fetch(
        `${modulePath}/${currentLanguage}.json`
    );

    if (!response.ok) {
        throw new Error(
            `Could not load module translations: ${modulePath}/${currentLanguage}.json`
        );
    }

    return await response.json();
}

export function applyTranslations(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((element) => {
        element.textContent = t(element.dataset.i18n);
    });

    root.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
        element.placeholder = t(element.dataset.i18nPlaceholder);
    });

    // Keep language selectors synchronized.
    document.querySelectorAll("#language-select").forEach((selector) => {
        selector.value = currentLanguage;
    });

    document.documentElement.lang = currentLanguage;

    const path = location.pathname.replace(/\/+$/, "") || "/dashboard";
    let pageKey = path.replace(/^\/+/, "");

    if (pageKey === "devices/add") {
        pageKey = "deviceAdd";
    } else if (/^devices\/item\/[^/]+$/.test(pageKey)) {
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
        `/languages/${selectedLanguage}.json`
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

    document.querySelectorAll("#language-select").forEach((selector) => {
        selector.value = selectedLanguage;
    });

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

    const browserLanguage = navigator.language
        ?.toLowerCase()
        .startsWith("ru")
        ? "ru"
        : "en";

    const initialLanguage = savedLanguage
        ? (["en", "ru"].includes(savedLanguage) ? savedLanguage : "en")
        : browserLanguage;

    // Delegated listener works with dynamically loaded pages.
    document.addEventListener("change", async (event) => {
        if (!event.target.matches("#language-select")) {
            return;
        }

        const selector = event.target;

        try {
            await setLanguage(selector.value);
        } catch (error) {
            console.error("Language change failed:", error);
            selector.value = currentLanguage;
        }
    });

    try {
        await setLanguage(initialLanguage);
    } catch (error) {
        console.error(
            "Localization initialization failed:",
            error
        );
    }
}
