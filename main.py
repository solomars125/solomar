from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import httpx
import json
from datetime import datetime
from memory_manager import MemoryManager
from typing import Optional
import requests

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize memory manager
memory_manager = MemoryManager()

# Ollama configuration
OLLAMA_BASE_URL = "http://127.0.0.1:11434"

def is_ollama_running():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

def get_models_sync():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [model["name"] for model in models] if models else ["phi"]
            return sorted(model_names)
        return ["phi"]
    except:
        return ["phi"]

@app.get("/")
async def home(request: Request):
    ollama_status = is_ollama_running()
    available_models = get_models_sync() if ollama_status else []
    stats = memory_manager.manage_memory("stats")
    memories = memory_manager.manage_memory("list", limit=10)
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "ollama_status": ollama_status,
            "available_models": available_models,
            "memories": memories,
            "stats": stats
        }
    )

@app.get("/status")
async def get_status():
    ollama_running = is_ollama_running()
    return {"ollama_running": ollama_running}

@app.get("/models")
async def get_models():
    return {"models": get_models_sync()}

@app.post("/chat")
async def chat(message: str = Form(...), model: str = Form(...)):
    if not is_ollama_running():
        return JSONResponse(
            status_code=503,
            content={"response": "Ollama service needs to be started"}
        )
    
    try:
        # Get and analyze relevant memories
        relevant_memories = memory_manager.get_relevant_memories(message, limit=5)
        memory_contents = [mem[0]['content'] for mem in relevant_memories]
        context_summary = ""
        
        if memory_contents:
            # Group and analyze similar responses
            response_groups = {}
            for content in memory_contents:
                key = content.lower().strip()
                response_groups[key] = response_groups.get(key, 0) + 1
            
            if response_groups:
                common_responses = sorted(
                    response_groups.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )
                context_summary = common_responses[0][0]

        # Build enhanced prompt
        enhanced_prompt = f"""Previous relevant context: {context_summary}

Current message: {message}

Instructions: Provide a direct, natural response incorporating relevant context."""

        # Make request to Ollama
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": enhanced_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                }
            )
            
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Store conversation in memory
            memory_manager.process_message(message, "user_input")
            memory_manager.process_message(response_text, "assistant_response")
            
            return {"response": response_text}
            
    except Exception as e:
        print(f"Chat error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"response": "An error occurred while processing your request"}
        )

@app.post("/memories")
async def manage_memories(
    action: str = Form(...),
    query: Optional[str] = Form(None),
    memory_id: Optional[int] = Form(None),
    content: Optional[str] = Form(None)
):
    try:
        if action == "search" and query:
            results = memory_manager.manage_memory("search", query=query)
            return results
            
        elif action == "delete" and memory_id is not None:
            memory_manager.manage_memory("delete", memory_id=memory_id)
            return {"status": "success"}
            
        elif action == "update" and memory_id is not None and content:
            memory_manager.manage_memory("update", memory_id=memory_id, content=content)
            return {"status": "success"}
            
        elif action == "consolidate":
            memory_manager.manage_memory("consolidate")
            return {"status": "success"}
            
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Invalid action"}
        )
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    print("Starting Ollama GUI with Memory Management...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
