"""HTTP API for controlling the simulated laboratory pump.

The application uses one in-memory Pump instance per FastAPI application.
Calling create_app() allows tests to start with a fresh pump state.
"""

from fastapi import FastAPI, HTTPException

from pump import Pump


def create_app() -> FastAPI:
    """Create a pump API with an independent simulated pump instance."""
    app = FastAPI(title="Virtual Pump API")
    pump = Pump()

    @app.get("/status")
    def get_status():
        """Return the pump configuration, operating state, and active faults."""
        return {
            "speed": pump.speed,
            "running": pump.running,
            "sensor_connected": pump.sensor_connected,
            "motor_fault_active": pump.motor_fault_active,
        }

    @app.post("/speed/{rpm}")
    def set_speed(rpm: int):
        """Set speed in RPM, or return HTTP 400 for an unsupported value."""
        try:
            pump.set_speed(rpm)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"speed": pump.speed}

    @app.post("/start")
    def start():
        """Start the pump, or return HTTP 409 if prerequisites are unmet."""
        try:
            pump.start()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"running": pump.running}

    @app.post("/stop")
    def stop():
        """Stop the pump; repeated stop requests are safe."""
        pump.stop()
        return {"running": pump.running}

    @app.post("/simulation/sensor/disconnect")
    def disconnect_sensor():
        """Simulate a sensor failure that immediately stops the pump.

        This is a fault-injection endpoint for the virtual simulator only.
        """
        pump.disconnect_sensor()
        return {"sensor_connected": pump.sensor_connected, "running": pump.running}

    @app.post("/simulation/sensor/reconnect")
    def reconnect_sensor():
        """Restore the simulated sensor without restarting the pump."""
        pump.reconnect_sensor()
        return {"sensor_connected": pump.sensor_connected, "running": pump.running}

    @app.post("/simulation/motor/fail")
    def fail_motor():
        """Inject a simulated motor failure and stop the pump immediately."""
        pump.fail_motor()
        return {"motor_fault_active": pump.motor_fault_active, "running": pump.running}

    @app.post("/simulation/motor/reset")
    def reset_motor_fault():
        """Clear the motor failure without automatically starting the pump."""
        pump.reset_motor_fault()
        return {"motor_fault_active": pump.motor_fault_active, "running": pump.running}

    return app


# ASGI entry point for: uvicorn api:app --reload
app = create_app()
