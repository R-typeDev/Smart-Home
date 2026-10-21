import { applyTranslations } from "./i18n.js";

export async function loadPage(page) {
    const content = document.querySelector("#app-content");

    try {
        const response = await fetch(page.html);

        if (!response.ok) {
            throw new Error(`Page request failed: ${response.status}`);
        }

        content.innerHTML = await response.text();

        let stylesheet = document.querySelector(
            `link[data-page-css="${page.name}"]`
        );

        if (!stylesheet) {
            stylesheet = document.createElement("link");
            stylesheet.rel = "stylesheet";
            stylesheet.dataset.pageCss = page.name;
            document.head.append(stylesheet);
        }

        stylesheet.href = page.css;

        const pageModule = await import(page.js);

        if (typeof pageModule.init === "function") {
            await pageModule.init();
        }

        applyTranslations(content);
        content.focus();
    } catch (error) {
        console.error("Page loading failed:", error);

        content.textContent =
            "The page could not be loaded. Check the server and try again.";
    }
}
