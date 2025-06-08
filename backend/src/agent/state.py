from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict, List, Dict # Added List, Dict

from langgraph.graph import add_messages
from typing_extensions import Annotated


import operator
# from dataclasses import dataclass, field # Redundant import
# from typing_extensions import Annotated # Redundant import


class OverallState(TypedDict):
    messages: Annotated[list, add_messages]
    search_query: Annotated[list, operator.add] # Stores each search query string executed
    web_research_result: Annotated[list, operator.add] # Stores text summaries from web research
    sources_gathered: Annotated[list, operator.add] # Stores source objects
    initial_search_query_count: int # Config: number of initial queries
    max_research_loops: int # Config: max reflection loops
    research_loop_count: int # Current loop count
    reasoning_model: str # Config: which model to use for reasoning

    # Fields populated by reflection node
    is_sufficient: bool
    knowledge_gap: str
    follow_up_queries: Annotated[list, operator.add] # List of new queries from reflection
    files_to_write: List[Dict[str, str]] # Files for sandbox from reflection
    command_to_run: str # Command for sandbox from reflection

    # Field populated by code_execution node
    code_execution_output: Annotated[list, operator.add] # Output from sandbox

    # New field for effort level
    effort: str # e.g., "low", "medium", "high"

    # Field from generate_query
    query_list: List[str] # List of initial queries.

    # Field added by reflection node
    number_of_ran_queries: int


class ReflectionState(TypedDict): # This might be redundant if all fields are in OverallState
    is_sufficient: bool
    knowledge_gap: str
    follow_up_queries: Annotated[list, operator.add]
    research_loop_count: int
    number_of_ran_queries: int
    # files_to_write and command_to_run would also be here if it were a standalone state for reflection output
    # However, the reflection node in graph.py returns a dict that updates OverallState directly.


class Query(TypedDict): # This is used by QueryGenerationState
    query: str
    rationale: str


class QueryGenerationState(TypedDict): # This state is specific to the output of generate_query node if not directly merged to OverallState.
                                      # Given generate_query returns {"query_list": result.query}, and query_list is now in OverallState,
                                      # this specific TypedDict might be less critical if all nodes consume from OverallState.
                                      # However, continue_to_web_research receives QueryGenerationState.
                                      # For now, keeping it as is.
    query_list: list[Query] # generate_query actually returns List[str] for query_list based on prompt.
                            # The SearchQueryList Pydantic model has query: List[str].
                            # So this should be query_list: List[str] if generate_query directly updates OverallState.
                            # Or, if generate_query returns a dict with QueryGenerationState structure, then it's List[Query].
                            # Let's check graph.py's generate_query: it returns {"query_list": result.query}
                            # where result is SearchQueryList, and result.query is List[str].
                            # So QueryGenerationState should be query_list: List[str].

class WebSearchState(TypedDict): # Specific to web_research node's input needs
    search_query: str
    id: str


@dataclass(kw_only=True)
class SearchStateOutput: # Seems unused currently
    running_summary: str = field(default=None)  # Final report
