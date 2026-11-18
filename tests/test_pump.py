
"""Unit tests for the simulated laboratory pump.

These tests exercise the public methods of the Pump class
without requiring physical hardware or a running API server.
"""

import pytest

from pump import Pump


def test_pump_starts_when_speed_is_set():
    """The pump starts when a valid speed and sensor are available."""
    pump = Pump()
    pump.set_speed(150)

    pump.start()

    assert pump.running is True


def test_pump_stops():
    """Stopping a running pump changes its running state to False."""
    pump = Pump()
    pump.set_speed(150)
    pump.start()

    pump.stop()

    assert pump.running is False


@pytest.mark.parametrize("speed", [1, 300])
def test_accepts_speed_at_valid_limits(speed):
    """Both endpoints of the allowed 1–300 RPM range are accepted."""
    pump = Pump()

    pump.set_speed(speed)

    assert pump.speed == speed


@pytest.mark.parametrize("speed", [0, 301, 500])
def test_rejects_speed_outside_valid_range(speed):
    """Out-of-range speed values raise an error and leave speed unchanged."""
    pump = Pump()

    with pytest.raises(ValueError, match="Speed must be between 1 and 300 RPM"):
        pump.set_speed(speed)

    assert pump.speed == 0


def test_cannot_start_without_speed():
    """Starting a pump before selecting a speed is prohibited."""
    pump = Pump()

    with pytest.raises(RuntimeError, match="Set pump speed first"):
        pump.start()

    assert pump.running is False


def test_sensor_disconnection_stops_pump():
    """Losing the sensor connection immediately stops a running pump."""
    pump = Pump()
    pump.set_speed(150)
    pump.start()

    pump.disconnect_sensor()

    assert pump.sensor_connected is False
    assert pump.running is False


def test_cannot_start_with_disconnected_sensor():
    """The pump cannot run while the simulated sensor is disconnected."""
    pump = Pump()
    pump.set_speed(150)
    pump.disconnect_sensor()

    with pytest.raises(RuntimeError, match="Sensor disconnected"):
        pump.start()

    assert pump.running is False


def test_pump_can_restart_after_sensor_reconnection():
    """Restoring the sensor allows the pump to restart at its set speed."""
    pump = Pump()
    pump.set_speed(150)
    pump.disconnect_sensor()

    pump.reconnect_sensor()
    pump.start()

    assert pump.sensor_connected is True
    assert pump.speed == 150
    assert pump.running is True
