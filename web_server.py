import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

# Initialize FastAPI
app = FastAPI()

# Setup Templates directory (make sure you have a folder named 'templates')
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Renders the main dashboard HTML.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """
    Simple health endpoint for external pingers (like UptimeRobot).
    """
    return {"status": "online", "service": "fb_data_manager"}

async def start_web_server():
    """
    Starts the Uvicorn server programmatically.
    This allows it to run inside the same asyncio loop as the bot.
    """
    config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=10000, 
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()