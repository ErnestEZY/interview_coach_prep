from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import HTMLResponse
from .controllers.auth_routes import router as auth_router
from .controllers.resume_routes import router as resume_router
from .controllers.interview_routes import router as interview_router
from .controllers.admin_routes import router as admin_router
from .controllers.job_routes import router as job_router
from .services.rag_engine import rag_engine
from .services.utils import get_malaysia_time
from .core.db import interviews, pending_users, client
import os

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(interview_router)
app.include_router(admin_router)
app.include_router(job_router)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

@app.on_event("startup")
async def startup():
    # Check DB Connection
    try:
        await client.admin.command('ping')
        print("Successfully connected to MongoDB")
    except Exception as e:
        print(f"CRITICAL: Failed to connect to MongoDB: {e}")

    # Create TTL index for pending_users (expires after 15 minutes)
    try:
        await pending_users.create_index("created_at", expireAfterSeconds=900)
    except Exception as e:
        print(f"Error creating TTL index for pending_users: {e}")

    # Initialize RAG Engine during startup
    rag_engine.initialize()
    try:
        await interviews.update_many({"ended_at": None}, {"$set": {"ended_at": get_malaysia_time()}})
    except Exception:
        pass
    app.state.startup_id = str(get_malaysia_time().timestamp())

@app.get("/api/meta/startup_id")
async def startup_id():
    return {"startup_id": getattr(app.state, "startup_id", "")}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# Catch-all to serve index.html for any unknown routes (SPA support)
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, full_path: str):
    if not full_path:
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    
    if full_path.startswith("api/"):
        return Response(status_code=404)
        
    try:
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("index.html not found", status_code=404)
