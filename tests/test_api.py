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
        "running": False,
        "sensor_connected": True,
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
        "running": False,
        "sensor_connected": False,
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
