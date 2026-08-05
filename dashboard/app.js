const alertsTableBody = document.querySelector("#alerts-table-body");
const eventsTableBody = document.querySelector("#events-table-body");
const deviceList = document.querySelector("#device-list");
const refreshButton = document.querySelector("#refresh-button");
const sidebarStatus = document.querySelector(".sidebar-status");
const statusDot = document.querySelector(".status-dot");


function escapeHtml(value) {
    const element = document.createElement("div");
    element.textContent = value ?? "";
    return element.innerHTML;
}


function formatDate(value) {
    if (!value) {
        return "Unknown";
    }

    const includesTimezone =
        value.endsWith("Z") ||
        /[+-]\d{2}:\d{2}$/.test(value);

    const normalizedValue = includesTimezone
        ? value
        : `${value}Z`;

    const date = new Date(normalizedValue);

    if (Number.isNaN(date.getTime())) {
        return "Invalid date";
    }

    return date.toLocaleString(
        undefined,
        {
            dateStyle: "short",
            timeStyle: "medium",
        }
    );
}


function shortenMessage(message, maximumLength = 100) {
    if (!message) {
        return "No message available";
    }

    if (message.length <= maximumLength) {
        return message;
    }

    return `${message.slice(0, maximumLength)}...`;
}


async function fetchJson(url) {
    const response = await fetch(url);

    if (!response.ok) {
        throw new Error(
            `Request to ${url} failed with status ${response.status}`
        );
    }

    return response.json();
}


function renderAlerts(alerts) {
    if (alerts.length === 0) {
        alertsTableBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    No alerts have been generated.
                </td>
            </tr>
        `;
        return;
    }

    alertsTableBody.innerHTML = alerts.map((alert) => `
        <tr>
            <td>
                <span class="badge severity-${escapeHtml(alert.severity)}">
                    ${escapeHtml(alert.severity)}
                </span>
            </td>

            <td>
                <strong>${escapeHtml(alert.title)}</strong>
            </td>

            <td>${escapeHtml(alert.rule_id)}</td>

            <td>
    <select
        class="status-select status-${escapeHtml(alert.status)}"
        data-alert-id="${alert.id}"
    >
        <option
            value="open"
            ${alert.status === "open" ? "selected" : ""}
        >
            Open
        </option>

        <option
            value="investigating"
            ${alert.status === "investigating" ? "selected" : ""}
        >
            Investigating
        </option>

        <option
            value="resolved"
            ${alert.status === "resolved" ? "selected" : ""}
        >
            Resolved
        </option>

        <option
            value="dismissed"
            ${alert.status === "dismissed" ? "selected" : ""}
        >
            Dismissed
        </option>
    </select>
</td>

            <td>${escapeHtml(formatDate(alert.created_at))}</td>
        </tr>
    `).join("");
}


function renderEvents(events) {
    if (events.length === 0) {
        eventsTableBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">
                    No security events have been received.
                </td>
            </tr>
        `;
        return;
    }

    eventsTableBody.innerHTML = events.slice(0, 25).map((event) => `
        <tr>
            <td>
                <strong>${escapeHtml(event.windows_event_id)}</strong>
            </td>

            <td>${escapeHtml(event.provider)}</td>

            <td>${escapeHtml(event.level)}</td>

            <td
                class="event-message"
                title="${escapeHtml(event.message)}"
            >
                ${escapeHtml(shortenMessage(event.message))}
            </td>

            <td>${escapeHtml(formatDate(event.occurred_at))}</td>
        </tr>
    `).join("");
}


function renderDevices(devices) {
    if (devices.length === 0) {
        deviceList.innerHTML = `
            <p class="empty-state">
                No monitoring agents are registered.
            </p>
        `;
        return;
    }

    deviceList.innerHTML = devices.map((device) => `
        <article class="device-card">
            <div class="device-card-header">
                <h4>${escapeHtml(device.hostname)}</h4>

                <span class="device-status">
                    ${escapeHtml(device.status)}
                </span>
            </div>

            <p>${escapeHtml(device.operating_system)}</p>
            <p>IP address: ${escapeHtml(device.ip_address)}</p>
            <p>Agent version: ${escapeHtml(device.agent_version)}</p>
            <p>Last seen: ${escapeHtml(formatDate(device.last_seen))}</p>
        </article>
    `).join("");
}


function updateMetrics(alerts, events, devices) {
    const activeAlerts = alerts.filter(
        (alert) =>
            alert.status === "open" ||
            alert.status === "investigating"
    );

    const criticalAlerts = activeAlerts.filter(
        (alert) => alert.severity === "critical"
    );

    document.querySelector("#open-alert-count").textContent =
        activeAlerts.length;

    document.querySelector("#critical-alert-count").textContent =
        criticalAlerts.length;

    document.querySelector("#event-count").textContent =
        events.length;

    document.querySelector("#device-count").textContent =
        devices.length;
}


function setConnectionStatus(connected) {
    if (connected) {
        sidebarStatus.lastChild.textContent = " API connected";
        statusDot.style.background = "var(--green)";
        statusDot.style.boxShadow = "0 0 12px var(--green)";
        return;
    }

    sidebarStatus.lastChild.textContent = " API unavailable";
    statusDot.style.background = "var(--red)";
    statusDot.style.boxShadow = "0 0 12px var(--red)";
}


async function loadDashboard() {
    refreshButton.disabled = true;
    refreshButton.textContent = "Refreshing...";

    try {
        const [alerts, events, devices] = await Promise.all([
            fetchJson("/alerts/?limit=100"),
            fetchJson("/events/?limit=100"),
            fetchJson("/devices/"),
        ]);

        renderAlerts(alerts);
        renderEvents(events);
        renderDevices(devices);
        updateMetrics(alerts, events, devices);
        setConnectionStatus(true);

        document.querySelector("#last-updated").textContent =
            `Updated ${new Date().toLocaleTimeString()}`;
    }
    catch (error) {
        console.error(error);

        setConnectionStatus(false);

        alertsTableBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state error-message">
                    Unable to load Watchtower data.
                </td>
            </tr>
        `;
    }
    finally {
        refreshButton.disabled = false;
        refreshButton.textContent = "Refresh data";
    }
}

alertsTableBody.addEventListener("change", async (browserEvent) => {
    const statusSelect = browserEvent.target.closest(".status-select");

    if (!statusSelect) {
        return;
    }

    const alertId = statusSelect.dataset.alertId;
    const newStatus = statusSelect.value;

    statusSelect.disabled = true;

    try {
        const response = await fetch(
            `/alerts/${alertId}/status`,
            {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    status: newStatus,
                }),
            }
        );

        if (!response.ok) {
            throw new Error(
                `Alert update failed with status ${response.status}`
            );
        }

        await loadDashboard();
    }
    catch (error) {
        console.error(error);
        window.alert("Watchtower could not update this alert.");
        await loadDashboard();
    }
    finally {
        statusSelect.disabled = false;
    }
});

refreshButton.addEventListener("click", loadDashboard);

loadDashboard();

setInterval(loadDashboard, 30000);

async function loadAuditLogs() {
    const auditLogs = await fetchJson("/audit/?limit=100");
    const tableBody = document.getElementById("audit-table-body");

    tableBody.replaceChildren();

    if (auditLogs.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 6;
        cell.textContent = "No audit activity has been recorded.";

        row.appendChild(cell);
        tableBody.appendChild(row);
        return;
    }

    auditLogs.forEach((entry) => {
        const row = document.createElement("tr");

        const values = [
            formatDate(entry.created_at),
            entry.user_id ? `User #${entry.user_id}` : "System",
            entry.action,
            entry.resource_id
                ? `${entry.resource_type} #${entry.resource_id}`
                : entry.resource_type,
            entry.details
                ? JSON.stringify(entry.details)
                : "—",
            entry.source_ip || "—",
        ];

        values.forEach((value) => {
            const cell = document.createElement("td");
            cell.textContent = value;
            row.appendChild(cell);
        });

        tableBody.appendChild(row);
    });
}

async function loadCurrentUser() {
    const response = await fetch("/auth/me");

    if (response.status === 401) {
        window.location.replace("/login");
        return;
    }

    if (!response.ok) {
        throw new Error("Unable to load the signed-in user.");
    }

    const user = await response.json();

    document.getElementById("analyst-name").textContent = user.username;
    document.getElementById("analyst-role").textContent =
        user.role.charAt(0).toUpperCase() + user.role.slice(1);
    if (user.role === "admin") {
    document
        .getElementById("audit-navigation")
        .removeAttribute("hidden");

    document
        .getElementById("audit")
        .removeAttribute("hidden");

    await loadAuditLogs();
}
}

async function logout() {
    const logoutButton = document.getElementById("logout-button");
    logoutButton.disabled = true;
    logoutButton.textContent = "Signing out...";

    try {
        const response = await fetch("/auth/logout", {
            method: "POST",
        });

        if (!response.ok) {
            throw new Error("Unable to sign out.");
        }

        window.location.replace("/login");
    } catch (error) {
        logoutButton.disabled = false;
        logoutButton.textContent = "Sign out";
        alert(error.message);
    }
}

document
    .getElementById("logout-button")
    .addEventListener("click", logout);

loadCurrentUser().catch((error) => {
    console.error(error);
    window.location.replace("/login");
});