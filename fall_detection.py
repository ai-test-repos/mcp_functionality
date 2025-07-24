"""A simple script to simulate the behavior of the fall detection service endpoint - sending a message that fall has happened to the receiver"""

from fastapi import FastAPI

app = FastAPI(title = "Fall Detection Service")

@app.post("/detect_fall")
async def detect_fall():
    return {"status": "Fall Happened"}
