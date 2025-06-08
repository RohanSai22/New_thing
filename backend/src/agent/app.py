# mypy: disable - error - code = "no-untyped-def,misc"
import os # ADDED
from typing import List, Dict, Any # ADDED
import pathlib
from fastapi import FastAPI, Request, Response, HTTPException # ADDED HTTPException
from fastapi.staticfiles import StaticFiles
import fastapi.exceptions
from pydantic import BaseModel # ADDED
import google.generativeai as genai # ADDED
from fastapi.middleware.cors import CORSMiddleware # ADDED


# Define Pydantic Model for MindMapRequest
class MindMapRequest(BaseModel):
    history: List[Dict[str, Any]]


MIND_MAP_PROMPT = """
Convert the following conversation history into a Mermaid.js graph TD (Top-Down) syntax.
The graph should represent the key topics, questions, and answers, showing the flow of the conversation.
Focus on creating a concise yet informative mind map. Nodes should be brief. Edges should show relationships.
Ensure the output is ONLY the Mermaid syntax starting with 'graph TD'. Do not include any other explanatory text or markdown code fences.

Conversation History:
{history_string}

Mermaid Output (MUST start with 'graph TD'):
"""

# Define the FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
        # Add other origins if needed, e.g., your production frontend URL
    ],
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)


def create_frontend_router(build_dir="../frontend/dist"):
    """Creates a router to serve the React frontend.

    Args:
        build_dir: Path to the React build directory relative to this file.

    Returns:
        A Starlette application serving the frontend.
    """
    build_path = pathlib.Path(__file__).parent.parent.parent / build_dir
    static_files_path = build_path / "assets"  # Vite uses 'assets' subdir

    if not build_path.is_dir() or not (build_path / "index.html").is_file():
        print(
            f"WARN: Frontend build directory not found or incomplete at {build_path}. Serving frontend will likely fail."
        )
        # Return a dummy router if build isn't ready
        from starlette.routing import Route

        async def dummy_frontend(request):
            return Response(
                "Frontend not built. Run 'npm run build' in the frontend directory.",
                media_type="text/plain",
                status_code=503,
            )

        return Route("/{path:path}", endpoint=dummy_frontend)

    build_dir = pathlib.Path(build_dir)

    react = FastAPI(openapi_url="")
    react.mount(
        "/assets", StaticFiles(directory=static_files_path), name="static_assets"
    )

    @react.get("/{path:path}")
    async def handle_catch_all(request: Request, path: str):
        fp = build_path / path
        if not fp.exists() or not fp.is_file():
            fp = build_path / "index.html"
        return fastapi.responses.FileResponse(fp)

    return react


# Mount the frontend under /app to not conflict with the LangGraph API routes
app.mount(
    "/app",
    create_frontend_router(),
    name="frontend",
)


@app.post("/mindmap")
async def generate_mind_map_endpoint(request: MindMapRequest):
    # 1. Get API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # print("ERROR: GEMINI_API_KEY not found in environment variables.")
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured on server.")

    # 2. Configure GenAI client
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        # print(f"ERROR: Failed to configure Gemini client - {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to configure Gemini client: {str(e)}")

    try:
        # 3. Format history
        history_parts = []
        for message in request.history:
            speaker = message.get("type", "unknown").capitalize()
            content = str(message.get("content", ""))
            # Truncate long messages to keep the prompt focused
            content_summary = (content[:150] + '...') if len(content) > 150 else content
            history_parts.append(f"{speaker}: {content_summary}")
        history_string = "\n".join(history_parts)

        # 4. Get Model
        reasoning_model_name = os.getenv("REASONING_MODEL", "gemini-1.5-flash-latest")
        model = genai.GenerativeModel(reasoning_model_name)

        # 5. Format Prompt
        prompt = MIND_MAP_PROMPT.format(history_string=history_string)

        # 6. Call Gemini
        response = await model.generate_content_async(prompt)

        # 7. Extract and strip text
        mermaid_string = response.text.strip()

        # 8. Clean the string
        if mermaid_string.startswith("```mermaid"):
            mermaid_string = mermaid_string[len("```mermaid"):].strip()
            if mermaid_string.endswith("```"):
                mermaid_string = mermaid_string[:-len("```")].strip()
        elif mermaid_string.startswith("```"):
            mermaid_string = mermaid_string[len("```"):].strip()
            if mermaid_string.endswith("```"):
                mermaid_string = mermaid_string[:-len("```")].strip()

        # 9. Find "graph TD"
        graph_td_index = mermaid_string.find("graph TD")
        if graph_td_index != -1:
            mermaid_string = mermaid_string[graph_td_index:]
        # else:
            # If "graph TD" is not found, we might have an issue.
            # For now, use the string as is, or potentially raise an error/return a default.
            # print(f"WARN: 'graph TD' not found in Gemini response: {mermaid_string[:100]}")

        # 10. Return
        return {"mermaid_string": mermaid_string}

    except Exception as e:
        error_detail = f"An unexpected error occurred while generating mind map: {str(e)}"
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            error_detail += f" | Prompt Feedback: {str(response.prompt_feedback)}"
        # print(f"ERROR: /mindmap endpoint - {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)
