# Windows PowerShell Startup Script for ICP Backend
# This script activates the virtual environment and starts the FastAPI server

$VENV_PATH = ".\venv"
$ACTIVATE_PATH = "$VENV_PATH\Scripts\Activate.ps1"

if (Test-Path $ACTIVATE_PATH) {
    echo "Activating virtual environment..."
    # Set execution policy for the current process to allow running the activation script if needed
    # . $ACTIVATE_PATH
    
    echo "Starting Uvicorn Backend on http://127.0.0.1:8001 ..."
    # Use the venv's python directly to avoid activation issues
    & "$VENV_PATH\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
} else {
    echo "Error: Virtual environment not found at $VENV_PATH"
    echo "Please ensure you have created the venv using: python -m venv venv"
}
