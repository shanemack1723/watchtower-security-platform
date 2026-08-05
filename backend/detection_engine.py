import json
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import Alert, SecurityEvent


RULES_PATH = (
    Path(__file__).resolve().parent.parent
    / "detection_rules"
    / "rules.json"
)


@lru_cache
def load_detection_rules() -> list[dict]:
    with RULES_PATH.open("r", encoding="utf-8") as rules_file:
        return json.load(rules_file)


def detection_rule_matches(
    rule: dict,
    security_event: SecurityEvent,
    database: Session,
) -> bool:
    if rule["windows_event_id"] != security_event.windows_event_id:
        return False

    threshold = rule.get("threshold")
    window_minutes = rule.get("window_minutes")

    if threshold is None or window_minutes is None:
        return True

    window_start = security_event.occurred_at - timedelta(
        minutes=window_minutes
    )

    matching_event_count = database.scalar(
        select(func.count(SecurityEvent.id)).where(
            SecurityEvent.device_id == security_event.device_id,
            SecurityEvent.windows_event_id
            == security_event.windows_event_id,
            SecurityEvent.occurred_at >= window_start,
            SecurityEvent.occurred_at <= security_event.occurred_at,
        )
    )

    return matching_event_count == threshold


def evaluate_security_event(
    security_event: SecurityEvent,
    database: Session,
) -> list[Alert]:
    created_alerts: list[Alert] = []

    for rule in load_detection_rules():
        if not detection_rule_matches(
            rule=rule,
            security_event=security_event,
            database=database,
        ):
            continue

        existing_alert = database.scalar(
            select(Alert).where(
                Alert.security_event_id == security_event.id,
                Alert.rule_id == rule["rule_id"],
            )
        )

        if existing_alert is not None:
            continue

        alert = Alert(
            security_event_id=security_event.id,
            rule_id=rule["rule_id"],
            title=rule["title"],
            description=rule["description"],
            severity=rule["severity"],
            status="open",
        )

        database.add(alert)
        created_alerts.append(alert)

    if created_alerts:
        database.commit()

        for alert in created_alerts:
            database.refresh(alert)

    return created_alerts