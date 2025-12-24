import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import time  # Import time module
import os

# Initialize FastAPI
app = FastAPI()

# SETUP TEMPLATES
templates = Jinja2Templates(directory="templates")

# --- NEW: Record when the server started ---
SERVER_START_TIME = time.time()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    return {"status": "online", "service": "fb_data_manager"}

# --- NEW: Endpoint to provide server start time ---
@app.get("/api/stats")
async def get_stats():
    return {"start_time": SERVER_START_TIME}

async def start_web_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=10000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()