
from fastapi import FastAPI, HTTPException
from pump import Pump

def create_app():
    app = FastAPI()
    pump = Pump()

    @app.get("/status")
    def get_status():
        return {
            "speed": pump.speed,
            "running": pump.running,
            "sensor_connected": pump.sensor_connected
        }

    @app.post("/speed/{rpm}")
    def set_speed(rpm: int):
        try:
            pump.set_speed(rpm)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"speed": pump.speed}

    @app.post("/start")
    def start():
        try:
            pump.start()
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return {"running": pump.running}

    return app

app = create_app()
