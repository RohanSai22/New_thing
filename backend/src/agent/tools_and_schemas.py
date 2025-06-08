from typing import List, Dict
from pydantic import BaseModel, Field
from e2b import Sandbox


class SearchQueryList(BaseModel):
    query: List[str] = Field(
        description="A list of search queries to be used for web research."
    )
    rationale: str = Field(
        description="A brief explanation of why these queries are relevant to the research topic."
    )


class Reflection(BaseModel):
    is_sufficient: bool = Field(
        description="Whether the provided summaries are sufficient to answer the user's question."
    )
    knowledge_gap: str = Field(
        description="A description of what information is missing or needs clarification."
    )
    follow_up_queries: List[str] = Field(
        description="A list of follow-up queries to address the knowledge gap."
    )
    files_to_write: List[Dict[str, str]] = Field(default_factory=list, description="A list of dictionaries, where each dictionary must have 'filename' and 'code' keys for files to be written to the sandbox. E.g., [{'filename': 'main.py', 'code': 'print(\"hello\")'}]")
    command_to_run: str = Field(default="", description="The shell command to execute the written files, e.g., 'python main.py'. This should be an empty string if no command needs to be run.")


class CodeSandboxInput(BaseModel):
    files: List[Dict[str, str]] = Field(description="A list of dictionaries, where each dictionary must have 'filename' and 'code' keys, e.g., [{'filename': 'main.py', 'code': 'print(\"hello\")'}]")
    command: str = Field(description="The shell command to execute in the sandbox, e.g., 'python main.py'")


def code_sandbox(inputs: CodeSandboxInput) -> dict:
    # Ensure E2B_API_KEY is available, though direct os.getenv here might be redundant
    # if handled globally or by the e2b_sdk itself.
    # Consider adding a check or relying on E2B SDK's error handling for missing key.

    sandbox = None  # Initialize sandbox to None
    try:
        sandbox = Sandbox(template="base") # Assumes E2B_API_KEY is in env

        # Create directories if they don't exist
        for file_info in inputs.files:
            filename = file_info["filename"]
            if "/" in filename:
                directory_path = "/".join(filename.split("/")[:-1])
                sandbox.filesystem.make_dir(directory_path)

        # Write files to the sandbox
        for file_info in inputs.files:
            sandbox.filesystem.write(file_info["filename"], file_info["code"])

        # Execute the command
        process = sandbox.process.start_and_wait(cmd=inputs.command)

        return {"stdout": process.stdout, "stderr": process.stderr}

    except Exception as e:
        # Catch any exception during sandbox operation
        return {"error": f"Sandbox execution failed: {str(e)}"}
    finally:
        if sandbox:
            sandbox.close()
