from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database import Base, get_database
from backend.main import app
from backend.auth_security import hash_password
from backend.models import User


TEST_API_KEY = "watchtower-test-api-key"
TEST_JWT_SECRET = "watchtower-test-jwt-secret-at-least-32-characters"
TEST_ADMIN_USERNAME = "testadmin"
TEST_ADMIN_PASSWORD = "TestAdminPassword123!"

AGENT_HEADERS = {
    "X-Watchtower-API-Key": TEST_API_KEY,
}

DEVICE_DATA = {
    "device_id": "TEST-PC-001",
    "hostname": "Test-PC",
    "operating_system": "Windows 11",
    "ip_address": "192.168.1.100",
    "agent_version": "0.1.0",
}


@pytest.fixture
def client(
    tmp_path,
    monkeypatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv(
        "WATCHTOWER_AGENT_API_KEY",
        TEST_API_KEY,
    )

    monkeypatch.setenv(
        "WATCHTOWER_JWT_SECRET",
        TEST_JWT_SECRET,
    )

    database_path = tmp_path / "watchtower-test.db"

    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )

    TestSession = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    setup_database = TestSession()

    try:
        setup_database.add(
            User(
                username=TEST_ADMIN_USERNAME,
                password_hash=hash_password(TEST_ADMIN_PASSWORD),
                role="admin",
                is_active=True,
            )
        )
        setup_database.commit()
    finally:
        setup_database.close()

    def override_database() -> Generator[Session, None, None]:
        database = TestSession()

        try:
            yield database
        finally:
            database.close()

    app.dependency_overrides[get_database] = override_database

    with TestClient(app) as test_client:
        login_response = test_client.post(
            "/auth/login",
            json={
                "username": TEST_ADMIN_USERNAME,
                "password": TEST_ADMIN_PASSWORD,
            },
        )

        assert login_response.status_code == 200
        yield test_client

    app.dependency_overrides.clear()
    test_engine.dispose()


def register_test_device(client: TestClient):
    return client.post(
        "/devices/register",
        headers=AGENT_HEADERS,
        json=DEVICE_DATA,
    )


def create_failed_login_event(
    client: TestClient,
    record_id: int,
    occurred_at: str,
):
    return client.post(
        "/events/",
        headers=AGENT_HEADERS,
        json={
            "device_id": DEVICE_DATA["device_id"],
            "windows_event_id": 4625,
            "record_id": record_id,
            "log_name": "Security",
            "provider": "Watchtower-Test",
            "level": "Information",
            "message": "Automated failed-login test.",
            "occurred_at": occurred_at,
            "raw_data": {
                "simulation": True,
                "source_ip": "192.168.1.200",
            },
        },
    )


def test_registration_requires_api_key(client: TestClient):
    response = client.post(
        "/devices/register",
        json=DEVICE_DATA,
    )

    assert response.status_code == 401


def test_authorized_device_registration(client: TestClient):
    response = register_test_device(client)

    assert response.status_code == 201
    assert response.json()["device_id"] == "TEST-PC-001"
    assert response.json()["status"] == "online"

def test_device_heartbeat(client: TestClient):
    registration_response = register_test_device(client)

    assert registration_response.status_code == 201

    response = client.post(
        f"/devices/{DEVICE_DATA['device_id']}/heartbeat",
        headers=AGENT_HEADERS,
        json={
            "agent_version": "0.2.0",
        },
    )

    assert response.status_code == 200
    assert response.json()["device_id"] == DEVICE_DATA["device_id"]
    assert response.json()["status"] == "online"
    assert response.json()["agent_version"] == "0.2.0"

def test_device_heartbeat_requires_api_key(client: TestClient):
    registration_response = register_test_device(client)

    assert registration_response.status_code == 201

    response = client.post(
        f"/devices/{DEVICE_DATA['device_id']}/heartbeat",
        json={
            "agent_version": "0.2.0",
        },
    )

    assert response.status_code == 401

def test_device_telemetry_workflow(client: TestClient):
    registration_response = register_test_device(client)

    assert registration_response.status_code == 201

    telemetry_response = client.post(
        f"/devices/{DEVICE_DATA['device_id']}/telemetry",
        headers=AGENT_HEADERS,
        json={
            "cpu_percent": 27.5,
            "memory_percent": 61.2,
            "disk_total_gb": 475.0,
            "disk_free_gb": 203.4,
            "uptime_seconds": 86400,
        },
    )

    assert telemetry_response.status_code == 201
    assert telemetry_response.json()["cpu_percent"] == 27.5
    assert telemetry_response.json()["memory_percent"] == 61.2
    assert telemetry_response.json()["disk_free_gb"] == 203.4
    assert telemetry_response.json()["uptime_seconds"] == 86400

    latest_response = client.get(
        f"/devices/{DEVICE_DATA['device_id']}/telemetry/latest"
    )

    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == telemetry_response.json()["id"]

    second_telemetry_response = client.post(
        f"/devices/{DEVICE_DATA['device_id']}/telemetry",
        headers=AGENT_HEADERS,
        json={
            "cpu_percent": 35.0,
            "memory_percent": 64.0,
            "disk_total_gb": 475.0,
            "disk_free_gb": 200.0,
            "uptime_seconds": 86500,
        },
    )

    assert second_telemetry_response.status_code == 201

    history_response = client.get(
        f"/devices/{DEVICE_DATA['device_id']}/telemetry?limit=10"
    )

    assert history_response.status_code == 200
    assert len(history_response.json()) == 2
    assert history_response.json()[0]["id"] == telemetry_response.json()["id"]
    assert (
        history_response.json()[1]["id"]
        == second_telemetry_response.json()["id"]
    )

def test_device_health_alert_lifecycle(client: TestClient):
    registration_response = register_test_device(client)

    assert registration_response.status_code == 201

    unhealthy_telemetry = {
        "cpu_percent": 95.0,
        "memory_percent": 92.0,
        "disk_total_gb": 100.0,
        "disk_free_gb": 5.0,
        "uptime_seconds": 86400,
    }

    first_response = client.post(
        f"/devices/{DEVICE_DATA['device_id']}/telemetry",
        headers=AGENT_HEADERS,
        json=unhealthy_telemetry,
    )

    assert first_response.status_code == 201

    alerts_response = client.get("/alerts/")

    assert alerts_response.status_code == 200

    health_rule_ids = {
        "device-high-cpu",
        "device-high-memory",
        "device-low-disk",
    }

    health_alerts = [
        alert
        for alert in alerts_response.json()
        if alert["rule_id"] in health_rule_ids
    ]

    assert len(health_alerts) == 3
    assert all(
        alert["status"] == "open"
        for alert in health_alerts
    )

    duplicate_response = client.post(
        f"/devices/{DEVICE_DATA['device_id']}/telemetry",
        headers=AGENT_HEADERS,
        json=unhealthy_telemetry,
    )

    assert duplicate_response.status_code == 201

    duplicate_alerts_response = client.get("/alerts/")

    duplicate_health_alerts = [
        alert
        for alert in duplicate_alerts_response.json()
        if alert["rule_id"] in health_rule_ids
    ]

    assert len(duplicate_health_alerts) == 3

    recovery_response = client.post(
        f"/devices/{DEVICE_DATA['device_id']}/telemetry",
        headers=AGENT_HEADERS,
        json={
            "cpu_percent": 20.0,
            "memory_percent": 40.0,
            "disk_total_gb": 100.0,
            "disk_free_gb": 60.0,
            "uptime_seconds": 86500,
        },
    )

    assert recovery_response.status_code == 201

    recovered_alerts_response = client.get("/alerts/")

    recovered_health_alerts = [
        alert
        for alert in recovered_alerts_response.json()
        if alert["rule_id"] in health_rule_ids
    ]

    assert len(recovered_health_alerts) == 3
    assert all(
        alert["status"] == "resolved"
        for alert in recovered_health_alerts
    )

def test_stale_device_is_marked_offline(
    client: TestClient,
    monkeypatch,
):
    registration_response = register_test_device(client)

    assert registration_response.status_code == 201

    monkeypatch.setattr(
        "backend.routes.devices.DEVICE_OFFLINE_AFTER",
        timedelta(seconds=0),
    )

    response = client.get("/devices/")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "offline"

    alerts_response = client.get("/alerts/")

    assert alerts_response.status_code == 200

    offline_alerts = [
        alert
        for alert in alerts_response.json()
        if alert["rule_id"] == "device-offline"
    ]

    assert len(offline_alerts) == 1
    assert offline_alerts[0]["title"] == "Device offline: Test-PC"
    assert offline_alerts[0]["severity"] == "high"
    assert offline_alerts[0]["status"] == "open"

    second_devices_response = client.get("/devices/")

    assert second_devices_response.status_code == 200

    second_alerts_response = client.get("/alerts/")

    second_offline_alerts = [
        alert
        for alert in second_alerts_response.json()
        if alert["rule_id"] == "device-offline"
    ]

    assert len(second_offline_alerts) == 1

    heartbeat_response = client.post(
        f"/devices/{DEVICE_DATA['device_id']}/heartbeat",
        headers=AGENT_HEADERS,
        json={
            "agent_version": "0.2.0",
        },
    )

    assert heartbeat_response.status_code == 200
    assert heartbeat_response.json()["status"] == "online"

    recovered_alerts_response = client.get("/alerts/")

    assert recovered_alerts_response.status_code == 200

    recovered_offline_alerts = [
        alert
        for alert in recovered_alerts_response.json()
        if alert["rule_id"] == "device-offline"
    ]

    assert len(recovered_offline_alerts) == 1
    assert recovered_offline_alerts[0]["status"] == "resolved"


def test_duplicate_event_is_not_stored_twice(client: TestClient):
    register_test_device(client)

    first_response = create_failed_login_event(
        client=client,
        record_id=50001,
        occurred_at="2026-08-05T02:00:00Z",
    )

    second_response = create_failed_login_event(
        client=client,
        record_id=50001,
        occurred_at="2026-08-05T02:00:00Z",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] == second_response.json()["id"]

    events_response = client.get("/events/")

    assert events_response.status_code == 200
    assert len(events_response.json()) == 1


def test_failed_login_creates_medium_alert(client: TestClient):
    register_test_device(client)

    event_response = create_failed_login_event(
        client=client,
        record_id=60001,
        occurred_at="2026-08-05T02:05:00Z",
    )

    assert event_response.status_code == 201

    alerts_response = client.get("/alerts/")

    assert alerts_response.status_code == 200

    alerts = alerts_response.json()

    assert len(alerts) == 1
    assert alerts[0]["rule_id"] == "WIN-FAILED-LOGIN"
    assert alerts[0]["severity"] == "medium"


def test_five_failures_create_high_correlation_alert(
    client: TestClient,
):
    register_test_device(client)

    event_times = [
        "2026-08-05T02:10:00Z",
        "2026-08-05T02:11:00Z",
        "2026-08-05T02:12:00Z",
        "2026-08-05T02:13:00Z",
        "2026-08-05T02:14:00Z",
    ]

    for index, event_time in enumerate(event_times):
        response = create_failed_login_event(
            client=client,
            record_id=70001 + index,
            occurred_at=event_time,
        )

        assert response.status_code == 201

    alerts_response = client.get("/alerts/")
    alerts = alerts_response.json()

    correlation_alerts = [
        alert
        for alert in alerts
        if alert["rule_id"]
        == "WIN-REPEATED-FAILED-LOGINS"
    ]

    assert len(correlation_alerts) == 1
    assert correlation_alerts[0]["severity"] == "high"

def test_authenticated_admin_can_view_profile(
    client: TestClient,
):
    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == TEST_ADMIN_USERNAME
    assert response.json()["role"] == "admin"


def test_invalid_password_is_rejected(
    client: TestClient,
):
    response = client.post(
        "/auth/login",
        json={
            "username": TEST_ADMIN_USERNAME,
            "password": "IncorrectPassword123!",
        },
    )

    assert response.status_code == 401


def test_logout_protects_dashboard_data(
    client: TestClient,
):
    logout_response = client.post("/auth/logout")

    assert logout_response.status_code == 204

    alerts_response = client.get("/alerts/")
    events_response = client.get("/events/")
    devices_response = client.get("/devices/")

    assert alerts_response.status_code == 401
    assert events_response.status_code == 401
    assert devices_response.status_code == 401


def test_admin_can_view_audit_log(
    client: TestClient,
):
    response = client.get("/audit/")

    assert response.status_code == 200

    audit_logs = response.json()
    actions = [entry["action"] for entry in audit_logs]

    assert "authentication.succeeded" in actions

def test_alert_investigation_workflow(
    client: TestClient,
):
    register_test_device(client)

    event_response = create_failed_login_event(
        client=client,
        record_id=70001,
        occurred_at="2026-08-05T03:00:00Z",
    )

    assert event_response.status_code == 201

    alerts_response = client.get("/alerts/")
    assert alerts_response.status_code == 200

    alert_id = alerts_response.json()[0]["id"]

    profile_response = client.get("/auth/me")
    assert profile_response.status_code == 200

    user_id = profile_response.json()["id"]

    assignment_response = client.put(
        f"/alerts/{alert_id}/assignment",
        json={
            "assigned_user_id": user_id,
        },
    )

    assert assignment_response.status_code == 200
    assert assignment_response.json()["alert_id"] == alert_id
    assert assignment_response.json()["assigned_user_id"] == user_id

    note_response = client.post(
        f"/alerts/{alert_id}/notes",
        json={
            "body": "Reviewed the alert and documented the investigation.",
        },
    )

    assert note_response.status_code == 201
    assert note_response.json()["author_user_id"] == user_id

    notes_response = client.get(
        f"/alerts/{alert_id}/notes"
    )

    assert notes_response.status_code == 200
    assert len(notes_response.json()) == 1

    audit_response = client.get("/audit/")
    assert audit_response.status_code == 200

    actions = [
        entry["action"]
        for entry in audit_response.json()
    ]

    assert "alert.assigned" in actions
    assert "alert.note_added" in actions