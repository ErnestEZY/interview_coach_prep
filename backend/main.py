from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import HTMLResponse, FileResponse
from .controllers.auth_routes import router as auth_router
from .controllers.resume_routes import router as resume_router
from .controllers.interview_routes import router as interview_router
from .controllers.admin_routes import router as admin_router
from .controllers.job_routes import router as job_router
from .services.rag_engine import rag_engine
from .services.utils import get_malaysia_time
from .core.db import interviews, pending_users, reset_tokens, client
import os
import logging

# Suppress noisy httpx logging
logging.getLogger("httpx").setLevel(logging.WARNING)

# Helper to get the real client IP behind Nginx/Proxy
def get_real_ip(request: Request):
    # Check for standard proxy headers (X-Forwarded-For)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # The first IP in the list is the original client
        return forwarded.split(",")[0].strip()
    
    # Check for X-Real-IP (another common proxy header)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
        
    # Fallback to direct connection IP (for local dev without Nginx)
    # This ensures it works even if you run `uvicorn` directly
    return request.client.host if request.client else "127.0.0.1"

limiter = Limiter(key_func=get_real_ip)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

@app.middleware("http")
async def log_origins(request: Request, call_next):
    origin = request.headers.get("Origin")
    if origin and "tauri" in origin.lower():
        print(f"[AUTH DEBUG] Incoming Tauri request from origin: {origin}")
        print(f"  - Path: {request.url.path}")
        print(f"  - Method: {request.method}")
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    # In production, we should list the exact frontend domains
    # But for now, we use a wildcard but enable credentials carefully
    allow_origins=[
        "http://localhost",
        "http://localhost:8000",
        "https://interview-coach-prep.onrender.com",
        "https://fyp-frontend.onrender.com",
        "https://*.onrender.com",
        "tauri://localhost",
        "https://tauri.localhost",
        "http://tauri.localhost",
        "tauri://com.icp.dev",
        "https://tauri.com.icp.dev",
        "tauri://*",
        "https://tauri.*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(interview_router)
app.include_router(admin_router)
app.include_router(job_router)

# --- App Download Routes ---
@app.get("/downloads/apk/app-release.apk")
async def download_apk():
    possible_paths = [
        os.path.join(os.getcwd(), "apps", "apk", "app-release.apk"),
        os.path.join(os.getcwd(), "mobile_app", "android", "app", "build", "outputs", "flutter-apk", "app-release.apk"),
        os.path.join(os.getcwd(), "mobile_app", "build", "app", "outputs", "flutter-apk", "app-release.apk"),
    ]
    for apk_path in possible_paths:
        apk_path = os.path.abspath(apk_path)
        if os.path.exists(apk_path):
            return FileResponse(apk_path, filename="icp-android.apk", media_type="application/vnd.android.package-archive")
    return Response(content="APK file not found on server", status_code=404)

@app.get("/downloads/msi/installer")
async def download_msi():
    possible_paths = [
        os.path.join(os.getcwd(), "apps", "msi", "Interview Coach Prep_0.1.0_x64_en-US.msi"),
        os.path.join(os.getcwd(), "apps", "msi", "Interview_Coach_Prep_0.1.0_x64_en-US.msi"),
        os.path.join(os.getcwd(), "src-tauri", "target", "release", "bundle", "msi", "Interview Coach Prep_0.1.0_x64_en-US.msi"),
        os.path.join(os.getcwd(), "src-tauri", "target", "release", "bundle", "msi", "Interview_Coach_Prep_0.1.0_x64_en-US.msi"),
    ]
    for msi_path in possible_paths:
        msi_path = os.path.abspath(msi_path)
        if os.path.exists(msi_path):
            return FileResponse(msi_path, filename="Interview_Coach_Prep_0.1.0_x64.msi", media_type="application/x-msi")
    return Response(content="MSI installer not found on server", status_code=404)

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

    # Create TTL index for reset_tokens (expires at the specific time in expires_at)
    try:
        await reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    except Exception as e:
        print(f"Error creating TTL index for reset_tokens: {e}")

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

# Catch-all to serve the appropriate HTML file for any unknown routes
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, full_path: str):
    # Construct the full path to the requested file
    file_path = os.path.join("frontend", full_path)

    # If the requested path points to an existing file, serve it with proper MIME type
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # Otherwise, serve the main index.html for SPA routing
    index_path = os.path.join("frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    return HTMLResponse("Not Found", status_code=404)
