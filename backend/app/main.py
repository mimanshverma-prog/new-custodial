from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from backend.app.routes_contacts import router as contacts_router
from backend.app.routes_campaigns import router as campaigns_router
from backend.app.routes_tracking import router as tracking_router
from backend.app.models import init_db

app = FastAPI(title="Bulk Email Server")

templates = Jinja2Templates(directory="backend/templates")

# Initialize Database
init_db()

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

app.include_router(contacts_router)
app.include_router(campaigns_router)
app.include_router(tracking_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
