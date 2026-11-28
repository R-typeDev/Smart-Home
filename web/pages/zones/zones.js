
import { t } from "../../assets/js/i18n.js";

export function init() {
    const toggleButton = document.querySelector("#zones-add-toggle");
    const formCard = document.querySelector("#zones-form-card");
    const form = document.querySelector("#zones-form");
    const cancelButton = document.querySelector("#zones-cancel");
    const nameInput = document.querySelector("#zone-name");
    const message = document.querySelector("#zones-form-message");

    if (!toggleButton || !formCard || !form || !cancelButton || !message) {
        return;
    }

    function closeForm() {
        formCard.hidden = true;
        toggleButton.setAttribute("aria-expanded", "false");
        message.hidden = true;
        form.reset();
    }

    toggleButton.addEventListener("click", () => {
        const shouldOpen = formCard.hidden;

        formCard.hidden = !shouldOpen;
        toggleButton.setAttribute("aria-expanded", String(shouldOpen));

        if (shouldOpen && nameInput) {
            nameInput.focus();
        }
    });

    cancelButton.addEventListener("click", closeForm);

    form.addEventListener("submit", (event) => {
        event.preventDefault();

        message.textContent = t("zones.previewMessage");
        message.hidden = false;
    });
}
