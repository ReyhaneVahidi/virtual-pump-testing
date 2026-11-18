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
        """Return the current pump speed, running state, and sensor status."""
        return {
            "speed": pump.speed,
            "running": pump.running,
            "sensor_connected": pump.sensor_connected,
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

    return app


# ASGI entry point for: uvicorn api:app --reload
app = create_app()
