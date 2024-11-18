@echo off
echo Starting Ollama GUI with Memory Management...

:: Activate virtual environment
call venv\Scripts\activate

:: Enhanced Ollama check with retry mechanism
echo Checking Ollama connection...
:RETRY
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo Waiting for Ollama to start...
    timeout /t 2 >nul
    goto RETRY
)
echo Ollama connection confirmed!

:: Start the FastAPI server with hot reload
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir . --log-level info

pause
