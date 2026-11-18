
import pytest
from pump import Pump


def test_pump_starts():
    pump = Pump()
    pump.set_speed(150)
    pump.start()

    assert pump.running is True


def test_pump_stops():
    pump = Pump()
    pump.set_speed(150)
    pump.start()
    pump.stop()

    assert pump.running is False


def test_invalid_speed():
    pump = Pump()

    with pytest.raises(ValueError):
        pump.set_speed(500)


def test_cannot_start_without_speed():
    pump = Pump()

    with pytest.raises(RuntimeError):
        pump.start()

@pytest.mark.parametrize("rpm", [1, 100, 150, 300])
def test_valid_speeds(rpm):
    pump = Pump()
    pump.set_speed(rpm)

    assert pump.speed == rpm #run the same function multiple times, with different values.


@pytest.mark.parametrize("rpm", [-10, 0, 301, 500])
def test_invalid_speeds(rpm):
    pump = Pump()

    with pytest.raises(ValueError):
        pump.set_speed(rpm)


def test_invalid_command_preserves_state():
    pump = Pump()
    pump.set_speed(150)
    pump.start()

    with pytest.raises(ValueError):
        pump.set_speed(500)

    assert pump.speed == 150
    assert pump.running is True


def test_sensor_disconnection():
    pump = Pump()
    pump.set_speed(150)
    pump.start()

    pump.disconnect_sensor()

    assert pump.running is False

    with pytest.raises(RuntimeError):
        pump.start()


def test_sensor_recovery():
    pump = Pump()
    pump.set_speed(150)
    pump.start()

    pump.disconnect_sensor()
    pump.reconnect_sensor()
    pump.start()

    assert pump.running is True
