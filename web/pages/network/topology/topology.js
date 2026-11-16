
const API_URL = "/api/network/topology";
const REFRESH_INTERVAL = 30000;

const SVG_NS = "http://www.w3.org/2000/svg";

const NODE_WIDTH = 170;
const NODE_HEIGHT = 72;
const NODE_GAP = 25;
const ROW_GAP = 45;
const SIDE_PADDING = 40;

let currentTopology = null;
let selectedNodeId = null;
let activeListType = null;
let refreshTimer = null;
let isLoading = false;

let layoutState = {
    width: 900,
    height: 470,
};

let viewState = {
    x: 0,
    y: 0,
    width: 900,
    height: 470,
};

let dragState = null;


function getElement(id) {
    return document.getElementById(id);
}


function setText(id, value) {
    const element = getElement(id);

    if (element) {
        element.textContent = String(value);
    }
}


function createSvgElement(tag, attributes = {}) {
    const element = document.createElementNS(SVG_NS, tag);

    for (const [name, value] of Object.entries(attributes)) {
        element.setAttribute(name, String(value));
    }

    return element;
}


function getAllNodes(topology) {
    return [
        ...topology.interfaces.map(node => ({
            ...node,
            node_type: "interface",
        })),
        ...topology.subnets.map(node => ({
            ...node,
            node_type: "subnet",
        })),
        ...topology.gateways.map(node => ({
            ...node,
            node_type: "gateway",
        })),
        ...topology.devices.map(node => ({
            ...node,
            node_type: "device",
        })),
    ];
}


function getNodeTitle(node) {
    switch (node.node_type) {
        case "interface":
            return node.name || node.id;

        case "subnet":
            return node.network || node.id;

        case "gateway":
            return node.ip_address || node.id;

        case "device":
            return node.hostname || node.ip_address || node.id;

        default:
            return node.id;
    }
}


function getNodeSubtitle(node) {
    switch (node.node_type) {
        case "interface":
            return (node.ip_addresses || []).join(", ") || "No IP address";

        case "subnet":
            return node.interface_name || "";

        case "gateway":
            return node.is_default ? "Default gateway" : "Gateway";

        case "device":
            return node.ip_address || "";

        default:
            return "";
    }
}


function createNodeLayout(topology) {
    const nodes = getAllNodes(topology);

    const interfaceNodes = nodes.filter(
        node => node.node_type === "interface"
    );

    const subnetNodes = nodes.filter(
        node => node.node_type === "subnet"
    );

    const bottomNodes = nodes.filter(
        node =>
            node.node_type === "gateway" ||
            node.node_type === "device"
    );

    const scroll = getElement("topology-scroll");

    const width = Math.max(
        700,
        (scroll?.clientWidth || 900) - 2
    );

    const columns = Math.max(
        1,
        Math.floor(
            (width - SIDE_PADDING * 2 + NODE_GAP) /
            (NODE_WIDTH + NODE_GAP)
        )
    );

    const positions = new Map();

    function placeRows(nodesToPlace, startY) {
        if (!nodesToPlace.length) {
            return startY;
        }

        const rowCount = Math.ceil(nodesToPlace.length / columns);

        nodesToPlace.forEach((node, index) => {
            const row = Math.floor(index / columns);
            const column = index % columns;

            const nodesInRow = Math.min(
                columns,
                nodesToPlace.length - row * columns
            );

            const rowWidth =
                nodesInRow * NODE_WIDTH +
                (nodesInRow - 1) * NODE_GAP;

            const startX = (width - rowWidth) / 2;

            const x = startX + column * (NODE_WIDTH + NODE_GAP);
            const y = startY + row * (NODE_HEIGHT + ROW_GAP);

            positions.set(node.id, {
                x,
                y,
                centerX: x + NODE_WIDTH / 2,
                centerY: y + NODE_HEIGHT / 2,
                top: y,
                bottom: y + NODE_HEIGHT,
            });
        });

        return startY + rowCount * (NODE_HEIGHT + ROW_GAP);
    }

    let nextY = placeRows(interfaceNodes, 35);
    nextY = placeRows(subnetNodes, nextY + 25);
    nextY = placeRows(bottomNodes, nextY + 25);

    const height = Math.max(470, nextY + 30);

    return {
        nodes,
        positions,
        width,
        height,
    };
}


function renderLinks(svg, topology, positions) {
    for (const link of topology.links || []) {
        const source = positions.get(link.source_id);
        const target = positions.get(link.target_id);

        if (!source || !target) {
            continue;
        }

        const sourceIsAbove = source.centerY < target.centerY;

        const startX = source.centerX;
        const endX = target.centerX;

        const startY = sourceIsAbove
            ? source.bottom
            : source.top;

        const endY = sourceIsAbove
            ? target.top
            : target.bottom;

        const direction = sourceIsAbove ? 1 : -1;

        const curveOffset = Math.max(
            35,
            Math.abs(endY - startY) * 0.4
        );

        const path = createSvgElement("path", {
            class: "topology-link",
            d: `
                M ${startX} ${startY}
                C ${startX} ${startY + curveOffset * direction},
                  ${endX} ${endY - curveOffset * direction},
                  ${endX} ${endY}
            `,
        });

        svg.appendChild(path);
    }
}


function renderNode(svg, node, position) {
    const group = createSvgElement("g", {
        class: `topology-node topology-node--${node.node_type}`,
        tabindex: "0",
        role: "button",
        "aria-label": `${node.node_type}: ${getNodeTitle(node)}`,
        "data-node-id": node.id,
    });

    if (node.id === selectedNodeId) {
        group.classList.add("is-selected");
    }

    const rectangle = createSvgElement("rect", {
        x: position.x,
        y: position.y,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        rx: 9,
        ry: 9,
    });

    const title = createSvgElement("text", {
        class: "topology-node__title",
        x: position.centerX,
        y: position.y + 31,
    });

    title.textContent = getNodeTitle(node);

    const subtitle = createSvgElement("text", {
        class: "topology-node__subtitle",
        x: position.centerX,
        y: position.y + 52,
    });

    subtitle.textContent = getNodeSubtitle(node);

    const tooltip = createSvgElement("title");
    tooltip.textContent = [
        getNodeTitle(node),
        getNodeSubtitle(node),
    ].filter(Boolean).join("\n");

    group.append(rectangle, title, subtitle, tooltip);

    group.addEventListener("click", () => {
        selectNode(node.id);
    });

    group.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            selectNode(node.id);
        }
    });

    svg.appendChild(group);
}


function addDetailRow(container, label, value) {
    if (value === undefined || value === null || value === "") {
        return;
    }

    const row = document.createElement("div");
    row.className = "topology-detail-row";

    const name = document.createElement("span");
    name.className = "topology-detail-label";
    name.textContent = label;

    const content = document.createElement("span");
    content.className = "topology-detail-value";

    content.textContent = Array.isArray(value)
        ? value.join(", ")
        : String(value);

    row.append(name, content);
    container.appendChild(row);
}


function renderDetails(node) {
    const container = getElement("topology-details-content");

    if (!container) {
        return;
    }

    container.replaceChildren();

    if (!node) {
        const message = document.createElement("p");
        message.className = "page-description";
        message.textContent = "Select a node on the map to view its properties.";
        container.appendChild(message);
        return;
    }

    const heading = document.createElement("h3");
    heading.textContent = getNodeTitle(node);

    const type = document.createElement("p");
    type.className = "topology-detail-type";
    type.textContent = node.node_type;

    container.append(heading, type);

    switch (node.node_type) {
        case "interface":
            addDetailRow(container, "Name", node.name);
            addDetailRow(container, "Type", node.interface_type);
            addDetailRow(container, "Index", node.interface_index);
            addDetailRow(container, "IP addresses", node.ip_addresses);
            addDetailRow(container, "MAC address", node.mac_address);
            addDetailRow(container, "Status", node.is_up ? "Up" : "Down");
            addDetailRow(container, "Virtual", node.is_virtual ? "Yes" : "No");
            break;

        case "subnet":
            addDetailRow(container, "Network", node.network);
            addDetailRow(container, "Prefix length", node.prefix_length);
            addDetailRow(container, "Interface", node.interface_name);
            addDetailRow(container, "Interface ID", node.interface_id);
            break;

        case "gateway":
            addDetailRow(container, "IP address", node.ip_address);
            addDetailRow(container, "Interface", node.interface_name);
            addDetailRow(container, "Interface index", node.interface_index);
            addDetailRow(container, "Default gateway", node.is_default ? "Yes" : "No");
            break;

        case "device":
            addDetailRow(container, "IP address", node.ip_address);
            addDetailRow(container, "Hostname", node.hostname);
            addDetailRow(container, "MAC address", node.mac_address);
            addDetailRow(container, "Availability", node.is_available ? "Available" : "Unavailable");
            addDetailRow(container, "Local device", node.is_local ? "Yes" : "No");
            addDetailRow(container, "Connection", node.connection_type);
            addDetailRow(container, "Discovery methods", node.discovery_methods);
            break;
    }
}


function selectNode(nodeId) {
    if (!currentTopology) {
        return;
    }

    selectedNodeId = nodeId;

    const node = getAllNodes(currentTopology).find(
        item => item.id === nodeId
    );

    renderDetails(node || null);
    renderTopology(currentTopology);
    renderListItems();
}


function renderStatistics(topology) {
    setText("stat-interfaces", topology.interfaces.length);
    setText("stat-subnets", topology.subnets.length);
    setText("stat-gateways", topology.gateways.length);
    setText("stat-devices", topology.devices.length);

    setText(
        "topology-updated",
        topology.generated_at
            ? new Date(topology.generated_at).toLocaleString()
            : new Date().toLocaleString()
    );
}


function getTypeLabel(type) {
    const labels = {
        interface: "Interfaces",
        subnet: "Subnets",
        gateway: "Gateways",
        device: "Devices",
    };

    return labels[type] || "Items";
}


function showNodeList(type) {
    if (!currentTopology) {
        return;
    }

    const panel = getElement("topology-list");
    const title = getElement("topology-list-title");

    if (!panel || !title) {
        return;
    }

    if (activeListType === type && !panel.hidden) {
        closeNodeList();
        return;
    }

    activeListType = type;
    title.textContent = getTypeLabel(type);
    panel.hidden = false;

    document.querySelectorAll(".topology-stat").forEach(card => {
        card.classList.toggle(
            "is-active",
            card.dataset.nodeType === type
        );
    });

    renderListItems();
}


function closeNodeList() {
    activeListType = null;

    const panel = getElement("topology-list");

    if (panel) {
        panel.hidden = true;
    }

    document.querySelectorAll(".topology-stat").forEach(card => {
        card.classList.remove("is-active");
    });
}


function renderListItems() {
    const container = getElement("topology-list-items");

    if (!container || !currentTopology || !activeListType) {
        return;
    }

    container.replaceChildren();

    const nodes = getAllNodes(currentTopology).filter(
        node => node.node_type === activeListType
    );

    if (!nodes.length) {
        const message = document.createElement("p");
        message.textContent = "No items found.";
        container.appendChild(message);
        return;
    }

    for (const node of nodes) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "topology-list__item";

        if (node.id === selectedNodeId) {
            button.classList.add("is-selected");
        }

        const name = document.createElement("strong");
        name.textContent = getNodeTitle(node);

        const subtitle = document.createElement("span");
        subtitle.textContent = getNodeSubtitle(node) || node.node_type;

        button.append(name, subtitle);

        button.addEventListener("click", () => {
            selectNode(node.id);
        });

        container.appendChild(button);
    }
}


function applySearch() {
    const input = getElement("topology-search");
    const query = input?.value.trim().toLowerCase() || "";

    const nodes = document.querySelectorAll(".topology-node");

    nodes.forEach(element => {
        element.classList.remove("is-dimmed", "is-match");

        if (!query) {
            return;
        }

        const nodeId = element.dataset.nodeId;

        const node = getAllNodes(currentTopology).find(
            item => item.id === nodeId
        );

        if (!node) {
            return;
        }

        const searchableText = [
            getNodeTitle(node),
            getNodeSubtitle(node),
            node.ip_address,
            node.mac_address,
            node.name,
            node.hostname,
            node.network,
            node.id,
        ].filter(Boolean).join(" ").toLowerCase();

        if (searchableText.includes(query)) {
            element.classList.add("is-match");
        } else {
            element.classList.add("is-dimmed");
        }
    });
}


function updateViewBox() {
    const svg = getElement("topology-svg");

    if (!svg) {
        return;
    }

    svg.setAttribute(
        "viewBox",
        `${viewState.x} ${viewState.y} ${viewState.width} ${viewState.height}`
    );
}


function fitTopology() {
    viewState = {
        x: 0,
        y: 0,
        width: layoutState.width,
        height: layoutState.height,
    };

    updateViewBox();
}


function zoomTopology(factor) {
    const oldWidth = viewState.width;
    const oldHeight = viewState.height;

    const newWidth = Math.max(
        layoutState.width * 0.25,
        Math.min(layoutState.width * 3, oldWidth * factor)
    );

    const newHeight = newWidth * layoutState.height / layoutState.width;

    const centerX = viewState.x + oldWidth / 2;
    const centerY = viewState.y + oldHeight / 2;

    viewState.width = newWidth;
    viewState.height = newHeight;
    viewState.x = centerX - newWidth / 2;
    viewState.y = centerY - newHeight / 2;

    updateViewBox();
}


function setupMapInteraction() {
    const scroll = getElement("topology-scroll");
    const svg = getElement("topology-svg");

    if (!scroll || !svg) {
        return;
    }

    scroll.addEventListener("wheel", event => {
        if (!currentTopology) {
            return;
        }

        event.preventDefault();

        zoomTopology(event.deltaY < 0 ? 0.9 : 1.1);
    }, { passive: false });

    svg.addEventListener("pointerdown", event => {
        if (event.target.closest(".topology-node")) {
            return;
        }

        if (event.button !== 0) {
            return;
        }

        dragState = {
            pointerId: event.pointerId,
            startX: event.clientX,
            startY: event.clientY,
            viewX: viewState.x,
            viewY: viewState.y,
        };

        svg.setPointerCapture(event.pointerId);
        svg.classList.add("is-dragging");
    });

    svg.addEventListener("pointermove", event => {
        if (!dragState || dragState.pointerId !== event.pointerId) {
            return;
        }

        const bounds = svg.getBoundingClientRect();

        const scaleX = viewState.width / bounds.width;
        const scaleY = viewState.height / bounds.height;

        viewState.x = dragState.viewX -
            (event.clientX - dragState.startX) * scaleX;

        viewState.y = dragState.viewY -
            (event.clientY - dragState.startY) * scaleY;

        updateViewBox();
    });

    function stopDragging(event) {
        if (!dragState || dragState.pointerId !== event.pointerId) {
            return;
        }

        dragState = null;
        svg.classList.remove("is-dragging");
    }

    svg.addEventListener("pointerup", stopDragging);
    svg.addEventListener("pointercancel", stopDragging);
    svg.addEventListener("lostpointercapture", () => {
        dragState = null;
        svg.classList.remove("is-dragging");
    });
}


function renderTopology(topology) {
    const svg = getElement("topology-svg");
    const message = getElement("topology-message");

    if (!svg) {
        return;
    }

    const layout = createNodeLayout(topology);

    layoutState = {
        width: layout.width,
        height: layout.height,
    };

    svg.replaceChildren();

    const currentWidth = viewState.width;
    const isInitialView =
        !Number.isFinite(currentWidth) ||
        currentWidth <= 0 ||
        currentWidth === 900;

    if (isInitialView) {
        fitTopology();
    } else {
        viewState.height =
            viewState.width * layout.height / layout.width;

        updateViewBox();
    }

    svg.setAttribute("width", "100%");
    svg.setAttribute("height", `${layout.height}px`);
    svg.setAttribute("preserveAspectRatio", "xMidYMin meet");

    renderLinks(svg, topology, layout.positions);

    for (const node of layout.nodes) {
        const position = layout.positions.get(node.id);

        if (position) {
            renderNode(svg, node, position);
        }
    }

    svg.removeAttribute("hidden");

    if (message) {
        message.hidden = true;
    }

    const selectedNode = layout.nodes.find(
        node => node.id === selectedNodeId
    );

    if (selectedNode) {
        renderDetails(selectedNode);
    } else if (!selectedNodeId) {
        renderDetails(null);
    } else {
        selectedNodeId = null;
        renderDetails(null);
    }

    applySearch();
}


async function loadTopology() {
    if (isLoading) {
        return;
    }

    isLoading = true;

    const status = getElement("topology-status");

    if (status) {
        status.textContent = "Updating...";
        status.classList.remove("is-error");
    }

    try {
        const response = await fetch(API_URL, {
            method: "GET",
            cache: "no-store",
            headers: {
                Accept: "application/json",
            },
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const topology = await response.json();

        for (const key of [
            "interfaces",
            "subnets",
            "gateways",
            "devices",
            "links",
        ]) {
            if (!Array.isArray(topology[key])) {
                topology[key] = [];
            }
        }

        currentTopology = topology;

        renderStatistics(topology);
        renderTopology(topology);

        if (activeListType) {
            renderListItems();
        }

        if (status) {
            status.textContent = "Connected";
        }
    } catch (error) {
        console.error("Topology loading failed:", error);

        if (status) {
            status.textContent = "Connection error";
            status.classList.add("is-error");
        }

        const message = getElement("topology-message");

        if (message) {
            message.hidden = false;
            message.textContent = "Could not load network topology.";
        }
    } finally {
        isLoading = false;
    }
}


function handleResize() {
    if (!currentTopology) {
        return;
    }

    renderTopology(currentTopology);
}


function init() {
    const refreshButton = getElement("topology-refresh");
    const zoomInButton = getElement("topology-zoom-in");
    const zoomOutButton = getElement("topology-zoom-out");
    const fitButton = getElement("topology-fit");
    const searchInput = getElement("topology-search");
    const closeListButton = getElement("topology-list-close");

    refreshButton?.addEventListener("click", loadTopology);
    zoomInButton?.addEventListener("click", () => zoomTopology(0.8));
    zoomOutButton?.addEventListener("click", () => zoomTopology(1.25));
    fitButton?.addEventListener("click", fitTopology);
    searchInput?.addEventListener("input", applySearch);
    closeListButton?.addEventListener("click", closeNodeList);

    document.querySelectorAll(".topology-stat").forEach(card => {
        card.addEventListener("click", () => {
            showNodeList(card.dataset.nodeType);
        });
    });

    setupMapInteraction();

    window.addEventListener("resize", handleResize);

    if (refreshTimer) {
        clearInterval(refreshTimer);
    }

    loadTopology();

    refreshTimer = setInterval(
        loadTopology,
        REFRESH_INTERVAL
    );
}


export function destroy() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }

    window.removeEventListener("resize", handleResize);

    isLoading = false;
    dragState = null;
}


export { init };
