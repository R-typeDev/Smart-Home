
import { applyTranslations } from "./i18n.js";

let activePageModule = null;

export async function loadPage(page) {
    const content = document.querySelector("#app-content");

    try {
        // Stop the previous page before loading another one.
        if (activePageModule && typeof activePageModule.destroy === "function") {
            await activePageModule.destroy();
        }

        activePageModule = null;

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

        activePageModule = pageModule;

        if (typeof pageModule.init === "function") {
            await pageModule.init();
        }

        applyTranslations(content);
        content.focus();
    } catch (error) {
        console.error("Page loading failed:", error);

        if (activePageModule && typeof activePageModule.destroy === "function") {
            try {
                await activePageModule.destroy();
            } catch (destroyError) {
                console.error("Page cleanup failed:", destroyError);
            }
        }

        activePageModule = null;

        content.textContent =
            "The page could not be loaded. Check the server and try again.";
    }
}
