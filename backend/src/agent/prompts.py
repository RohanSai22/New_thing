from datetime import datetime


# Get current date in a readable format
def get_current_date():
    return datetime.now().strftime("%B %d, %Y")


query_writer_instructions = """Your goal is to generate sophisticated and diverse web search queries. These queries are intended for an advanced automated web research tool capable of analyzing complex results, following links, and synthesizing information.

Instructions:
- Always prefer a single search query, only add another query if the original question requests multiple aspects or elements and one query is not enough.
- Each query should focus on one specific aspect of the original question.
- Don't produce more than {number_queries} queries.
- Queries should be diverse, if the topic is broad, generate more than 1 query.
- Don't generate multiple similar queries, 1 is enough.
- Query should ensure that the most current information is gathered. The current date is {current_date}.

Format: 
- Format your response as a JSON object with ALL three of these exact keys:
   - "rationale": Brief explanation of why these queries are relevant
   - "query": A list of search queries

Example:

Topic: What revenue grew more last year apple stock or the number of people buying an iphone
```json
{{
    "rationale": "To answer this comparative growth question accurately, we need specific data points on Apple's stock performance and iPhone sales metrics. These queries target the precise financial information needed: company revenue trends, product-specific unit sales figures, and stock price movement over the same fiscal period for direct comparison.",
    "query": ["Apple total revenue growth fiscal year 2024", "iPhone unit sales growth fiscal year 2024", "Apple stock price growth fiscal year 2024"],
}}
```

Context: {research_topic}"""


web_searcher_instructions = """Conduct targeted Google Searches to gather the most recent, credible information on "{research_topic}" and synthesize it into a verifiable text artifact.

Instructions:
- Query should ensure that the most current information is gathered. The current date is {current_date}.
- Conduct multiple, diverse searches to gather comprehensive information.
- Consolidate key findings while meticulously tracking the source(s) for each specific piece of information.
- The output should be a well-written summary or report based on your search findings. 
- Only include the information found in the search results, don't make up any information.

Research Topic:
{research_topic}
"""

reflection_instructions = """
You are an expert research assistant analyzing summaries about "{research_topic}".
Your current operational effort level is: **{effort}**.

**Effort Level Guidance:**
- If Effort is "low": Prioritize speed. Avoid code execution and follow-up searches unless the query is impossible to answer otherwise. Aim to be sufficient in one loop. If code is absolutely necessary, keep it minimal.
- If Effort is "medium": Perform thorough research. If the query involves data, numbers, or complex logic, you should consider using the code execution tool to generate or verify information. Plan for one or two loops of follow-up questions or code execution if needed.
- If Effort is "high": You are in deep research mode. Actively seek opportunities to use code execution for verification, complex calculations, data visualization, or to process information from multiple sources. Plan for multiple research loops and code executions. Do not stop until the user's query has been answered exhaustively. Generate comprehensive code if it helps in achieving a better answer.

Your goal is to determine if the current information is sufficient or if further actions are needed, which may include additional web searches or executing code, keeping your effort level in mind.

Instructions:
- Evaluate the provided summaries based on your current effort level. Are they sufficient to answer the user's question comprehensively?
- If not, identify the knowledge gap. What specific information is missing or needs clarification?
- Based on the knowledge gap, you can suggest:
    a) Follow-up web search queries if more information needs to be gathered from the web.
    b) Writing files and a command to execute them in a sandbox if calculations, data processing, or code-based verification is needed.
- If you decide code execution is useful, provide:
    - `files_to_write`: A list of dictionaries, where each dictionary has "filename" (e.g., "main.py", "utils/helpers.py") and "code" (the Python code).
    - `command_to_run`: The shell command to execute these files (e.g., "python main.py").
- If code execution is not needed, `files_to_write` should be an empty list and `command_to_run` an empty string.
- If further web searches are not needed, `follow_up_queries` should be an empty list.
- If the information is sufficient, set `is_sufficient` to true.

Requirements:
- Ensure any follow-up queries are self-contained and include necessary context.
- Ensure filenames for code execution can represent paths (e.g., 'my_module/main.py').
- The agent can only either perform web searches OR execute code in a single step, not both. Prioritize the action that seems most direct to fill the knowledge gap.

Output Format:
- Format your response as a JSON object with these exact keys:
   - "is_sufficient": true or false
   - "knowledge_gap": Describe what information is missing or needs clarification (can be empty if sufficient).
   - "follow_up_queries": A list of specific questions to address this gap (can be empty).
   - "files_to_write": A list of file dictionaries (e.g., `[{"filename": "script.py", "code": "print('Hello')"}]`) or an empty list.
   - "command_to_run": A string for the command (e.g., "python script.py") or an empty string.

Example for code execution:
```json
{{
    "is_sufficient": false,
    "knowledge_gap": "The summary mentions a complex calculation is needed to determine the growth rate. I need to perform this calculation.",
    "follow_up_queries": [],
    "files_to_write": [
        {{
            "filename": "calculator.py",
            "code": "def calculate_growth(initial, final):\\n  return ((final - initial) / initial) * 100"
        }},
        {{
            "filename": "main.py",
            "code": "from calculator import calculate_growth\\ninitial_val = 100\\nfinal_val = 150\\ngrowth = calculate_growth(initial_val, final_val)\\nprint(f'Growth rate: {{growth}}%')"
        }}
    ],
    "command_to_run": "python main.py"
}}
```

Example for follow-up search:
```json
{{
    "is_sufficient": false,
    "knowledge_gap": "The summary lacks information about recent market trends for this technology.",
    "follow_up_queries": ["What are the latest market trends for [specific technology] in 2024?"],
    "files_to_write": [],
    "command_to_run": ""
}}
```

Example when sufficient:
```json
{{
    "is_sufficient": true,
    "knowledge_gap": "",
    "follow_up_queries": [],
    "files_to_write": [],
    "command_to_run": ""
}}
```

Reflect carefully on the Summaries to identify knowledge gaps and produce your output following this JSON format, adhering to your **{effort}** level guidance.

Summaries:
{summaries}
"""

answer_instructions = """Generate a high-quality answer to the user's question based on the provided summaries.

Instructions:
- The current date is {current_date}.
- You are the final step of a multi-step research process, don't mention that you are the final step. 
- You have access to all the information gathered from the previous steps.
- You have access to the user's question.
- Generate a high-quality answer to the user's question based on the provided summaries and the user's question.
- you MUST include all the citations from the summaries in the answer correctly.

User Context:
- {research_topic}

Summaries:
{summaries}"""
