
import { t } from "./i18n.js";

let initialized = false;
let notifications = [];
let languageChangeHandler = null;

const elements = {};

function createDemoNotifications() {
    return [
        {
            id: "backup-failed",
            translationKey: "notifications.demo.backupFailed",
            category: "system",
            severity: "critical",
            read: false,
            time: new Date(Date.now() - 5 * 60 * 1000)
        },
        {
            id: "device-disconnected",
            translationKey: "notifications.demo.deviceDisconnected",
            category: "devices",
            severity: "warning",
            read: false,
            deviceName: t("devices.add.types.plug"),
            time: new Date(Date.now() - 25 * 60 * 1000)
        },
        {
            id: "automation-failed",
            translationKey: "notifications.demo.automationFailed",
            category: "automations",
            severity: "warning",
            read: true,
            time: new Date(Date.now() - 60 * 60 * 1000)
        },
        {
            id: "update-available",
            translationKey: "notifications.demo.updateAvailable",
            category: "system",
            severity: "info",
            read: true,
            time: new Date(Date.now() - 3 * 60 * 60 * 1000)
        }
    ];
}

function getText(notification, field) {
    let value = t(`${notification.translationKey}.${field}`);

    if (notification.deviceName) {
        value = value.replaceAll("{device_name}", notification.deviceName);
    }

    return value;
}

function getCategoryLabel(category) {
    return t(`notifications.categories.${category}`);
}

function getSeverityLabel(severity) {
    return t(`notifications.severity.${severity}`);
}

function formatTime(date) {
    const language = document.documentElement.lang || "en";

    return new Intl.DateTimeFormat(language, {
        hour: "2-digit",
        minute: "2-digit"
    }).format(date);
}

function updateCounter() {
    const unreadCount = notifications.filter(item => !item.read).length;

    elements.badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
    elements.badge.hidden = unreadCount === 0;

    elements.unread.textContent = String(unreadCount);
}

function renderNotifications() {
    const recentNotifications = notifications.slice(0, 5);

    if (recentNotifications.length === 0) {
        elements.list.innerHTML = `
            <div class="notification-menu__empty">
                <p>${t("notifications.header.empty")}</p>
            </div>
        `;

        updateCounter();
        return;
    }

    elements.list.innerHTML = recentNotifications.map(notification => `
        <button
            class="notification-menu__item${notification.read ? " is-read" : " is-unread"}"
            type="button"
            data-notification-id="${notification.id}"
        >
            <span class="notification-menu__item-indicator notification-menu__item-indicator--${notification.severity}"></span>

            <span class="notification-menu__item-content">
                <span class="notification-menu__item-title">
                    ${getText(notification, "title")}
                </span>

                <span class="notification-menu__item-description">
                    ${getText(notification, "description")}
                </span>

                <span class="notification-menu__item-meta">
                    ${getCategoryLabel(notification.category)}
                    <span aria-hidden="true">·</span>
                    ${getSeverityLabel(notification.severity)}
                    <span aria-hidden="true">·</span>
                    ${formatTime(notification.time)}
                </span>
            </span>
        </button>
    `).join("");

    updateCounter();
}

function setDropdownOpen(open) {
    elements.dropdown.hidden = !open;
    elements.trigger.setAttribute("aria-expanded", String(open));
}

function handleTriggerClick() {
    setDropdownOpen(elements.dropdown.hidden);
}

function handleOutsideClick(event) {
    if (!elements.menu.contains(event.target)) {
        setDropdownOpen(false);
    }
}

function handleEscape(event) {
    if (event.key === "Escape" && !elements.dropdown.hidden) {
        setDropdownOpen(false);
        elements.trigger.focus();
    }
}

function handleViewAllClick() {
    setDropdownOpen(false);
}

function handleNotificationClick(event) {
    const notificationElement = event.target.closest("[data-notification-id]");

    if (!notificationElement) return;

    const notification = notifications.find(
        item => item.id === notificationElement.dataset.notificationId
    );

    if (!notification) return;

    notification.read = true;
    renderNotifications();
}

function handleLanguageChange() {
    renderNotifications();
}

export function initNotificationsHeader() {
    if (initialized) return;

    elements.menu = document.getElementById("notification-menu");
    elements.trigger = document.getElementById("notification-menu-trigger");
    elements.dropdown = document.getElementById("notification-menu-dropdown");
    elements.badge = document.getElementById("notification-menu-badge");
    elements.unread = document.getElementById("notification-menu-unread");
    elements.list = document.getElementById("notification-menu-list");
    elements.viewAll = elements.menu?.querySelector(".notification-menu__all");

    if (
        !elements.menu ||
        !elements.trigger ||
        !elements.dropdown ||
        !elements.badge ||
        !elements.unread ||
        !elements.list
    ) {
        console.warn("Notifications header elements were not found.");
        return;
    }

    notifications = createDemoNotifications();

    elements.trigger.addEventListener("click", handleTriggerClick);
    elements.list.addEventListener("click", handleNotificationClick);
    elements.viewAll?.addEventListener("click", handleViewAllClick);

    document.addEventListener("click", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);

    languageChangeHandler = handleLanguageChange;
    window.addEventListener("language:changed", languageChangeHandler);

    renderNotifications();

    initialized = true;
}

export function destroyNotificationsHeader() {
    if (!initialized) return;

    elements.trigger.removeEventListener("click", handleTriggerClick);
    elements.list.removeEventListener("click", handleNotificationClick);
    elements.viewAll?.removeEventListener("click", handleViewAllClick);

    document.removeEventListener("click", handleOutsideClick);
    document.removeEventListener("keydown", handleEscape);

    if (languageChangeHandler) {
        window.removeEventListener("language:changed", languageChangeHandler);
    }

    setDropdownOpen(false);

    notifications = [];
    initialized = false;
}
