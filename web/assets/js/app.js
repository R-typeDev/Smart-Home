
import { initI18n } from "./i18n.js";
import { startNavigation } from "./navigation.js";
import { initNotificationsHeader } from "./notifications-header.js";

await initI18n();

initNotificationsHeader();
startNavigation();
