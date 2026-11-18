"""FastAPI endpoints for a virtual pump and its fault-injection scenarios.

Each application instance owns one in-memory Pump. Factory-created instances
keep tests isolated; a server restart resets the simulated state and events.
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from pump import Pump


class FeedbackInput(BaseModel):
    """Validate an explicitly simulated RPM feedback measurement."""

    measured_rpm: float = Field(ge=0, le=1000, allow_inf_nan=False)


def create_app() -> FastAPI:
    """Create the API with an independent pump instance for each app."""
    app = FastAPI(
        title="Virtual Laboratory Pump API",
        description="Software-only pump control, fault injection and test logging.",
        version="1.0.0",
    )
    pump = Pump()

    @app.get("/status")
    def get_status():
        """Return current commanded speed, last feedback and fault states."""
        return {
            "speed": pump.speed,
            "measured_rpm": pump.measured_rpm,
            "running": pump.running,
            "sensor_connected": pump.sensor_connected,
            "motor_fault_active": pump.motor_fault_active,
            "feedback_fault_code": pump.feedback_fault_code,
        }

    @app.post("/speed/{rpm}")
    def set_speed(rpm: int):
        """Set commanded RPM; reject out-of-range values with HTTP 400."""
        try:
            pump.set_speed(rpm)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"speed": pump.speed}

    @app.post("/start")
    def start():
        """Start the virtual pump unless a safety interlock prevents it."""
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
        """Simulate a disconnected feedback sensor and stop operation."""
        pump.disconnect_sensor()
        return {"sensor_connected": pump.sensor_connected, "running": pump.running}

    @app.post("/simulation/sensor/reconnect")
    def reconnect_sensor():
        """Re-establish the sensor without restarting the pump."""
        pump.reconnect_sensor()
        return {"sensor_connected": pump.sensor_connected, "running": pump.running}

    @app.post("/simulation/motor/fail")
    def fail_motor():
        """Inject a latched motor fault and force a stop."""
        pump.fail_motor()
        return {"motor_fault_active": pump.motor_fault_active, "running": pump.running}

    @app.post("/simulation/motor/reset")
    def reset_motor_fault():
        """Reset the motor fault without restarting the pump."""
        pump.reset_motor_fault()
        return {"motor_fault_active": pump.motor_fault_active, "running": pump.running}

    @app.post("/simulation/feedback")
    def simulate_feedback(payload: FeedbackInput):
        """Evaluate a simulated measurement and latch any detected fault."""
        try:
            fault_code = pump.update_feedback(payload.measured_rpm)
        except (ValueError, RuntimeError) as exc:
            status_code = 400 if isinstance(exc, ValueError) else 409
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        return {
            "measured_rpm": pump.measured_rpm,
            "fault_code": fault_code,
            "running": pump.running,
        }

    @app.post("/simulation/feedback/reset")
    def reset_feedback_fault():
        """Clear a detected RPM fault; an explicit start is still required."""
        pump.reset_feedback_fault()
        return {"feedback_fault_code": pump.feedback_fault_code, "running": pump.running}

    @app.get("/events")
    def get_events(limit: int = Query(default=100, ge=1, le=1000)):
        """Read recent timestamped events, oldest first within the limit."""
        return {"events": pump.list_events(limit=limit), "total": pump.event_count}

    return app


# ASGI entry point: python -m uvicorn api:app --reload
app = create_app()
