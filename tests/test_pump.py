"""Unit tests for the simulated laboratory pump.

These tests exercise the public methods of :class:`pump.Pump` without
requiring physical hardware or a running FastAPI server.
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


def test_motor_fault_stops_running_pump():
    """A motor failure forces the pump to stop without clearing its speed."""
    pump = Pump()
    pump.set_speed(150)
    pump.start()

    pump.fail_motor()

    assert pump.running is False
    assert pump.motor_fault_active is True
    assert pump.speed == 150


def test_motor_fault_prevents_start():
    """The pump refuses to start while its motor fault is active."""
    pump = Pump()
    pump.set_speed(150)
    pump.fail_motor()

    with pytest.raises(RuntimeError, match="Motor fault active"):
        pump.start()

    assert pump.running is False


def test_motor_fault_can_be_injected_before_start():
    """A fault injected at rest persists until explicitly reset."""
    pump = Pump()

    pump.fail_motor()

    assert pump.motor_fault_active is True
    assert pump.running is False


def test_resetting_motor_fault_does_not_restart_pump():
    """Resetting a motor fault never causes an automatic restart."""
    pump = Pump()
    pump.set_speed(150)
    pump.start()
    pump.fail_motor()

    pump.reset_motor_fault()

    assert pump.motor_fault_active is False
    assert pump.running is False


def test_motor_can_restart_after_fault_reset():
    """A reset fault permits a separate, explicit start request."""
    pump = Pump()
    pump.set_speed(150)
    pump.fail_motor()
    pump.reset_motor_fault()

    pump.start()

    assert pump.running is True


def test_stop_does_not_reset_motor_fault():
    """Stopping a faulted pump leaves its motor alarm latched."""
    pump = Pump()
    pump.fail_motor()

    pump.stop()

    assert pump.motor_fault_active is True


def test_recovery_from_motor_fault_does_not_clear_sensor_fault():
    """A pump cannot start until both independent faults are cleared."""
    pump = Pump()
    pump.set_speed(150)
    pump.fail_motor()
    pump.disconnect_sensor()
    pump.reset_motor_fault()

    with pytest.raises(RuntimeError, match="Sensor disconnected"):
        pump.start()

    pump.reconnect_sensor()
    pump.start()
    assert pump.running is True


def test_repeated_motor_fault_and_reset_are_safe():
    """Duplicate fail/reset commands do not lead to inconsistent states."""
    pump = Pump()
    pump.fail_motor()
    pump.fail_motor()

    assert pump.motor_fault_active is True
    assert pump.running is False

    pump.reset_motor_fault()
    pump.reset_motor_fault()

    assert pump.motor_fault_active is False
    assert pump.running is False


@pytest.mark.parametrize("rpm", [1, 150, 300])
def test_start_uses_ideal_feedback_until_an_update_arrives(rpm):
    """With no injected measurement, feedback follows the commanded speed."""
    pump = Pump()
    pump.set_speed(rpm)

    pump.start()

    assert pump.speed == rpm
    assert pump.measured_rpm == float(rpm)
    assert pump.feedback_fault_code is None


def test_changing_setpoint_updates_ideal_feedback():
    """A healthy running pump instantly follows a new setpoint in the model."""
    pump = Pump()
    pump.set_speed(100)
    pump.start()

    pump.set_speed(150)

    assert pump.measured_rpm == 150.0
    assert pump.running is True


@pytest.mark.parametrize("reading", [120, 150, 180])
def test_feedback_within_inclusive_tolerance_does_not_stop_pump(reading):
    """Exactly 80% and 120% of the target are accepted as normal."""
    pump = Pump()
    pump.set_speed(150)
    pump.start()

    result = pump.update_feedback(reading)

    assert result is None
    assert pump.measured_rpm == float(reading)
    assert pump.running is True
    assert pump.feedback_fault_code is None


@pytest.mark.parametrize(
    ("reading", "expected_code"),
    [(0, "BLOCKED"), (10, "UNDERSPEED"), (119, "UNDERSPEED"),
     (181, "OVERSPEED"), (300, "OVERSPEED")],
)
def test_abnormal_feedback_latches_fault_and_stops_pump(reading, expected_code):
    """Out-of-range measured RPM produces an explicit fault and safe stop."""
    pump = Pump()
    pump.set_speed(150)
    pump.start()

    fault_code = pump.update_feedback(reading)

    assert fault_code == expected_code
    assert pump.feedback_fault_code == expected_code
    assert pump.running is False
    assert pump.measured_rpm == float(reading)


def test_feedback_fault_requires_explicit_reset_and_restart():
    """Resetting a latched speed fault never restarts the pump automatically."""
    pump = Pump()
    pump.set_speed(150)
    pump.start()
    pump.update_feedback(0)

    with pytest.raises(RuntimeError, match="Feedback fault active"):
        pump.start()

    pump.reset_feedback_fault()
    assert pump.running is False
    assert pump.feedback_fault_code is None
    assert pump.measured_rpm == 0.0

    pump.start()
    assert pump.running is True


def test_feedback_reset_does_not_bypass_other_interlocks():
    """Resetting the RPM alarm does not clear an independent motor fault."""
    pump = Pump()
    pump.set_speed(100)
    pump.start()
    pump.update_feedback(150)
    pump.fail_motor()

    pump.reset_feedback_fault()

    with pytest.raises(RuntimeError, match="Motor fault active"):
        pump.start()
    assert pump.motor_fault_active is True


@pytest.mark.parametrize("reading", [-1, 1001, float("nan"), float("inf"), True, "fast"])
def test_invalid_feedback_is_rejected_without_changing_state(reading):
    """Non-finite, non-numeric and out-of-range readings are not accepted."""
    pump = Pump()
    pump.set_speed(100)
    pump.start()

    with pytest.raises(ValueError, match="Measured RPM must be"):
        pump.update_feedback(reading)

    assert pump.running is True
    assert pump.measured_rpm == 100.0
    assert pump.feedback_fault_code is None


def test_feedback_requires_pump_to_be_running():
    """A stopped pump cannot accept a simulated operating measurement."""
    pump = Pump()
    with pytest.raises(RuntimeError, match="Pump is not running"):
        pump.update_feedback(100)


def test_sensor_disconnection_invalidates_last_measurement():
    """Disconnected sensors provide no available RPM measurement."""
    pump = Pump()
    pump.set_speed(100)
    pump.start()
    pump.disconnect_sensor()

    assert pump.measured_rpm is None
    with pytest.raises(RuntimeError, match="Sensor disconnected"):
        pump.update_feedback(50)

    pump.reconnect_sensor()
    assert pump.measured_rpm == 0.0
    assert pump.running is False


def test_event_log_records_timestamp_and_order():
    """Every operational action receives a UTC timestamp and stable order."""
    from datetime import datetime, timezone

    pump = Pump()
    pump.set_speed(150)
    pump.start()
    pump.update_feedback(0)

    events = pump.list_events()
    assert [event["id"] for event in events] == list(range(1, 5))
    assert [event["type"] for event in events] == [
        "speed_set", "pump_started", "feedback_received", "feedback_fault_detected"
    ]
    assert events[-1]["details"]["fault_code"] == "BLOCKED"
    assert all(
        datetime.fromisoformat(event["timestamp_utc"].replace("Z", "+00:00")).tzinfo
        == timezone.utc
        for event in events
    )


def test_event_log_returns_recent_items_as_copies():
    """Reading an event must not expose mutable internal log entries."""
    pump = Pump()
    pump.set_speed(100)
    pump.start()
    pump.stop()

    recent = pump.list_events(limit=2)
    assert [entry["type"] for entry in recent] == ["pump_started", "pump_stopped"]
    recent[0]["details"]["commanded_rpm"] = -999

    assert pump.list_events(limit=2)[0]["details"]["commanded_rpm"] == 100
    assert pump.event_count == 3


@pytest.mark.parametrize("limit", [0, 1001, True, 1.5, "10"])
def test_event_log_rejects_invalid_limits(limit):
    """Only integer limits from 1 through 1000 are allowed."""
    with pytest.raises(ValueError, match="Event limit must be"):
        Pump().list_events(limit)


def test_rejected_start_is_logged():
    """Rejected commands remain visible in the diagnostic event history."""
    pump = Pump()

    with pytest.raises(RuntimeError):
        pump.start()

    event = pump.list_events()[-1]
    assert event["type"] == "start_rejected"
    assert event["details"]["reason"] == "Set pump speed first"


def test_repeated_fault_injection_only_logs_state_changes():
    """Repeated fault requests do not create duplicate state-transition logs."""
    pump = Pump()
    pump.fail_motor()
    pump.fail_motor()
    pump.reset_motor_fault()
    pump.reset_motor_fault()

    assert [entry["type"] for entry in pump.list_events()] == [
        "motor_failed", "motor_fault_reset"
    ]


def test_stopping_after_feedback_fault_preserves_diagnostic_reading():
    """A later stop command must not erase the fault-triggering measurement."""
    pump = Pump()
    pump.set_speed(150)
    pump.start()
    pump.update_feedback(300)

    pump.stop()

    assert pump.feedback_fault_code == "OVERSPEED"
    assert pump.measured_rpm == 300.0
    assert pump.running is False


def test_motor_fault_does_not_erase_latched_feedback_reading():
    """Independent motor failure preserves a previously latched RPM reading."""
    pump = Pump()
    pump.set_speed(150)
    pump.start()
    pump.update_feedback(100)

    pump.fail_motor()

    assert pump.feedback_fault_code == "UNDERSPEED"
    assert pump.measured_rpm == 100.0
    assert pump.motor_fault_active is True
