"""Deterministic laboratory-pump simulator with fault detection and event history.

The simulator models commanded and reported RPM, fault interlocks, and an
in-memory event log. It does not control physical hardware or reproduce motor
physics. Feedback is supplied explicitly by the caller to test fault scenarios.
"""

from copy import deepcopy
from datetime import datetime, timezone
import math


class Pump:
    """Model a pump's operating state and simulated safety interlocks.

    Feedback values are assumed to be ideal unless test code injects a reading.
    Any detected feedback fault is latched, requiring a manual reset and start.
    """

    MIN_SPEED_RPM = 1
    MAX_SPEED_RPM = 300
    MAX_FEEDBACK_RPM = 1000
    RPM_TOLERANCE = 0.20  # Deviation exceeding 20% triggers a fault.

    def __init__(self):
        """Create a stopped, fault-free pump with an empty event history."""
        self.speed = 0  # Commanded setpoint in RPM; kept for API compatibility.
        self.measured_rpm = 0.0  # Most recent simulated reading, not hardware data.
        self.running = False
        self.sensor_connected = True
        self.motor_fault_active = False
        self.feedback_fault_code = None
        self._events = []

    def _record_event(self, event_type, **details):
        """Append a structured event with a UTC timestamp and sequence ID."""
        self._events.append(
            {
                "id": len(self._events) + 1,
                "timestamp_utc": datetime.now(timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z"),
                "type": event_type,
                "details": details,
            }
        )

    @property
    def event_count(self):
        """Return the number of events recorded since application startup."""
        return len(self._events)

    def list_events(self, limit=100):
        """Return the most recent events in chronological order.

        Returns a deep copy so callers cannot modify the internal event log.

        Raises:
            ValueError: If ``limit`` is outside the 1–1000 range.
        """
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Event limit must be an integer between 1 and 1000")
        return deepcopy(self._events[-limit:])

    def set_speed(self, rpm):
        """Set commanded speed between 1 and 300 RPM, inclusive.

        In this idealized simulator, a healthy running pump follows a new
        setpoint immediately until an explicit feedback reading is injected.

        Raises:
            ValueError: If speed is outside the supported range.
        """
        if type(rpm) is not int or not self.MIN_SPEED_RPM <= rpm <= self.MAX_SPEED_RPM:
            raise ValueError("Speed must be between 1 and 300 RPM")
        self.speed = rpm
        if self.running:
            self.measured_rpm = float(rpm)
        self._record_event("speed_set", commanded_rpm=rpm)

    def _reject_start(self, reason):
        """Record a rejected command before raising an operating error."""
        self._record_event("start_rejected", reason=reason)
        raise RuntimeError(reason)

    def start(self):
        """Start only when a speed is configured and no fault is active.

        Raises:
            RuntimeError: When a sensor, motor, or feedback fault is active,
                or speed has not been configured.
        """
        if not self.sensor_connected:
            self._reject_start("Sensor disconnected")
        if self.motor_fault_active:
            self._reject_start("Motor fault active")
        if self.feedback_fault_code is not None:
            self._reject_start("Feedback fault active")
        if self.speed == 0:
            self._reject_start("Set pump speed first")
        if not self.running:
            self.running = True
            self.measured_rpm = float(self.speed)
            self._record_event("pump_started", commanded_rpm=self.speed)

    def stop(self):
        """Stop without clearing fault alarms or the commanded setpoint."""
        was_running = self.running
        self.running = False
        # Keep a fault-triggering reading available for post-failure inspection.
        if self.feedback_fault_code is None:
            self.measured_rpm = 0.0 if self.sensor_connected else None
        if was_running:
            self._record_event("pump_stopped", reason="command")

    def disconnect_sensor(self):
        """Simulate a lost sensor, stopping the pump and invalidating feedback."""
        if self.sensor_connected:
            self.sensor_connected = False
            self.running = False
            self.measured_rpm = None
            self._record_event("sensor_disconnected")

    def reconnect_sensor(self):
        """Restore connectivity without restarting or clearing other faults."""
        if not self.sensor_connected:
            self.sensor_connected = True
            self.measured_rpm = 0.0
            self._record_event("sensor_reconnected")

    def fail_motor(self):
        """Inject a latched motor fault that forces a safe stop."""
        if not self.motor_fault_active:
            self.motor_fault_active = True
            self.running = False
            if not self.sensor_connected:
                self.measured_rpm = None
            elif self.feedback_fault_code is None:
                self.measured_rpm = 0.0
            self._record_event("motor_failed")

    def reset_motor_fault(self):
        """Clear a motor fault without automatically restarting the pump."""
        if self.motor_fault_active:
            self.motor_fault_active = False
            self._record_event("motor_fault_reset")

    def update_feedback(self, measured_rpm):
        """Inject a simulated RPM reading and evaluate its deviation.

        A zero reading is classified as BLOCKED. Other readings strictly below
        80% of commanded RPM are UNDERSPEED; those strictly above 120% are
        OVERSPEED. Threshold endpoints are accepted. Upon detection, the
        fault is latched and the pump stops, retaining the last reading for
        diagnostic inspection.

        Args:
            measured_rpm: Finite numeric reading from 0 to 1000 RPM.

        Returns:
            A fault code, or None when feedback is within tolerance.

        Raises:
            ValueError: If the reading is invalid.
            RuntimeError: If the pump is not running or sensor is disconnected.
        """
        if (
            isinstance(measured_rpm, bool)
            or not isinstance(measured_rpm, (int, float))
            or not math.isfinite(measured_rpm)
            or not 0 <= measured_rpm <= self.MAX_FEEDBACK_RPM
        ):
            raise ValueError("Measured RPM must be a finite number from 0 to 1000")
        if not self.sensor_connected:
            raise RuntimeError("Sensor disconnected")
        if not self.running:
            raise RuntimeError("Pump is not running")

        reading = float(measured_rpm)
        self.measured_rpm = reading
        self._record_event(
            "feedback_received", commanded_rpm=self.speed, measured_rpm=reading
        )

        fault_code = None
        if reading == 0.0:
            fault_code = "BLOCKED"
        elif reading < self.speed * (1 - self.RPM_TOLERANCE):
            fault_code = "UNDERSPEED"
        elif reading > self.speed * (1 + self.RPM_TOLERANCE):
            fault_code = "OVERSPEED"

        if fault_code is not None:
            self.feedback_fault_code = fault_code
            self.running = False
            self._record_event(
                "feedback_fault_detected",
                fault_code=fault_code,
                commanded_rpm=self.speed,
                measured_rpm=reading,
            )
        return fault_code

    def reset_feedback_fault(self):
        """Clear a feedback alarm but require a separate explicit start."""
        if self.feedback_fault_code is not None:
            previous_code = self.feedback_fault_code
            self.feedback_fault_code = None
            self.measured_rpm = 0.0 if self.sensor_connected else None
            self._record_event("feedback_fault_reset", previous_code=previous_code)
