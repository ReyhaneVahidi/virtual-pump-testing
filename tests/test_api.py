"""Integration tests for the virtual pump HTTP API.

FastAPI's TestClient sends requests to the application in memory,
without starting a web server or requiring physical pump hardware.
"""

import pytest
from fastapi.testclient import TestClient

from api import create_app


@pytest.fixture
def client():
    """Provide a new API and pump state for each test."""
    with TestClient(create_app()) as test_client:
        yield test_client


def test_status_reports_initial_state(client):
    """A new pump is stopped, has no speed, and has a connected sensor."""
    response = client.get("/status")

    assert response.status_code == 200
    assert response.json() == {
        "speed": 0,
        "measured_rpm": 0.0,
        "running": False,
        "sensor_connected": True,
        "motor_fault_active": False,
        "feedback_fault_code": None,
    }


@pytest.mark.parametrize("rpm", [1, 150, 300])
def test_set_speed_accepts_valid_values(client, rpm):
    """The API accepts speeds within the inclusive 1–300 RPM range."""
    response = client.post(f"/speed/{rpm}")

    assert response.status_code == 200
    assert response.json() == {"speed": rpm}
    assert client.get("/status").json()["speed"] == rpm


@pytest.mark.parametrize("rpm", [-1, 0, 301])
def test_set_speed_rejects_out_of_range_values(client, rpm):
    """Invalid RPM values return HTTP 400 rather than modifying the pump."""
    response = client.post(f"/speed/{rpm}")

    assert response.status_code == 400
    assert response.json() == {"detail": "Speed must be between 1 and 300 RPM"}
    assert client.get("/status").json()["speed"] == 0


def test_invalid_speed_preserves_previous_setting(client):
    """A rejected speed request must not overwrite a valid setting."""
    client.post("/speed/120")

    response = client.post("/speed/301")

    assert response.status_code == 400
    assert client.get("/status").json()["speed"] == 120


def test_non_integer_speed_returns_validation_error(client):
    """Non-integer path parameters are rejected by FastAPI with HTTP 422."""
    response = client.post("/speed/fast")

    assert response.status_code == 422


def test_start_without_speed_returns_conflict(client):
    """Starting without a speed returns HTTP 409 and leaves the pump stopped."""
    response = client.post("/start")

    assert response.status_code == 409
    assert response.json() == {"detail": "Set pump speed first"}
    assert client.get("/status").json()["running"] is False


def test_start_with_valid_speed(client):
    """A configured pump starts and exposes its running state over HTTP."""
    client.post("/speed/120")

    response = client.post("/start")

    assert response.status_code == 200
    assert response.json() == {"running": True}
    assert client.get("/status").json()["running"] is True


def test_stop_running_pump(client):
    """The stop endpoint changes a running pump to its stopped state."""
    client.post("/speed/120")
    client.post("/start")

    response = client.post("/stop")

    assert response.status_code == 200
    assert response.json() == {"running": False}
    assert client.get("/status").json()["running"] is False


def test_stop_is_idempotent(client):
    """Stopping an already stopped pump succeeds without changing its state."""
    response = client.post("/stop")

    assert response.status_code == 200
    assert response.json() == {"running": False}


def test_sensor_fault_stops_running_pump(client):
    """A simulated sensor failure forces a running pump to stop."""
    client.post("/speed/120")
    client.post("/start")

    response = client.post("/simulation/sensor/disconnect")

    assert response.status_code == 200
    assert response.json() == {"sensor_connected": False, "running": False}
    assert client.get("/status").json() == {
        "speed": 120,
        "measured_rpm": None,
        "running": False,
        "sensor_connected": False,
        "motor_fault_active": False,
        "feedback_fault_code": None,
    }


def test_sensor_fault_blocks_pump_start(client):
    """Starting the pump during a sensor fault returns HTTP 409."""
    client.post("/speed/120")
    client.post("/simulation/sensor/disconnect")

    response = client.post("/start")

    assert response.status_code == 409
    assert response.json() == {"detail": "Sensor disconnected"}
    assert client.get("/status").json()["running"] is False


def test_sensor_reconnection_does_not_restart_pump(client):
    """Recovering a sensor must not automatically reactivate the pump."""
    client.post("/speed/120")
    client.post("/start")
    client.post("/simulation/sensor/disconnect")

    response = client.post("/simulation/sensor/reconnect")

    assert response.status_code == 200
    assert response.json() == {"sensor_connected": True, "running": False}
    assert client.get("/status").json()["running"] is False


def test_pump_can_restart_after_sensor_recovery(client):
    """An explicit start request succeeds after sensor reconnection."""
    client.post("/speed/120")
    client.post("/simulation/sensor/disconnect")
    client.post("/simulation/sensor/reconnect")

    response = client.post("/start")

    assert response.status_code == 200
    assert client.get("/status").json()["running"] is True


def test_motor_fault_stops_running_pump(client):
    """A motor failure stops a running pump and appears in its status."""
    client.post("/speed/120")
    client.post("/start")

    response = client.post("/simulation/motor/fail")

    assert response.status_code == 200
    assert response.json() == {"motor_fault_active": True, "running": False}
    assert client.get("/status").json() == {
        "speed": 120,
        "measured_rpm": 0.0,
        "running": False,
        "sensor_connected": True,
        "motor_fault_active": True,
        "feedback_fault_code": None,
    }


def test_motor_fault_blocks_start(client):
    """An active motor failure produces HTTP 409 on a start attempt."""
    client.post("/speed/120")
    client.post("/simulation/motor/fail")

    response = client.post("/start")

    assert response.status_code == 409
    assert response.json() == {"detail": "Motor fault active"}
    assert client.get("/status").json()["running"] is False


def test_motor_fault_can_be_injected_while_stopped(client):
    """A stopped pump can still register a motor fault before startup."""
    response = client.post("/simulation/motor/fail")

    assert response.status_code == 200
    assert response.json()["motor_fault_active"] is True


def test_resetting_motor_fault_does_not_restart_pump(client):
    """Clearing a motor failure does not automatically resume operation."""
    client.post("/speed/120")
    client.post("/start")
    client.post("/simulation/motor/fail")

    response = client.post("/simulation/motor/reset")

    assert response.status_code == 200
    assert response.json() == {"motor_fault_active": False, "running": False}
    assert client.get("/status").json()["running"] is False


def test_motor_fault_recovery_requires_explicit_start(client):
    """Operation can resume only through a new start request after reset."""
    client.post("/speed/120")
    client.post("/start")
    client.post("/simulation/motor/fail")
    client.post("/simulation/motor/reset")

    response = client.post("/start")

    assert response.status_code == 200
    assert client.get("/status").json()["running"] is True


def test_stop_does_not_clear_motor_fault(client):
    """A stop command does not implicitly clear a registered motor fault."""
    client.post("/simulation/motor/fail")

    response = client.post("/stop")

    assert response.status_code == 200
    assert client.get("/status").json()["motor_fault_active"] is True


def test_both_faults_must_be_cleared_before_restart(client):
    """Clearing the motor fault alone cannot bypass a sensor fault."""
    client.post("/speed/120")
    client.post("/simulation/motor/fail")
    client.post("/simulation/sensor/disconnect")
    client.post("/simulation/motor/reset")

    blocked_response = client.post("/start")
    assert blocked_response.status_code == 409
    assert client.get("/status").json()["running"] is False

    client.post("/simulation/sensor/reconnect")
    assert client.post("/start").status_code == 200


def test_repeated_motor_fault_and_reset_requests_are_safe(client):
    """Reapplying a motor failure or reset leaves a consistent pump state."""
    client.post("/simulation/motor/fail")
    failure_again = client.post("/simulation/motor/fail")
    client.post("/simulation/motor/reset")
    reset_again = client.post("/simulation/motor/reset")

    assert failure_again.json() == {"motor_fault_active": True, "running": False}
    assert reset_again.json() == {"motor_fault_active": False, "running": False}


def test_status_shows_commanded_and_measured_speed(client):
    """Status distinguishes requested speed from simulated feedback."""
    client.post("/speed/150")
    client.post("/start")

    status = client.get("/status").json()
    assert status["speed"] == 150
    assert status["measured_rpm"] == 150.0
    assert status["feedback_fault_code"] is None


@pytest.mark.parametrize("reading", [120, 150, 180])
def test_normal_feedback_keeps_pump_running(client, reading):
    """Readings within the 20% tolerance preserve normal operation."""
    client.post("/speed/150")
    client.post("/start")

    response = client.post("/simulation/feedback", json={"measured_rpm": reading})

    assert response.status_code == 200
    assert response.json() == {
        "measured_rpm": float(reading), "fault_code": None, "running": True
    }


@pytest.mark.parametrize(
    ("reading", "code"),
    [(0, "BLOCKED"), (119, "UNDERSPEED"), (181, "OVERSPEED")],
)
def test_feedback_faults_stop_pump_through_api(client, reading, code):
    """HTTP feedback injection reports the detected fault and stops the pump."""
    client.post("/speed/150")
    client.post("/start")

    response = client.post("/simulation/feedback", json={"measured_rpm": reading})

    assert response.status_code == 200
    assert response.json() == {
        "measured_rpm": float(reading), "fault_code": code, "running": False
    }
    assert client.get("/status").json()["feedback_fault_code"] == code


@pytest.mark.parametrize("payload", [
    {"measured_rpm": -1},
    {"measured_rpm": 1001},
    {"measured_rpm": "invalid"},
    {},
])
def test_bad_feedback_payload_returns_validation_error(client, payload):
    """Invalid JSON input is rejected before it reaches the pump model."""
    client.post("/speed/150")
    client.post("/start")

    response = client.post("/simulation/feedback", json=payload)

    assert response.status_code == 422
    assert client.get("/status").json()["running"] is True


def test_feedback_while_stopped_returns_conflict(client):
    """Measurements are only accepted during a simulated running cycle."""
    response = client.post("/simulation/feedback", json={"measured_rpm": 100})
    assert response.status_code == 409
    assert response.json() == {"detail": "Pump is not running"}


def test_api_requires_reset_after_feedback_fault(client):
    """Fault recovery requires a reset followed by an explicit start."""
    client.post("/speed/150")
    client.post("/start")
    client.post("/simulation/feedback", json={"measured_rpm": 0})

    rejected = client.post("/start")
    assert rejected.status_code == 409
    assert rejected.json() == {"detail": "Feedback fault active"}

    reset = client.post("/simulation/feedback/reset")
    assert reset.status_code == 200
    assert reset.json() == {"feedback_fault_code": None, "running": False}

    assert client.post("/start").json()["running"] is True


def test_motor_fault_still_blocks_start_after_feedback_reset(client):
    """Independent interlocks remain active after RPM fault recovery."""
    client.post("/speed/150")
    client.post("/start")
    client.post("/simulation/feedback", json={"measured_rpm": 0})
    client.post("/simulation/motor/fail")
    client.post("/simulation/feedback/reset")

    assert client.post("/start").json() == {"detail": "Motor fault active"}
    client.post("/simulation/motor/reset")
    assert client.post("/start").status_code == 200


def test_events_endpoint_includes_fault_code_and_utc_timestamp(client):
    """HTTP clients can retrieve timestamped and structured fault events."""
    from datetime import datetime, timezone

    client.post("/speed/150")
    client.post("/start")
    client.post("/simulation/feedback", json={"measured_rpm": 0})

    response = client.get("/events")
    assert response.status_code == 200
    events = response.json()["events"]
    assert response.json()["total"] == 4
    assert [entry["id"] for entry in events] == [1, 2, 3, 4]
    assert events[-1]["type"] == "feedback_fault_detected"
    assert events[-1]["details"]["fault_code"] == "BLOCKED"
    assert datetime.fromisoformat(events[-1]["timestamp_utc"].replace("Z", "+00:00")).tzinfo == timezone.utc


def test_events_endpoint_limits_history(client):
    """The API returns only the requested number of latest events."""
    client.post("/speed/100")
    client.post("/start")
    client.post("/stop")

    response = client.get("/events?limit=2")
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert [event["type"] for event in response.json()["events"]] == [
        "pump_started", "pump_stopped"
    ]


@pytest.mark.parametrize("limit", ["0", "1001", "abc"])
def test_events_endpoint_rejects_invalid_limits(client, limit):
    """Query validation prevents unreasonable or malformed log requests."""
    assert client.get(f"/events?limit={limit}").status_code == 422


def test_event_histories_are_isolated_between_app_instances():
    """Tests using separate API instances cannot leak log or pump state."""
    with TestClient(create_app()) as first, TestClient(create_app()) as second:
        first.post("/speed/100")
        assert first.get("/events").json()["total"] == 1
        assert second.get("/events").json()["total"] == 0
