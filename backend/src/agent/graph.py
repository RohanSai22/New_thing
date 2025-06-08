import os
from typing import Union, List # ADDED/MODIFIED

from agent.tools_and_schemas import SearchQueryList, Reflection, code_sandbox, CodeSandboxInput # ADDED
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_core.runnables import RunnableConfig
from google.genai import Client

from agent.state import (
    OverallState,
    QueryGenerationState,
    ReflectionState,
    WebSearchState,
)
from agent.configuration import Configuration
from agent.prompts import (
    get_current_date,
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from agent.utils import (
    get_citations,
    get_research_topic,
    insert_citation_markers,
    resolve_urls,
)

load_dotenv()

if os.getenv("GEMINI_API_KEY") is None:
    raise ValueError("GEMINI_API_KEY is not set")

# Used for Google Search API
genai_client = Client(api_key=os.getenv("GEMINI_API_KEY"))


# Nodes
def generate_query(state: OverallState, config: RunnableConfig) -> QueryGenerationState:
    """LangGraph node that generates a search queries based on the User's question.

    Uses Gemini 2.0 Flash to create an optimized search query for web research based on
    the User's question.

    Args:
        state: Current graph state containing the User's question
        config: Configuration for the runnable, including LLM provider settings

    Returns:
        Dictionary with state update, including search_query key containing the generated query
    """
    configurable = Configuration.from_runnable_config(config)

    # check for custom initial search query count
    if state.get("initial_search_query_count") is None:
        state["initial_search_query_count"] = configurable.number_of_initial_queries

    # init Gemini 2.0 Flash
    llm = ChatGoogleGenerativeAI(
        model=configurable.query_generator_model,
        temperature=1.0,
        max_retries=2,
        api_key=os.getenv("GEMINI_API_KEY"),
    )
    structured_llm = llm.with_structured_output(SearchQueryList)

    # Format the prompt
    current_date = get_current_date()
    formatted_prompt = query_writer_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        number_queries=state["initial_search_query_count"],
    )
    # Generate the search queries
    yield {"generate_query": {"type": "status", "data": f"Generating {state['initial_search_query_count']} initial search queries..."}}
    result = structured_llm.invoke(formatted_prompt)
    yield {"query_list": result.query}


def continue_to_web_research(state: QueryGenerationState):
    """LangGraph node that sends the search queries to the web research node.

    This is used to spawn n number of web research nodes, one for each search query.
    """
    return [
        Send("web_research", {"search_query": search_query, "id": int(idx)})
        for idx, search_query in enumerate(state["query_list"])
    ]


def web_research(state: WebSearchState, config: RunnableConfig) -> OverallState:
    """LangGraph node that performs web research using the native Google Search API tool.

    Executes a web search using the native Google Search API tool in combination with Gemini 2.0 Flash.

    Args:
        state: Current graph state containing the search query and research loop count
        config: Configuration for the runnable, including search API settings

    Returns:
        Dictionary with state update, including sources_gathered, research_loop_count, and web_research_results
    """
    # Configure
    configurable = Configuration.from_runnable_config(config)
    formatted_prompt = web_searcher_instructions.format(
        current_date=get_current_date(),
        research_topic=state["search_query"],
    )

    # Uses the google genai client as the langchain client doesn't return grounding metadata
    response = genai_client.models.generate_content(
        model=configurable.query_generator_model,
        contents=formatted_prompt,
        config={
            "tools": [{"google_search": {}}],
            "temperature": 0,
        },
    )
    # resolve the urls to short urls for saving tokens and time
    resolved_urls = resolve_urls(
        response.candidates[0].grounding_metadata.grounding_chunks, state["id"]
    )
    # Gets the citations and adds them to the generated text
    yield {"web_research": {"type": "status", "data": f"Searching web for: {state['search_query']}"}}
    citations = get_citations(response, resolved_urls)
    modified_text = insert_citation_markers(response.text, citations)
    sources_gathered = [item for citation in citations for item in citation["segments"]]

    # Prepare source data for yielding (url and title)
    # resolved_urls is a list of dicts like {'url': short_url, 'value': original_url, 'label': label}
    # We need to extract the original URL and a title (if available, use label or part of URL)
    source_event_data = []
    if response.candidates[0].grounding_metadata.grounding_chunks:
        for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
            if chunk.web_uri:
                 # Find the original URL from resolved_urls if possible, otherwise use web_uri
                original_url = next((res_url['value'] for res_url in resolved_urls if res_url['label'] == chunk.id), chunk.web_uri)
                source_event_data.append({"url": original_url, "title": chunk.title if chunk.title else original_url})

    if source_event_data:
        yield {"web_research": {"type": "sources", "data": source_event_data}}
    else:
        yield {"web_research": {"type": "status", "data": "No direct sources found for this query."}}


    yield {
        "sources_gathered": sources_gathered, # This contains more detailed segment info for citations
        "search_query": [state["search_query"]],
        "web_research_result": [modified_text],
    }


def reflection(state: OverallState, config: RunnableConfig) -> ReflectionState:
    """LangGraph node that identifies knowledge gaps and generates potential follow-up queries.

    Analyzes the current summary to identify areas for further research and generates
    potential follow-up queries. Uses structured output to extract
    the follow-up query in JSON format.

    Args:
        state: Current graph state containing the running summary and research topic
        config: Configuration for the runnable, including LLM provider settings

    Returns:
        Dictionary with state update, including search_query key containing the generated follow-up query
    """
    configurable = Configuration.from_runnable_config(config)
    # Increment the research loop count and get the reasoning model
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    reasoning_model = state.get("reasoning_model") or configurable.reasoning_model

    # Format the prompt
    current_date = get_current_date()
    effort_level = state.get("effort", "medium") # Get effort from state, default if necessary
    formatted_prompt = reflection_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n\n---\n\n".join(state.get("web_research_result", [])), # Use .get for safety
        effort=effort_level, # Add effort here
    )
    # init Reasoning Model
    llm = ChatGoogleGenerativeAI(
        model=reasoning_model,
        temperature=1.0,
        max_retries=2,
        api_key=os.getenv("GEMINI_API_KEY"),
    )
    yield {"reflection": {"type": "status", "data": "Reflecting on research and planning next steps..."}}
    result = llm.with_structured_output(Reflection).invoke(formatted_prompt)

    plan_details = []
    if result.follow_up_queries:
        plan_details.append(f"Plan: Generate follow-up searches: {', '.join(result.follow_up_queries)}")
    if result.files_to_write and result.command_to_run:
        plan_details.append(f"Plan: Execute code: {result.command_to_run} with {len(result.files_to_write)} file(s).")
    if not plan_details and result.is_sufficient:
        plan_details.append("Plan: Information is sufficient. Finalizing answer.")
    elif not plan_details:
        plan_details.append("Plan: No further actions identified, but information might not be sufficient. Will attempt to finalize.")

    yield {"reflection": {"type": "plan", "data": "\n".join(plan_details)}}

    yield {
        "is_sufficient": result.is_sufficient,
        "knowledge_gap": result.knowledge_gap,
        "follow_up_queries": result.follow_up_queries,
        "files_to_write": result.files_to_write,
        "command_to_run": result.command_to_run,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
    }


def evaluate_research(state: OverallState, config: RunnableConfig) -> Union[str, List[Send]]:
    configurable = Configuration.from_runnable_config(config)
    max_research_loops = (
        state.get("max_research_loops")
        if state.get("max_research_loops") is not None
        else configurable.max_research_loops
    )

    # Get relevant data from the OverallState
    files_to_write = state.get("files_to_write")
    command_to_run = state.get("command_to_run")
    is_sufficient = state.get("is_sufficient", False) # Default to False
    follow_up_queries = state.get("follow_up_queries", [])
    research_loop_count = state.get("research_loop_count", 0)
    # 'number_of_ran_queries' is populated by the reflection node
    number_of_ran_queries = state.get("number_of_ran_queries", 0)


    if files_to_write and command_to_run:
        # If code execution is planned, this branch is taken.
        # Consider clearing follow_up_queries if strict mutual exclusivity is desired here,
        # though the reflection prompt aims for that.
        # state["follow_up_queries"] = [] # Optional: if state was mutable and we wanted to clear other paths
        return "code_execution"

    if is_sufficient or research_loop_count >= max_research_loops:
        return "finalize_answer"

    if follow_up_queries:
        # If follow-up searches are planned.
        # Consider clearing code execution fields if strict mutual exclusivity is desired here.
        # state["files_to_write"] = [] # Optional
        # state["command_to_run"] = "" # Optional
        sends = [
            Send(
                "web_research",
                {
                    "search_query": follow_up_query,
                    # Ensure 'number_of_ran_queries' is correctly passed and updated through state
                    "id": number_of_ran_queries + int(idx),
                },
            )
            for idx, follow_up_query in enumerate(follow_up_queries)
        ]
        if sends: # If there are actual queries to send
            return sends
        else: # Should not be reached if follow_up_queries is not empty
            return "finalize_answer"

    # Default case: if not sufficient, no code, no searches, but loop limit not hit (e.g., reflection error)
    return "finalize_answer"


def finalize_answer(state: OverallState, config: RunnableConfig):
    """LangGraph node that finalizes the research summary.

    Prepares the final output by deduplicating and formatting sources, then
    combining them with the running summary to create a well-structured
    research report with proper citations.

    Args:
        state: Current graph state containing the running summary and sources gathered

    Returns:
        Dictionary with state update, including running_summary key containing the formatted final summary with sources
    """
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.reasoning_model

    # Format the prompt
    current_date = get_current_date()
    research_topic = get_research_topic(state["messages"])
    # summaries = state.get("web_research_result", []) # Old line

    code_output_list = state.get("code_execution_output", []) # This is a list of dicts

    additional_context_parts = []
    if code_output_list: # Check if list is not empty
        for item_dict in code_output_list: # Each item should be a dict
            if isinstance(item_dict, dict):
                if item_dict.get("stdout"):
                    additional_context_parts.append(f"Code Execution Output (stdout):\n```\n{item_dict['stdout']}\n```")
                if item_dict.get("stderr"):
                    additional_context_parts.append(f"Code Execution Output (stderr):\n```\n{item_dict['stderr']}\n```")
                if item_dict.get("error"):
                    additional_context_parts.append(f"Code Execution Error:\n```\n{item_dict['error']}\n```")
            elif isinstance(item_dict, str): # Fallback for simple string messages
                additional_context_parts.append(f"Code Execution Information:\n```\n{item_dict}\n```")

    existing_summaries_text_list = state.get("web_research_result", [])
    combined_summaries_text = "\n---\n".join(existing_summaries_text_list)

    if additional_context_parts:
        combined_summaries_text += "\n\n---Code Execution Details---\n" + "\n".join(additional_context_parts)

    formatted_prompt = answer_instructions.format(
        current_date=current_date,
        research_topic=research_topic,
        summaries=combined_summaries_text, # USE THE COMBINED TEXT HERE
    )

    # init Reasoning Model, default to Gemini 2.5 Flash
    llm = ChatGoogleGenerativeAI(
        model=reasoning_model,
        temperature=0,
        max_retries=2,
        api_key=os.getenv("GEMINI_API_KEY"),
    )
    result = llm.invoke(formatted_prompt)

    yield {"finalize_answer": {"type": "status", "data": "Generating final answer..."}}
    # Replace the short urls with the original urls and add all used urls to the sources_gathered
    unique_sources = []
    for source in state.get("sources_gathered", []): # Use .get for safety
        if source.get("short_url") and source.get("value") and source["short_url"] in result.content:
            result.content = result.content.replace(
                source["short_url"], source["value"]
            )
            unique_sources.append(source)

    yield {
        "messages": [AIMessage(content=result.content)],
        "sources_gathered": unique_sources,
    }


def code_execution(state: OverallState, config: RunnableConfig) -> dict:
    files_to_write = state.get("files_to_write")
    command_to_run = state.get("command_to_run")

    yield {"code_execution": {"type": "status", "data": f"Executing command: {command_to_run} with {len(files_to_write)} file(s)."}}
    if not files_to_write or not command_to_run:
        # This case should ideally be handled by routing logic before reaching here.
        error_output = {"error": "Code execution node was called without files or command."}
        yield {"code_execution": {"type": "output", "data": error_output}}
        yield {"code_execution_output": [error_output]}
        return

    sandbox_input = CodeSandboxInput(files=files_to_write, command=command_to_run)
    execution_result = code_sandbox(sandbox_input) # Calling the imported tool

    yield {"code_execution": {"type": "output", "data": execution_result}}
    # The output is stored in a list to align with how web_research_result is stored.
    yield {"code_execution_output": [execution_result]}


# Create our Agent Graph
builder = StateGraph(OverallState, config_schema=Configuration)

# Define the nodes we will cycle between
builder.add_node("generate_query", generate_query)
builder.add_node("web_research", web_research)
builder.add_node("reflection", reflection)
builder.add_node("code_execution", code_execution) # ADDED
builder.add_node("finalize_answer", finalize_answer)

# Set the entrypoint as `generate_query`
# This means that this node is the first one called
builder.add_edge(START, "generate_query")
# Add conditional edge to continue with search queries in a parallel branch
builder.add_conditional_edges(
    "generate_query", continue_to_web_research, ["web_research"]
)
# Reflect on the web research
builder.add_edge("web_research", "reflection")
# Evaluate the research (MODIFIED)
builder.add_conditional_edges(
    "reflection",
    evaluate_research, # This function now returns Union[str, List[Send]]
    { # This map is used if evaluate_research returns a string key
        "code_execution": "code_execution",
        "finalize_answer": "finalize_answer",
        # Web research is handled implicitly if evaluate_research returns List[Send] objects
        # targeting the "web_research" node.
    }
)
# Add edge from code_execution to finalize_answer (ADDED)
builder.add_edge("code_execution", "finalize_answer")
# Finalize the answer
builder.add_edge("finalize_answer", END)

graph = builder.compile(name="pro-search-agent")
