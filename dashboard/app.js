const alertsTableBody = document.querySelector("#alerts-table-body");
const eventsTableBody = document.querySelector("#events-table-body");
const deviceList = document.querySelector("#device-list");
const refreshButton = document.querySelector("#refresh-button");
const sidebarStatus = document.querySelector(".sidebar-status");
const statusDot = document.querySelector(".status-dot");

const deviceDetailsSection = document.querySelector(
    "#device-details"
);
const deviceDetailsTitle = document.querySelector(
    "#device-details-title"
);
const deviceDetailsSummary = document.querySelector(
    "#device-details-summary"
);
const deviceAlertsTableBody = document.querySelector(
    "#device-alerts-table-body"
);
const deviceEventsTableBody = document.querySelector(
    "#device-events-table-body"
);
const closeDeviceDetailsButton = document.querySelector(
    "#close-device-details"
);


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


let redirectingToLogin = false;

async function fetchJson(url) {
    const response = await fetch(url, {
        credentials: "same-origin",
    });

    if (response.status === 401) {
        if (
            window.location.pathname !== "/login" &&
            !redirectingToLogin
        ) {
            redirectingToLogin = true;
            window.location.replace("/login");
        }

        throw new Error("Authentication required.");
    }

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
                <td colspan="6" class="empty-state">
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
            <td>
    <button
        class="investigate-button"
        type="button"
        data-alert-id="${alert.id}"
    >
        Investigate
    </button>
</td>
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

function buildSparkline(values, color) {
    if (!Array.isArray(values) || values.length === 0) {
        return "";
    }

    const safeValues = values.map((value) =>
        Math.max(0, Math.min(100, Number(value) || 0))
    );

    const width = 100;
    const height = 30;
    const divisor = Math.max(1, safeValues.length - 1);

    const points = safeValues
        .map((value, index) => {
            const x = (index / divisor) * width;
            const y = height - (value / 100) * height;

            return `${x.toFixed(2)},${y.toFixed(2)}`;
        })
        .join(" ");

    return `
        <svg
            class="telemetry-sparkline"
            viewBox="0 0 ${width} ${height}"
            preserveAspectRatio="none"
            aria-hidden="true"
        >
            <polyline
                points="${points}"
                fill="none"
                stroke="${color}"
                stroke-width="2"
                vector-effect="non-scaling-stroke"
            ></polyline>
        </svg>
    `;
}


function renderTelemetryHistory(history) {
    if (!Array.isArray(history) || history.length === 0) {
        return `
            <p class="telemetry-history-empty">
                Waiting for telemetry history
            </p>
        `;
    }

    const cpuValues = history.map(
        (record) => record.cpu_percent
    );

    const memoryValues = history.map(
        (record) => record.memory_percent
    );

    const diskValues = history.map((record) =>
        (
            Number(record.disk_free_gb) /
            Number(record.disk_total_gb)
        ) * 100
    );

    return `
        <div class="telemetry-history">
            <div>
                <span>CPU trend</span>
                ${buildSparkline(cpuValues, "#4f8cff")}
            </div>
            <div>
                <span>Memory trend</span>
                ${buildSparkline(memoryValues, "#a855f7")}
            </div>
            <div>
                <span>Disk free trend</span>
                ${buildSparkline(diskValues, "#2dd4bf")}
            </div>
        </div>
    `;
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
<article
    class="device-card"
    data-device-id="${escapeHtml(device.device_id)}"
    tabindex="0"
    role="button"
>
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
            ${device.telemetry ? `
                <div class="device-telemetry">
                    <p>
                        CPU:
                        ${Number(
                            device.telemetry.cpu_percent
                        ).toFixed(1)}%
                    </p>
                    <p>
                        Memory:
                        ${Number(
                            device.telemetry.memory_percent
                        ).toFixed(1)}%
                    </p>
                    <p>
                        Disk:
                        ${Number(
                            device.telemetry.disk_free_gb
                        ).toFixed(1)}
                        GB free of
                        ${Number(
                            device.telemetry.disk_total_gb
                        ).toFixed(1)}
                        GB
                    </p>
                    <p>
                        Uptime:
                        ${Math.floor(
                            device.telemetry.uptime_seconds / 86400
                        )}d
                        ${Math.floor(
                            (
                                device.telemetry.uptime_seconds %
                                86400
                            ) / 3600
                        )}h
                    </p>
                </div>
            ` : `
                <p>Telemetry: Waiting for agent data</p>
            `}
            ${renderTelemetryHistory(
                device.telemetryHistory
            )}
        </article>
    `).join("");
}

async function openDeviceDetails(deviceId) {
    deviceDetailsSection.hidden = false;
    deviceDetailsTitle.textContent = "Loading device...";
    deviceDetailsSummary.innerHTML = `
        <p class="empty-state">Loading device details...</p>
    `;
    deviceAlertsTableBody.innerHTML = `
        <tr>
            <td colspan="4">Loading alerts...</td>
        </tr>
    `;
    deviceEventsTableBody.innerHTML = `
        <tr>
            <td colspan="4">Loading events...</td>
        </tr>
    `;

    const encodedDeviceId = encodeURIComponent(deviceId);

    try {
        const [device, telemetry, alerts, events] = await Promise.all([
            fetchJson(`/devices/${encodedDeviceId}`),
            fetchJson(`/devices/${encodedDeviceId}/telemetry/latest`),
            fetchJson(`/devices/${encodedDeviceId}/alerts?limit=25`),
            fetchJson(`/devices/${encodedDeviceId}/events?limit=25`),
        ]);

        deviceDetailsTitle.textContent = device.hostname;

        deviceDetailsSummary.innerHTML = `
            <div class="device-detail-stat">
                <strong>Status</strong>
                <span>${escapeHtml(device.status)}</span>
            </div>
            <div class="device-detail-stat">
                <strong>Device ID</strong>
                <span>${escapeHtml(device.device_id)}</span>
            </div>
            <div class="device-detail-stat">
                <strong>Operating system</strong>
                <span>${escapeHtml(device.operating_system)}</span>
            </div>
            <div class="device-detail-stat">
                <strong>IP address</strong>
                <span>${escapeHtml(device.ip_address)}</span>
            </div>
            <div class="device-detail-stat">
                <strong>Agent version</strong>
                <span>${escapeHtml(device.agent_version)}</span>
            </div>
            <div class="device-detail-stat">
                <strong>Last seen</strong>
                <span>${escapeHtml(formatDate(device.last_seen))}</span>
            </div>
            <div class="device-detail-stat">
                <strong>CPU</strong>
                <span>${Number(telemetry.cpu_percent).toFixed(1)}%</span>
            </div>
            <div class="device-detail-stat">
                <strong>Memory</strong>
                <span>${Number(telemetry.memory_percent).toFixed(1)}%</span>
            </div>
        `;

        deviceAlertsTableBody.innerHTML = alerts.length
            ? alerts.map((alert) => `
                <tr>
                    <td>${escapeHtml(alert.severity)}</td>
                    <td>${escapeHtml(alert.title)}</td>
                    <td>${escapeHtml(alert.status)}</td>
                    <td>${escapeHtml(formatDate(alert.created_at))}</td>
                </tr>
            `).join("")
            : `
                <tr>
                    <td colspan="4" class="empty-state">
                        No alerts found for this device.
                    </td>
                </tr>
            `;

        deviceEventsTableBody.innerHTML = events.length
            ? events.map((event) => `
                <tr>
                    <td>${escapeHtml(event.windows_event_id)}</td>
                    <td>${escapeHtml(event.provider)}</td>
                    <td>${escapeHtml(event.level)}</td>
                    <td>${escapeHtml(formatDate(event.occurred_at))}</td>
                </tr>
            `).join("")
            : `
                <tr>
                    <td colspan="4" class="empty-state">
                        No security events found for this device.
                    </td>
                </tr>
            `;

        deviceDetailsSection.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    } catch (error) {
        console.error(error);
        deviceDetailsTitle.textContent = "Device details";
        deviceDetailsSummary.innerHTML = `
            <p class="empty-state error-message">
                Unable to load device details.
            </p>
        `;
    }
}

deviceList.addEventListener("click", (event) => {
    const deviceCard = event.target.closest(
        ".device-card[data-device-id]"
    );

    if (!deviceCard) {
        return;
    }

    openDeviceDetails(deviceCard.dataset.deviceId);
});

deviceList.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") {
        return;
    }

    const deviceCard = event.target.closest(
        ".device-card[data-device-id]"
    );

    if (!deviceCard) {
        return;
    }

    event.preventDefault();
    openDeviceDetails(deviceCard.dataset.deviceId);
});

closeDeviceDetailsButton.addEventListener("click", () => {
    deviceDetailsSection.hidden = true;

    document.querySelector("#devices").scrollIntoView({
        behavior: "smooth",
        block: "start",
    });
});


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

        await Promise.all(
            devices.map(async (device) => {
                device.telemetry = await fetchJson(
                    `/devices/${encodeURIComponent(
                        device.device_id
                    )}/telemetry/latest`
                );
                device.telemetryHistory = await fetchJson(
                    `/devices/${encodeURIComponent(
                        device.device_id
                    )}/telemetry?limit=30`
                );
            })
        );

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

let activeInvestigationAlertId = null;
let activeAnalysts = [];


async function loadAnalysts() {
    activeAnalysts = await fetchJson("/auth/analysts");

    const assignmentSelect =
        document.getElementById("assignment-user");

    assignmentSelect.replaceChildren();

    const unassignedOption = document.createElement("option");
    unassignedOption.value = "";
    unassignedOption.textContent = "Select an analyst";
    assignmentSelect.appendChild(unassignedOption);

    activeAnalysts.forEach((analyst) => {
        const option = document.createElement("option");

        option.value = analyst.id;
        option.textContent =
            `${analyst.username} (${analyst.role})`;

        assignmentSelect.appendChild(option);
    });
}


async function loadAlertAssignment(alertId) {
    const response = await fetch(
        `/alerts/${alertId}/assignment`
    );

    if (response.status === 401) {
        window.location.replace("/login");
        return;
    }

    const assignmentSelect =
        document.getElementById("assignment-user");

    if (response.status === 404) {
        assignmentSelect.value = "";
        return;
    }

    if (!response.ok) {
        throw new Error("Unable to load alert assignment.");
    }

    const assignment = await response.json();

    assignmentSelect.value =
        String(assignment.assigned_user_id);
}

async function loadInvestigationNotes(alertId) {
    const notes = await fetchJson(
        `/alerts/${alertId}/notes`
    );

    const notesContainer =
        document.getElementById("investigation-notes");

    notesContainer.replaceChildren();

    if (notes.length === 0) {
        const emptyMessage = document.createElement("p");
        emptyMessage.className = "empty-state";
        emptyMessage.textContent =
            "No investigation notes have been added.";

        notesContainer.appendChild(emptyMessage);
        return;
    }

    notes.forEach((note) => {
        const author = activeAnalysts.find(
            (analyst) => analyst.id === note.author_user_id
        );

        const noteElement = document.createElement("article");
        noteElement.className = "investigation-note";

        const metadata = document.createElement("p");
        metadata.className = "investigation-note-meta";
        metadata.textContent =
            `${author ? author.username : `User #${note.author_user_id}`} · ` +
            formatDate(note.created_at);

        const body = document.createElement("p");
        body.className = "investigation-note-body";
        body.textContent = note.body;

        noteElement.append(metadata, body);
        notesContainer.appendChild(noteElement);
    });
}


async function submitInvestigationNote(event) {
    event.preventDefault();

    if (!activeInvestigationAlertId) {
        return;
    }

    const noteInput = document.getElementById("note-body");
    const noteBody = noteInput.value.trim();

    if (!noteBody) {
        alert("Enter an investigation note.");
        return;
    }

    const response = await fetch(
        `/alerts/${activeInvestigationAlertId}/notes`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                body: noteBody,
            }),
        }
    );

    if (response.status === 401) {
        window.location.replace("/login");
        return;
    }

    if (!response.ok) {
        throw new Error("Unable to add investigation note.");
    }

    noteInput.value = "";

    await loadInvestigationNotes(
        activeInvestigationAlertId
    );
}


async function saveAlertAssignment() {
    const assignmentSelect =
        document.getElementById("assignment-user");

    const assignedUserId = Number(assignmentSelect.value);

    if (!assignedUserId || !activeInvestigationAlertId) {
        alert("Select an analyst first.");
        return;
    }

    const response = await fetch(
        `/alerts/${activeInvestigationAlertId}/assignment`,
        {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                assigned_user_id: assignedUserId,
            }),
        }
    );

    if (response.status === 401) {
        window.location.replace("/login");
        return;
    }

    if (!response.ok) {
        throw new Error("Unable to save alert assignment.");
    }

    alert("Alert assignment saved.");
}
async function openInvestigation(alertId) {
    activeInvestigationAlertId = alertId;

    const modal = document.getElementById(
        "investigation-modal"
    );

    document.getElementById(
        "investigation-title"
    ).textContent = `Investigate Alert #${alertId}`;

    document.getElementById(
        "investigation-alert-summary"
    ).textContent =
        "Assign ownership and document the investigation timeline.";

    document.getElementById("note-body").value = "";

    modal.removeAttribute("hidden");

    try {
        await loadAnalysts();

        await Promise.all([
            loadAlertAssignment(alertId),
            loadInvestigationNotes(alertId),
        ]);
    } catch (error) {
        console.error(error);
        alert(error.message);
        closeInvestigation();
    }
}


function closeInvestigation() {
    document
        .getElementById("investigation-modal")
        .setAttribute("hidden", "");

    activeInvestigationAlertId = null;
}


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

alertsTableBody.addEventListener("click", (event) => {
    const button = event.target.closest(
        ".investigate-button"
    );

    if (!button) {
        return;
    }

    openInvestigation(
        Number(button.dataset.alertId)
    );
});


document
    .getElementById("close-investigation")
    .addEventListener("click", closeInvestigation);


document
    .getElementById("save-assignment")
    .addEventListener("click", () => {
        saveAlertAssignment().catch((error) => {
            console.error(error);
            alert(error.message);
        });
    });


document
    .getElementById("note-form")
    .addEventListener("submit", (event) => {
        submitInvestigationNote(event).catch((error) => {
            console.error(error);
            alert(error.message);
        });
    });


document
    .getElementById("investigation-modal")
    .addEventListener("click", (event) => {
        if (event.target === event.currentTarget) {
            closeInvestigation();
        }
    });


document.addEventListener("keydown", (event) => {
    if (
        event.key === "Escape" &&
        activeInvestigationAlertId
    ) {
        closeInvestigation();
    }
});