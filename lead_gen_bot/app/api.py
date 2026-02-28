from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os

from main import LeadGeneratorEngine
from mailer import ZoraMailer
from responder import ZoraIMAPListener
from social_outreach import ZoraSocialEngine

app = FastAPI(title="Zora Engine", description="Omni-channel Lead Generation & Mass Mailer", version="1.0.0")

# Setup templates and static files (Dashboard)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(BASE_DIR, "templates")
static_dir = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=templates_dir)
# Ensure static folder exists
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Global state for background tasks
campaign_status = {
    "is_running": False,
    "leads_found": 0,
    "target": 0,
    "emails_sent": 0,
    "current_domain": ""
}

social_campaign_status = {
    "is_running": False,
    "reddit_posts_success": [],
    "reddit_posts_failed": [],
    "twitter_thread_url": "",
    "linkedin_messages_sent": 0
}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Returns the main Zora Dashboard.
    """
    return templates.TemplateResponse("dashboard.html", {"request": request, "status": campaign_status})

@app.get("/api/status")
async def get_status():
    """
    API endpoint for the frontend to poll campaign status.
    """
    return campaign_status

def run_campaign_task(industry, country, job_title, target):
    """
    Background worker that runs the massive lead generation and hand-offs to mailer.
    """
    global campaign_status
    campaign_status["is_running"] = True
    campaign_status["target"] = target
    campaign_status["leads_found"] = 0

    # 1. Start Lead Generation (Omni-channel)
    engine = LeadGeneratorEngine(target_count=target)

    # We patch the engine to update our global state as it finds leads
    original_save = engine._save_chunk
    def patched_save(chunk):
        original_save(chunk)
        campaign_status["leads_found"] += len(chunk)
    engine._save_chunk = patched_save

    # Run the heavy asyncio loop in a new event loop for this thread
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            engine.generate_leads(
                industry=industry,
                country=country,
                job_title=job_title,
                employee_range="Any",
                revenue_range="Any"
            )
        )
    except Exception as e:
        print(f"Campaign Engine Error: {e}")
    finally:
        campaign_status["is_running"] = False
        loop.close()

@app.post("/api/start")
async def start_campaign(background_tasks: BackgroundTasks, payload: dict):
    """
    Starts a new Zora lead gen & mailing campaign in the background.
    """
    if campaign_status["is_running"]:
        return {"error": "A campaign is already running."}

    industry = payload.get("industry", "Software")
    country = payload.get("country", "United States")
    job_title = payload.get("job_title", "CTO")
    target = int(payload.get("target", 100000))

    background_tasks.add_task(run_campaign_task, industry, country, job_title, target)
    return {"message": "Zora Engine Started!"}

def run_social_task(credentials, platforms, content):
    """
    Background worker that executes the massive social media outreach engine.
    """
    global social_campaign_status
    social_campaign_status["is_running"] = True
    social_campaign_status["reddit_posts_success"] = []
    social_campaign_status["reddit_posts_failed"] = []
    social_campaign_status["twitter_thread_url"] = ""
    social_campaign_status["linkedin_messages_sent"] = 0

    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        engine = ZoraSocialEngine(credentials)

        # Concurrently execute selected platforms
        tasks = []
        if "reddit" in platforms:
            tasks.append(engine.post_to_reddit(content.get("subreddits", ["startups"]), content["reddit_title"], content["reddit_body"]))
        if "twitter" in platforms:
            tasks.append(engine.post_to_twitter(content["twitter_text"]))
        if "linkedin" in platforms:
            tasks.append(engine.message_linkedin_connections(content["linkedin_message"]))

        results = loop.run_until_complete(asyncio.gather(*tasks))

        # Update status based on results
        # (This is a simplified aggregation for the dashboard)
        for r in results:
            if isinstance(r, dict):
                if "success" in r and isinstance(r["success"], list):
                    social_campaign_status["reddit_posts_success"] = r["success"]
                    social_campaign_status["reddit_posts_failed"] = r.get("failed", [])
                elif "url" in r or "urls" in r:
                    social_campaign_status["twitter_thread_url"] = r.get("url", "Thread Posted")
                elif "success" in r and isinstance(r["success"], int):
                    social_campaign_status["linkedin_messages_sent"] = r["success"]

    except Exception as e:
        print(f"Social Engine Error: {e}")
    finally:
        social_campaign_status["is_running"] = False
        loop.close()

@app.post("/api/social/start")
async def start_social_campaign(background_tasks: BackgroundTasks, payload: dict):
    """
    Starts the Zora Social Media Outreach engine.
    Expected payload format matches ZoraSocialEngine credentials + content configuration.
    """
    if social_campaign_status["is_running"]:
        return {"error": "A social campaign is already running."}

    credentials = payload.get("credentials", {})
    platforms = payload.get("platforms", [])
    content = payload.get("content", {})

    background_tasks.add_task(run_social_task, credentials, platforms, content)
    return {"message": "Zora Social Engine Started!"}

@app.get("/api/social/status")
async def get_social_status():
    """
    API endpoint for the frontend to poll social campaign status.
    """
    return social_campaign_status

if __name__ == "__main__":
    # Start the Zora backend server
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
