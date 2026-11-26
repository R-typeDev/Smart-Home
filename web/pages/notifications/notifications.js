
import { t } from "../../assets/js/i18n.js";

let notifications = [];
let languageChangeHandler = null;
let activeNotificationId = null;

const categoryKeys = {
    system: "notifications.categories.system",
    devices: "notifications.categories.devices",
    automations: "notifications.categories.automations",
    custom: "notifications.categories.custom"
};

const severityKeys = {
    info: "notifications.severity.info",
    warning: "notifications.severity.warning",
    critical: "notifications.severity.critical"
};

const demoNotifications = [
    {
        id: 1,
        category: "system",
        severity: "critical",
        translationKey: "notifications.demo.backupFailed",
        sourceKey: "notifications.categories.system",
        date: new Date(Date.now() - 5 * 60000),
        read: false
    },
    {
        id: 2,
        category: "devices",
        severity: "warning",
        translationKey: "notifications.demo.deviceDisconnected",
        deviceNameKey: "devices.add.types.plug",
        date: new Date(Date.now() - 25 * 60000),
        read: false
    },
    {
        id: 3,
        category: "automations",
        severity: "warning",
        translationKey: "notifications.demo.automationFailed",
        sourceKey: "notifications.categories.automations",
        date: new Date(Date.now() - 2 * 3600000),
        read: false
    },
    {
        id: 4,
        category: "system",
        severity: "info",
        translationKey: "notifications.demo.updateAvailable",
        sourceKey: "notifications.categories.system",
        date: new Date(Date.now() - 5 * 3600000),
        read: true
    },
    {
        id: 5,
        category: "devices",
        severity: "info",
        translationKey: "notifications.demo.deviceReconnected",
        deviceNameKey: "devices.add.types.plug",
        date: new Date(Date.now() - 8 * 3600000),
        read: true
    },
    {
        id: 6,
        category: "custom",
        severity: "warning",
        translationKey: "notifications.demo.highTemperature",
        deviceNameKey: "devices.add.types.sensor",
        date: new Date(Date.now() - 24 * 3600000),
        read: true
    }
];

const categoryIcons = {
    system: `
        <svg viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round"
             aria-hidden="true">
            <rect x="3" y="4" width="18" height="16" rx="2"/>
            <path d="M7 8h10M7 12h10M7 16h5"/>
        </svg>
    `,
    devices: `
        <svg viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round"
             aria-hidden="true">
            <rect x="7" y="2" width="10" height="20" rx="2"/>
            <path d="M11 18h2"/>
        </svg>
    `,
    automations: `
        <svg viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round"
             aria-hidden="true">
            <path d="M12 3v3m0 12v3M3 12h3m12 0h3"/>
            <circle cx="12" cy="12" r="5"/>
            <path d="m10 12 1.5 1.5L14 10"/>
        </svg>
    `,
    custom: `
        <svg viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round"
             aria-hidden="true">
            <path d="M12 3v18M3 12h18"/>
            <circle cx="12" cy="12" r="9"/>
        </svg>
    `
};

function getElements() {
    return {
        list: document.getElementById("notifications-list"),
        empty: document.getElementById("notifications-empty"),
        total: document.getElementById("notifications-total"),
        unread: document.getElementById("notifications-unread"),
        important: document.getElementById("notifications-important"),
        search: document.getElementById("notifications-search"),
        category: document.getElementById("notifications-category"),
        status: document.getElementById("notifications-status"),
        markAll: document.getElementById("notifications-mark-all"),
        details: document.getElementById("notification-details"),
        detailsContent: document.getElementById(
            "notification-details-content"
        ),
        detailsClose: document.getElementById(
            "notification-details-close"
        )
    };
}

function interpolate(text, params = {}) {
    return text.replace(/\{(\w+)\}/g, (match, key) => {
        return params[key] ?? match;
    });
}

function getNotificationText(notification, field) {
    const params = {};

    if (notification.deviceNameKey) {
        params.device_name = t(notification.deviceNameKey);
    }

    const translation = t(
        `${notification.translationKey}.${field}`
    );

    return interpolate(translation, params);
}

function getSourceLabel(notification) {
    if (notification.deviceNameKey) {
        return t(notification.deviceNameKey);
    }

    return notification.sourceKey
        ? t(notification.sourceKey)
        : "";
}

function formatDate(date) {
    const locale = document.documentElement.lang || "en";

    return new Intl.DateTimeFormat(locale, {
        day: "numeric",
        month: "short",
        year: "numeric"
    }).format(date);
}

function formatTime(date) {
    const locale = document.documentElement.lang || "en";

    return new Intl.DateTimeFormat(locale, {
        hour: "2-digit",
        minute: "2-digit"
    }).format(date);
}

function getCategoryLabel(category) {
    return t(categoryKeys[category] || category);
}

function getSeverityLabel(severity) {
    return t(severityKeys[severity] || severity);
}

function updateSummary() {
    const elements = getElements();

    if (!elements.total) {
        return;
    }

    elements.total.textContent = notifications.length;

    elements.unread.textContent = notifications.filter(
        notification => !notification.read
    ).length;

    elements.important.textContent = notifications.filter(
        notification =>
            notification.severity === "warning" ||
            notification.severity === "critical"
    ).length;
}

function createNotificationElement(notification) {
    const item = document.createElement("article");

    item.className = [
        "notification-item",
        notification.read ? "" : "notification-item--unread"
    ].filter(Boolean).join(" ");

    item.dataset.notificationId = notification.id;
    item.tabIndex = 0;
    item.setAttribute("role", "button");
    item.setAttribute(
        "aria-label",
        `${getNotificationText(notification, "title")}. ${getCategoryLabel(notification.category)}`
    );

    const indicator = document.createElement("span");
    indicator.className = "notification-item__indicator";
    indicator.setAttribute("aria-hidden", "true");

    const icon = document.createElement("span");
    icon.className = "notification-item__icon";
    icon.innerHTML = categoryIcons[notification.category] || "";

    const body = document.createElement("div");
    body.className = "notification-item__body";

    const top = document.createElement("div");
    top.className = "notification-item__top";

    const title = document.createElement("h2");
    title.className = "notification-item__title";
    title.textContent = getNotificationText(notification, "title");

    const severity = document.createElement("span");
    severity.className = [
        "notification-item__severity",
        `notification-item__severity--${notification.severity}`
    ].join(" ");
    severity.textContent = getSeverityLabel(notification.severity);

    top.append(title, severity);

    const description = document.createElement("p");
    description.className = "notification-item__description";
    description.textContent = getNotificationText(
        notification,
        "description"
    );

    const meta = document.createElement("div");
    meta.className = "notification-item__meta";

    const category = document.createElement("span");
    category.className = "notification-item__category";
    category.textContent = getCategoryLabel(notification.category);

    const source = document.createElement("span");
    source.textContent = getSourceLabel(notification);

    const date = document.createElement("time");
    date.className = "notification-item__time";
    date.dateTime = notification.date.toISOString();
    date.textContent = `${formatDate(notification.date)} · ${formatTime(notification.date)}`;

    meta.append(category, source);

    body.append(top, description, meta);
    item.append(indicator, icon, body, date);

    return item;
}

function getFilteredNotifications() {
    const elements = getElements();

    const search = elements.search?.value
        .trim()
        .toLowerCase() || "";

    const category = elements.category?.value || "all";
    const status = elements.status?.value || "all";

    return notifications
        .filter(notification => {
            const matchesCategory =
                category === "all" ||
                notification.category === category;

            const matchesStatus =
                status === "all" ||
                (status === "unread" && !notification.read) ||
                (status === "read" && notification.read);

            const searchText = [
                getNotificationText(notification, "title"),
                getNotificationText(notification, "description"),
                getNotificationText(notification, "details"),
                getSourceLabel(notification),
                getCategoryLabel(notification.category)
            ].join(" ").toLowerCase();

            const matchesSearch = searchText.includes(search);

            return (
                matchesCategory &&
                matchesStatus &&
                matchesSearch
            );
        })
        .sort((a, b) => b.date - a.date);
}

function renderNotifications() {
    const elements = getElements();

    if (!elements.list || !elements.empty) {
        return;
    }

    const filtered = getFilteredNotifications();

    elements.list.querySelectorAll(".notification-item").forEach(
        item => item.remove()
    );

    filtered.forEach(notification => {
        elements.list.append(
            createNotificationElement(notification)
        );
    });

    elements.empty.hidden = filtered.length > 0;

    updateSummary();
    renderDetails();
}

function renderDetails() {
    const elements = getElements();

    if (!elements.details || !elements.detailsContent) {
        return;
    }

    const notification = notifications.find(
        item => item.id === activeNotificationId
    );

    if (!notification) {
        elements.details.hidden = true;
        return;
    }

    elements.details.hidden = false;
    elements.detailsContent.replaceChildren();

    const title = document.createElement("h3");
    title.textContent = getNotificationText(notification, "title");

    const description = document.createElement("p");
    description.textContent = getNotificationText(
        notification,
        "details"
    );

    const category = document.createElement("p");
    category.textContent =
        `${t("notifications.detailsCategory")}: ${getCategoryLabel(notification.category)}`;

    const severity = document.createElement("p");
    severity.textContent =
        `${t("notifications.detailsSeverity")}: ${getSeverityLabel(notification.severity)}`;

    const source = document.createElement("p");
    source.textContent =
        `${t("notifications.detailsSource")}: ${getSourceLabel(notification)}`;

    const date = document.createElement("p");
    date.textContent =
        `${formatDate(notification.date)} · ${formatTime(notification.date)}`;

    const markRead = document.createElement("button");
    markRead.type = "button";
    markRead.textContent = notification.read
        ? t("notifications.markUnread")
        : t("notifications.markRead");

    markRead.addEventListener("click", () => {
        notification.read = !notification.read;
        renderNotifications();
    });

    elements.detailsContent.append(
        title,
        description,
        category,
        severity,
        source,
        date,
        markRead
    );
}

function selectNotification(id) {
    const notification = notifications.find(
        item => item.id === id
    );

    if (!notification) {
        return;
    }

    activeNotificationId = id;
    notification.read = true;

    renderNotifications();
}

function handleListClick(event) {
    const item = event.target.closest(".notification-item");

    if (!item) {
        return;
    }

    selectNotification(Number(item.dataset.notificationId));
}

function handleListKeydown(event) {
    if (event.key !== "Enter" && event.key !== " ") {
        return;
    }

    const item = event.target.closest(".notification-item");

    if (!item) {
        return;
    }

    event.preventDefault();
    selectNotification(Number(item.dataset.notificationId));
}

function markAllAsRead() {
    notifications.forEach(notification => {
        notification.read = true;
    });

    renderNotifications();
}

function closeDetails() {
    const elements = getElements();

    activeNotificationId = null;

    if (elements.details) {
        elements.details.hidden = true;
    }
}

function initEventListeners() {
    const elements = getElements();

    elements.search?.addEventListener(
        "input",
        renderNotifications
    );

    elements.category?.addEventListener(
        "change",
        renderNotifications
    );

    elements.status?.addEventListener(
        "change",
        renderNotifications
    );

    elements.list?.addEventListener(
        "click",
        handleListClick
    );

    elements.list?.addEventListener(
        "keydown",
        handleListKeydown
    );

    elements.markAll?.addEventListener(
        "click",
        markAllAsRead
    );

    elements.detailsClose?.addEventListener(
        "click",
        closeDetails
    );
}

export function init() {
    destroy();

    notifications = demoNotifications.map(notification => ({
        ...notification,
        date: new Date(notification.date),
        read: notification.read
    }));

    activeNotificationId = null;

    initEventListeners();
    renderNotifications();

    languageChangeHandler = () => {
        renderNotifications();
    };

    window.addEventListener(
        "language:changed",
        languageChangeHandler
    );
}

export function destroy() {
    const elements = getElements();

    elements.search?.removeEventListener(
        "input",
        renderNotifications
    );

    elements.category?.removeEventListener(
        "change",
        renderNotifications
    );

    elements.status?.removeEventListener(
        "change",
        renderNotifications
    );

    elements.list?.removeEventListener(
        "click",
        handleListClick
    );

    elements.list?.removeEventListener(
        "keydown",
        handleListKeydown
    );

    elements.markAll?.removeEventListener(
        "click",
        markAllAsRead
    );

    elements.detailsClose?.removeEventListener(
        "click",
        closeDetails
    );

    if (languageChangeHandler) {
        window.removeEventListener(
            "language:changed",
            languageChangeHandler
        );

        languageChangeHandler = null;
    }

    notifications = [];
    activeNotificationId = null;
}
