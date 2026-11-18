"""In-memory model of a laboratory pump and its simulated failure states.

The class models commanded speed, running state, a sensor connection, and a
motor fault. It is a software simulator, not a physical hardware driver.
"""


class Pump:
    """Control a simulated pump while enforcing simple safety interlocks."""

    def __init__(self):
        """Create a stopped pump without any active faults."""
        self.speed = 0
        self.running = False
        self.sensor_connected = True
        self.motor_fault_active = False

    def set_speed(self, rpm):
        """Set a speed between 1 and 300 RPM, inclusive.

        Raises:
            ValueError: If ``rpm`` is outside the supported range.
        """
        if not 1 <= rpm <= 300:
            raise ValueError("Speed must be between 1 and 300 RPM")
        self.speed = rpm

    def start(self):
        """Start the pump only when it is configured and fault-free.

        Raises:
            RuntimeError: If a sensor or motor fault is active, or if speed
                has not been configured.
        """
        if not self.sensor_connected:
            raise RuntimeError("Sensor disconnected")
        if self.motor_fault_active:
            raise RuntimeError("Motor fault active")
        if self.speed == 0:
            raise RuntimeError("Set pump speed first")
        self.running = True

    def stop(self):
        """Stop the pump without resetting faults or the speed setting."""
        self.running = False

    def disconnect_sensor(self):
        """Inject a sensor-disconnection fault and stop the pump safely."""
        self.sensor_connected = False
        self.running = False

    def reconnect_sensor(self):
        """Clear the sensor fault without automatically starting the pump."""
        self.sensor_connected = True

    def fail_motor(self):
        """Inject a motor fault and immediately put the pump in a stopped state."""
        self.motor_fault_active = True
        self.running = False

    def reset_motor_fault(self):
        """Clear the simulated motor fault; a new start command is required."""
        # Clearing an alarm alone must never resume an actuator automatically.
        self.motor_fault_active = False
