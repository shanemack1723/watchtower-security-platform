from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database import Base, get_database
from backend.main import app


TEST_API_KEY = "watchtower-test-api-key"

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

    def override_database() -> Generator[Session, None, None]:
        database = TestSession()

        try:
            yield database
        finally:
            database.close()

    app.dependency_overrides[get_database] = override_database

    with TestClient(app) as test_client:
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