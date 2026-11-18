
class Pump:
    def __init__(self):
        self.speed = 0
        self.running = False
        self.sensor_connected = True

    def set_speed(self, rpm):
        if not 1 <= rpm <= 300:
            raise ValueError("Speed must be between 1 and 300 RPM")
        self.speed = rpm

    def start(self):
        if not self.sensor_connected:
            raise RuntimeError("Sensor disconnected")
        if self.speed == 0:
            raise RuntimeError("Set pump speed first")
        self.running = True

    def stop(self):
        self.running = False

    def disconnect_sensor(self):
        self.sensor_connected = False
        self.running = False

    def reconnect_sensor(self):
        self.sensor_connected = True
