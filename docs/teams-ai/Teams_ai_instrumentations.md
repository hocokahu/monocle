# Teams AI Support

## Table of Contents

1. [Code Flow](#code-flow)
   - [Flow Breakdown](#flow-breakdown)
2. [Instrumentation Requirements](#instrumentation-requirements)
   - [Basic Custom Engine Agent (Typescript)](#1-basic-custom-engine-agent-typescript)
   - [Basic Bot](#2-basic-bot)
   - [Agent with API Build from Scratch](#3-agent-with-api-build-from-scratch)
   - [AI Bot with Azure AI Search](#4-ai-bot-with-azure-ai-search)

## Overview

Versions to understand where we are:

- Python: monocle_apptrace v0.4.0

- Typescript: Monocle v0.2.0-beta.1

The goal of this document is to identify the gaps for each of Teams AI app samples to cover the instrumentation gaps in the Teams AI SDK.

Sample Apps Source: https://github.com/OfficeDev/microsoft-365-agents-toolkit/tree/main/templates

## Code Flow

> We will use [Agent with API Build from Scratch](https://github.com/OfficeDev/microsoft-365-agents-toolkit/tree/main/templates/python/custom-copilot-assistant-new) bot for all flow diagrams below. They are mostly similar except the usage of `ActionPlanner` SDK.

This diagram illustrates the code flow from a user sending a chat message in Teams to a specific action handler, like `createTask`, being executed within the bot.

```mermaid
sequenceDiagram
    participant User
    participant WebApp as "aiohttp App (app.py)"
    participant Application as "teams.Application"
    participant AI as "teams.ai.AI (ai.py)"
    participant Planner as "ActionPlanner"
    participant OpenAI as "OpenAI Client"
    participant ActionEntry as "Registered Action (bot.py)"

    User->>WebApp: POST /api/messages (e.g., "create a task to buy milk")
    WebApp->>Application: bot_app.process(req)
    note right of Application: Application.process orchestrates the turn. It uses an adapter<br/>to create a TurnContext and then calls the turn handler.

    Application->>AI: AI.run(context, state)
    note right of AI: AI.run starts the AI logic flow.

    AI->>AI: moderator.review_input()
    AI->>Planner: planner.begin_task(context, state)
    note right of Planner: ActionPlanner builds a prompt using PromptManager,<br/>including user input, history, and functions from actions.json.
    
    Planner->>OpenAI: model.complete_prompt(...)
    OpenAI-->>Planner: LLM returns JSON with command to call 'createTask' action.
    Planner-->>AI: Returns a Plan object with a `PredictedDoCommand` for 'createTask'.
    
    AI->>AI: moderator.review_output(plan)
    AI->>AI: Executes commands in the Plan
    
    note right of AI: For a PredictedDoCommand, AI.run finds the registered action<br/>and invokes the default 'DO_COMMAND' handler (_on_do_command).

    AI->>AI: _on_do_command(context, state, command)
    AI->>ActionEntry: action_entry.invoke(context, state, parameters)
    note right of ActionEntry: This calls the actual Python function decorated<br/>with @bot_app.ai.action("createTask").
    
    ActionEntry->>ActionEntry: createTask(context, state) executes
    ActionEntry-->>AI: Returns string result (e.g. "task created...")
    
    AI->>Application: AI.run() completes.
    Application->>WebApp: Returns HTTP response.
```

### Flow Breakdown

1.  **Request Entry**: The user's message is sent to the `/api/messages` endpoint in `src/app.py`.
2.  **Application Processing**: `bot_app.process(req)` is called. The `teams.Application` instance, using `TeamsAdapter`, converts the incoming HTTP request into a `TurnContext` object, which encapsulates all the information about the turn.
3.  **AI System Execution**: The application routes the `TurnContext` to the AI system by calling `AI.run(context, state)`.
4.  **Input Moderation**: The AI system's `Moderator` first reviews the user's input for any policy violations (See [Moderator](https://github.com/microsoft/teams-ai/blob/main/getting-started/CONCEPTS/MODERATOR.md)).
5.  **Planning**: `ActionPlanner.begin_task` is invoked.
    *   It uses the `PromptManager` to construct a detailed prompt. This prompt includes the overall instructions (`skprompt.txt`), the user's current message, conversation history, and the list of available tools/actions (`actions.json`).
    *   The `OpenAIModel` sends this prompt to the configured LLM.
    *   The LLM analyzes the prompt and decides that the `createTask` action should be executed. It returns a response, typically structured as JSON, indicating the action name and parameters (e.g., `{"action": "createTask", "parameters": {"title": "buy milk", "description": "get some milk from the store"}}`).
    *   The `ActionPlanner` parses this response and creates a `Plan` object containing a `PredictedDoCommand`.
6.  **Output Moderation**: The generated `Plan` is reviewed by the `Moderator` before execution.
7.  **Plan Execution**: The `AI.run` method iterates through the commands in the `Plan`.
8.  **Action Dispatch**:
    *   For a `PredictedDoCommand`, `AI.run` calls its internal `_on_do_command` handler.
    *   `_on_do_command` looks up the action name (`createTask`) in its registry of actions.
    *   It finds the `ActionEntry` corresponding to `createTask` and calls its `invoke` method, passing the context, state, and the parameters from the plan.
9.  **Action Handler Execution**: The `invoke` call finally executes the Python function registered for the action, i.e., the `create_task` function in `src/bot.py`. This function contains the business logic to create the task and update the application state.
10. **Response**: The action returns a string, the AI loop may continue or end, and eventually, an HTTP response is sent back.

## Instrumentation Requirements

### 1. Basic Custom Engine Agent (Typescript)

#### Current State

**Spans**: 
- workflow

![](../resources/Basic-Custom-Engine-Agent.png)

**Traces**: [Basic-Custom-Engine-Agent.json](../resources/Basic-Custom-Engine-Agent.json)

> This `workflow` is not useful for users because it doesn't show the details of the steps.

#### Requirements

At the minimum, this needs to be on-pair with Python version:

- `aiohttp.web_app.Application`
- `teams.ai.planners.action_planner.ActionPlanner`
- `teams.ai.models.openai_model.OpenAIModel`
- `openai.resources.chat.completions.completions.AsyncCompletions`

### 2. Basic Bot

#### Current State

**Spans**: 
- `workflow`
- `aiohttp.web_app.Application`
- `teams.ai.planners.action_planner.ActionPlanner`
- `teams.ai.models.openai_model.OpenAIModel`
- `openai.resources.chat.completions.completions.AsyncCompletions`

![](../resources/Basic-Bot.png)

**Traces**: [Basic-Bot.json](../resources/Basic-Bot.json)

#### Requirements

- `teams.ai.prompts.prompt_manager.PromptManager` - We need to understand better how PromptManager transforms the prompt using variables.


### 3. Agent with API Build from Scratch

#### Current State

**Spans**:
- `workflow`
- `aiohttp.web_app.Application`
- `teams.ai.planners.action_planner.ActionPlanner`
- `teams.ai.models.openai_model.OpenAIModel`
- `openai.resources.chat.completions.completions.AsyncCompletions`

![](../resources/Agent-with-API-Build-from-Scratch.png)

**Traces (without new instrumentation)**: [Agent-with-API-Build-from-Scratch.json](../resources/Agent-with-API-Build-from-Scratch.json)

#### Requirements (UPDATED 7/8 for 0.4.1a9)

The goal of this instrumentation:
1.  **[Optional]** Trace the complete lifecycle of a user request, from the initial HTTP call to the final action execution. The caveat is that this might apply to lots of aiohttp requests as well (which will cause a large number of traces).
2.  Gain visibility into the AI planner's decision-making process, including which actions and parameters are chosen.
3.  Monitor the performance and correctness of individual, custom-defined actions (the "API" part).
4.  Debug prompt engineering by inspecting the exact prompts sent to the LLM.
5.  **[Optional]** Understand the impact of content moderation on both user inputs and AI outputs. This is applicable to all bots using Teams AI SDK but most will rely on the LLM outputs to determine.

To gain deeper insights into the application's behavior, performance, and potential issues, we recommend instrumenting the following classes and methods. This complements the existing instrumentations on `aiohttp`, `ActionPlanner`, `OpenAIModel`, and `openai`.

> Note: The exact "method" may need to be verified. This is due to the use of Template Method Pattern in Teams AI SDK.
>
> For example, the Moderator's review_output() is defined in various files:
>
> ```python
> # Base abstract class (interface)
> class Moderator(ABC):
> @abstractmethod
> async def review_output(self): pass
>
> # Concrete implementations
> class DefaultModerator(Moderator):
> async def review_output(self):
> return plan # Simple pass-through
>
> class OpenAIModerator(Moderator):
> async def review_output(self):
> # Complex OpenAI moderation logic
>
> class AzureContentSafetyModerator(Moderator):
> async def review_output(self):
> # Complex Azure moderation logic
> ```
>
> The method exists everywhere because:
> - Moderator (base class) defines it as an abstract method that all moderators must implement
> - Each concrete moderator class (`DefaultModerator`, `OpenAIModerator`, `AzureContentSafetyModerator`) provides its own implementation:
> - `DefaultModerator`: Simple pass-through, no moderation
> - `OpenAIModerator`: Uses OpenAI's moderation API
> - `AzureContentSafetyModerator`: Uses Azure Content Safety API
>
> This pattern allows the Teams AI framework to:
> - Use any moderator interchangeably (polymorphism)
> - Ensure all moderators have the required methods
> - Let each moderator implement its own moderation logic while maintaining a consistent interface

| Class/Method & Reason | Status | Details | Inputs to Capture | Outputs to Capture |
|----------------------|--------|---------|-------------------|-------------------|
| `teams.app.Application.process`<br/>To trace the entire processing of an incoming request, providing a top-level view of a single turn. | ✅ **Implemented** | Span name: `teams.app.application.process`<br/>Span type: `application` | `aiohttp.web.Request` object containing headers and body. | `aiohttp.web.Response` object. |
| `teams.ai.ai.AI.run`<br/>This is the main entry point for the AI logic. Instrumenting it allows seeing the entire AI chain of thought process for a turn. | ✅ **Implemented** | Span name: `teams.ai.ai.AI.run`<br/>Span type: `application` | `context: TurnContext`, `state: TurnState`. Can capture `context.activity.text` for user input. | Boolean for success. The final state, or any exceptions raised. |
| `teams.ai.actions.ActionEntry.invoke`<br/>To monitor the execution of individual actions predicted by the planner. Crucial for debugging action calls, parameters, and success/failure. | ✅ **Implemented** | Span name: `teams.ai.actions.action_entry.invoke`<br/>Span type: `state_management` | `context: TurnContext`, `state: TurnState`, `parameters` for the action, `name` of the action. | The string result returned by the action handler. |
| `teams.ai.moderators.moderator.Moderator.review_input`<br/>To monitor input content moderation and understand if/why user input is being flagged. | ❌ **Not Implemented** | - | `context: TurnContext`, `state: TurnState`. Can capture `context.activity.text`. | A `Plan` object if the input is flagged (containing a `FLAGGED_INPUT` action), otherwise `None`. |
| `teams.ai.moderators.moderator.Moderator.review_output`<br/>To monitor output content moderation and understand if/why the bot's generated response/plan is being flagged. | ❌ **Not Implemented** | - | `context: TurnContext`, `state: TurnState`, `plan: Plan`. | The (potentially modified) `Plan` object. |
| `src.state.AppTurnState.load`<br/>To monitor the performance of loading application state from storage, helping identify state-related performance bottlenecks. | ✅ **Implemented** | Span name: `app.state.conversation_state.load`<br/>Span type: `state_management` | `context: TurnContext`, `storage: Storage`. | The loaded `AppTurnState` object. Its size could be captured. |
| `teams.state.conversation_state.ConversationState.load`<br/>To monitor base conversation state loading from storage. | ✅ **Implemented** | Span name: `teams.state.conversation_state.load`<br/>Span type: `state_management` | `context: TurnContext`, `storage: Storage`. | The loaded `ConversationState` object. Its size could be captured. |
| `teams.ai.prompts.prompt_manager.PromptManager.get_prompt`<br/>To inspect prompt templates and configurations being retrieved from the prompt manager. | ✅ **Implemented** | Span name: `teams.ai.prompts.prompt_manager.get_prompt`<br/>Span type: `prompt_manager` | `prompt_name` (e.g., "planner"). | `prompt_template`, `prompt_template_config`, `prompt_template_actions`. |
| `teams.ai.prompts.prompt_manager.PromptManager.render_prompt`<br/>To inspect the exact prompt being sent to the LLM. This is invaluable for debugging prompt engineering and improving model responses. | ❌ **Not Implemented** | - | `context: TurnContext`, `state: TurnState`, `prompt` name or template. | The rendered prompt string or list of messages. |

#### Pending Implementation & Flow

##### 1-Chat Conversation

**Sample Trace**: [Teams-ai-basic-rag-bot-prompt-manager1.json](../resources/Teams-ai-basic-rag-bot-prompt-manager1.json)

**Flow explained in plain English:**

1. **User Input**: "who is prasad https://raw.githubusercontent.com/monocle2ai/monocle/refs/heads/main/CODEOWNERS.md"

2. **First OpenAIModel Call**: 
   - **Prompt**: System instructions + user message + available actions (`createTask`, `deleteTask`, `extractRAGURL`, `SAY`)
   - **What affects the prompt**: User's question + URL + available action definitions
   - **LLM Decision**: "I need to extract the URL to find information about Prasad" → Plan: `DO` `extractRAGURL`

3. **extractRAGURL Action**: Fetches and stores the `CODEOWNERS.md` content in conversation state

4. **Second OpenAIModel Call**:
   - **Prompt**: System instructions + user message + **extracted content** (now includes the maintainers list) + available actions
   - **What affects the prompt**: User's question + **extracted content showing Prasad is a maintainer** + available action definitions
   - **LLM Decision**: "I found Prasad in the maintainers list" → Plan: `SAY` response

5. **SAY Command**: Sends final response to user

6. **Bot Output**: "Prasad Mujumdar is a maintainer of the project, and you can find more about him on his GitHub profile: @prasad-okahu."

**Key Insight**: The **extracted content** from the first action becomes part of the **second prompt**, enabling the LLM to provide an informed response based on the actual data from the URL.

**Technical Flow:**

1. **User**: Asks "who is prasad https://raw.githubusercontent.com/monocle2ai/monocle/refs/heads/main/CODEOWNERS.md"

2. **WebApp**: Receives the HTTP request and routes it to the Teams AI application

3. **ConversationState**: Loads the current conversation state from storage, including any previous context and extracted content

4. **AI.run**: Starts the AI processing pipeline for this user turn

5. **ActionPlanner**: Analyzes the user's request and determines what actions are needed

6. **OpenAIModel**: Receives the prompt and generates a plan to extract information from the provided URL

7. **ActionPlanner**: Creates a plan with the command `DO extractRAGURL` to fetch content from the GitHub URL

8. **AI.run**: Executes the plan, starting with `PLAN_READY` to indicate the plan is ready for execution

9. **ActionEntry**: Handles the `DO_COMMAND` by calling the `extractRAGURL` function, which fetches the content from the GitHub URL

10. **ActionEntry**: Updates the conversation state with the extracted content (the CODEOWNERS.md file showing maintainers)

11. **ActionPlanner**: Re-plans with the new context (now has the extracted content about maintainers)

12. **OpenAIModel**: Receives the updated prompt (now including the extracted content) and generates a plan to respond to the user

13. **ActionPlanner**: Creates a new plan with the command `SAY` to send a response to the user

14. **AI.run**: Executes the new plan, starting with `PLAN_READY` for the `SAY` command

15. **ActionEntry**: Handles the `SAY_COMMAND` by formatting the response using the extracted information about Prasad

16. **AI.run**: Returns the final response to the user

17. **User**: Receives the answer: "Prasad Mujumdar is a maintainer of the project, and you can find more about him on his GitHub profile: @prasad-okahu."

```mermaid
sequenceDiagram
    participant User
    participant WebApp as "aiohttp App (app.py)"
    participant ConversationState
    participant AI as "AI.run"
    participant Planner as "ActionPlanner"
    participant OpenAI as "OpenAIModel"
    participant ActionEntry as "action_entry (bot.py)"

    %% Single chat: User asks about Prasad
    User->>WebApp: who is prasad https://raw.githubusercontent.com/monocle2ai/monocle/refs/heads/main/CODEOWNERS.md
    WebApp->>ConversationState: load()
    ConversationState-->>WebApp: state loaded
    WebApp->>AI: AI.run(context, state)
    AI->>Planner: planner.begin_task(context, state)
    Planner->>OpenAI: OpenAIModel.complete_prompt(...)
    OpenAI-->>Planner: LLM returns plan (DO extractRAGURL)
    Planner-->>AI: Plan(commands=[DO extractRAGURL])
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ PLAN_READY
    Note right of ActionEntry: Handles PLAN_READY (plan is ready to execute)
    ActionEntry-->>AI: "Plan ready, proceeding to next command"
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ DO_COMMAND
    Note right of ActionEntry: Handles DO_COMMAND (calls extractRAGURL)
    ActionEntry-->>AI: "Successfully extracted content from URLs..."
    Note right of ActionEntry: Updates state with extracted content
    AI->>Planner: planner.begin_task(context, state) [Second iteration]
    Note right of Planner: Planner now has extracted content in state
    Planner->>OpenAI: OpenAIModel.complete_prompt(...) [Second call]
    OpenAI-->>Planner: LLM returns plan (SAY response)
    Planner-->>AI: Plan(commands=[SAY])
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ PLAN_READY
    ActionEntry-->>AI: "Plan ready, proceeding to next command"
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ SAY_COMMAND
    Note right of ActionEntry: Handles SAY_COMMAND (send answer with extracted info)
    ActionEntry-->>AI: "Prasad Mujumdar is a maintainer of the project..."
    AI-->>User: Prasad Mujumdar is a maintainer of the project, and you can find more about him on his GitHub profile: [@prasad-okahu](https://github.com/prasad-okahu).
```

##### 3-Chat Conversation

**Sample Trace**: 

- [Teams-ai-basic-rag-bot-3-chat.json](../resources/Teams-ai-basic-rag-bot-3-chat.json)

- [Teams-ai-basic-rag-bot-prompt-manager2.json](../resources/Teams-ai-basic-rag-bot-prompt-manager2.json)

**Key Points:**

1. **First Message ("hi")**: No function calls needed - direct `SAY` response
2. **Second Message**: Calls `extractRAGURL` to fetch content, then `SAY` response  
3. **Third Message**: Calls `extractRAGURL` again (demonstrates conversation_state persistence across messages)

**Demonstrates**: How conversation_state maintains context and extracted content across multiple user interactions.

```mermaid
sequenceDiagram
    participant User
    participant WebApp as "aiohttp App (app.py)"
    participant ConversationState
    participant AI as "AI.run"
    participant Planner as "ActionPlanner"
    participant OpenAI as "OpenAIModel"
    participant ActionEntry as "action_entry (bot.py)"

    %% 1. Simple greeting
    User->>WebApp: hi
    WebApp->>ConversationState: load()
    ConversationState-->>WebApp: state loaded
    WebApp->>AI: AI.run(context, state)
    AI->>Planner: planner.begin_task(context, state)
    Planner->>OpenAI: OpenAIModel.complete_prompt(...)
    OpenAI-->>Planner: LLM returns plan (SAY hello)
    Planner-->>AI: Plan(commands=[SAY])
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ PLAN_READY
    Note right of ActionEntry: Handles PLAN_READY (plan is ready to execute)
    ActionEntry-->>AI: "Plan ready, proceeding to next command"
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ SAY_COMMAND
    Note right of ActionEntry: Handles SAY_COMMAND (send greeting)
    ActionEntry-->>AI: "Hello! How can I assist you today?"
    AI-->>User: Hello! How can I assist you today?

    %% 2. User asks about Prasad (triggers RAG extraction)
    User->>WebApp: who is prasad <CODEOWNERS.md>
    WebApp->>ConversationState: load()
    ConversationState-->>WebApp: state loaded
    WebApp->>AI: AI.run(context, state)
    AI->>Planner: planner.begin_task(context, state)
    Planner->>OpenAI: OpenAIModel.complete_prompt(...)
    OpenAI-->>Planner: LLM returns plan (DO extractRAGURL, SAY)
    Planner-->>AI: Plan(commands=[DO extractRAGURL, SAY])
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ PLAN_READY
    Note right of ActionEntry: Handles PLAN_READY (plan is ready to execute)
    ActionEntry-->>AI: "Plan ready, proceeding to next command"
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ DO_COMMAND
    Note right of ActionEntry: Handles DO_COMMAND (calls extractRAGURL)
    ActionEntry-->>AI: "Prasad refers to Prasad Mujumdar..."
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ SAY_COMMAND
    Note right of ActionEntry: Handles SAY_COMMAND (send answer)
    ActionEntry-->>AI: "Prasad refers to Prasad Mujumdar..."
    AI-->>User: Prasad refers to Prasad Mujumdar, who is listed as a maintainer in the project...

    %% 3. User asks for all maintainers (triggers RAG extraction again)
    User->>WebApp: who else are maintainers in <CODEOWNERS.md>
    WebApp->>ConversationState: load()
    ConversationState-->>WebApp: state loaded
    WebApp->>AI: AI.run(context, state)
    AI->>Planner: planner.begin_task(context, state)
    Planner->>OpenAI: OpenAIModel.complete_prompt(...)
    OpenAI-->>Planner: LLM returns plan (DO extractRAGURL, SAY)
    Planner-->>AI: Plan(commands=[DO extractRAGURL, SAY])
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ PLAN_READY
    Note right of ActionEntry: Handles PLAN_READY (plan is ready to execute)
    ActionEntry-->>AI: "Plan ready, proceeding to next command"
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ DO_COMMAND
    Note right of ActionEntry: Handles DO_COMMAND (calls extractRAGURL)
    ActionEntry-->>AI: "The current list of maintainers..."
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ SAY_COMMAND
    Note right of ActionEntry: Handles SAY_COMMAND (send answer)
    ActionEntry-->>AI: "The current list of maintainers..."
    AI-->>User: The current list of maintainers for the project is as follows: ...

    %% 4. Error handling (invalid LLM output)
    Note over AI,Planner: If LLM returns invalid JSON\nPlanner/AI returns error:\n'No valid JSON objects were found in the response. Return a valid JSON object with your thoughts and the next action to perform.'
```

### 4. AI Bot with Azure AI Search

#### Current State

**Spans**:
- `workflow`
- `aiohttp.web_app.Application`
- `teams.ai.planners.action_planner.ActionPlanner`
- `teams.ai.models.openai_model.OpenAIModel`
- `openai.resources.chat.completions.completions.AsyncCompletions`
- `openai.resources.embeddings.AsyncEmbeddings`

![](../resources/AI-Bot-with-Azure-AI-Search.png)


**Traces**: [AI-Bot-with-Azure-AI-Search.json](../resources/AI-Bot-with-Azure-AI-Search.
json)

#### Requirements (UPDATED 7/8 for 0.4.1a9)

The goal of this instrumentation:
1.  Search performance metrics (latency, result counts)
2.  Search quality indicators (scores, reranking)
3.  Prompt construction with search results
4.  Citation handling and formatting

The Azure AI Search bot extends the basic Teams AI bot with search capabilities. Here's how the flow works:

1.  **Initial Request Flow**: Same as basic bot until reaching the planner.
2.  **Search Integration Points**:
    *   When user asks a question, the bot first converts it to embeddings using `openai.resources.embeddings.AsyncEmbeddings`.
    *   These embeddings are used to perform vector search in Azure AI Search.
    *   Search results are incorporated into the prompt before calling the LLM.
    *   The LLM then generates a response based on both the search results and the conversation context.

> **Note**: Azure Search instrumentation requires both client and post-processing due to data availability (*This assumption needs validation*):
> *   `azure.search.documents.search`: Captures the initial search request but may lack complete result details.
> *   `azure.search.documents.search_post`: Captures full search results including scores and reranking.
>
> ```python
> # Example of what client vs post capture:
> # Client capture - Basic request info
> {
>     "vector_queries": [{"fields": "vector", "k": 3}],
>     "select": "docTitle,content"
> }
> 
> # Post capture - Detailed results
> {
>     "results": [
>         {
>             "docTitle": "Document 1",
>             "description": "Content...",
>             "@search.score": 0.89,
>             "@search.reranker_score": 0.92
>         }
>     ]
> }
> ```

#### Classes and Methods to Instrument

| Class/Method & Reason | Status | Details | Inputs to Capture | Outputs to Capture |
|---|---|---|---|---|
| `azure.search.documents.`<br/>`SearchClient.search`<br/>Monitor raw search requests and performance. Captures the query sent to Azure Search before post-processing. | ✅ **Implemented** | Span name: `azure.search.documents.`<br/>`_search_client.SearchClient`<br/>Span type: `search` | `kwargs`: `search_text`, `vector_queries` (without vector data), `filter`, `select`, `top`, `skip` | `pager`: `get_count()`, `get_coverage()`, `get_facets()` |
| `azure.search.documents.`<br/>`SearchClient.search_post`<br/>Capture detailed search results with scores after post-processing. Essential for visibility into reranking and final document scores. | ✅ **Implemented** | Span name: `azure.search.documents._generated.operations.`<br/>`_documents_operations.DocumentsOperations`<br/>Span type: `search` | `search_request`: `search_text` and other options like `scoring_profile`, `semantic_query`. | `results`: List of documents with `docTitle`, `description`, `@search.score`, `@search.reranker_score`. |
| `teams.ai.prompts.prompt_manager.`<br/>`PromptManager.render_prompt`<br/>Debug how search results are incorporated into the final prompt sent to the LLM. | ❌ **Not Implemented** | - | `state`: `temp.data_sources` which contains the search results. `prompt`: The prompt template object. | The fully rendered `PromptTemplate` object, including the text with citations from search results. |
| `teams.ai.citations.citations.`<br/>`format_citations_response`<br/>Monitor citation formatting. Useful for debugging cases where citations are missing or incorrect in the final response. | ❌ **Not Implemented** | - | `content`: The raw response string from the LLM. `citations`: List of `ClientCitation` objects. | The formatted response string with citation markers (e.g., `[doc1]`). |

**Sample Instrumented Traces**: [AI-Bot-with-Azure-AI-Search-Instrumented.json](../resources/AI-Bot-with-Azure-AI-Search-Instrumented.json) (Sample with full search instrumentation)

![](../resources/AI-Bot-with-Azure-AI-Search-Instrumented.png)

#### Pending Implementation & Flow

**Flow explained in plain English:**

1. **User Input**: "tell me about executive vacation days"

2. **Conversation State Loading**: The bot loads the current conversation state from storage to maintain context across interactions

3. **Embedding Generation**: The user's query "tell me about executive vacation days" is converted to vector embeddings using Azure OpenAI's embedding model

4. **Azure AI Search - SearchClient.search**: The embeddings are used to perform vector search against the "contoso-electronics" index, with the search request captured by the instrumented `azure.search.documents._search_client.SearchClient` span

5. **Azure AI Search - DocumentsOperations**: The search results are processed and returned with detailed document information, scores, and content, captured by the instrumented `azure.search.documents._generated.operations._documents_operations.DocumentsOperations` span:
   - **Contoso_Electronics_PerkPlus_Program** (score: 0.033)
   - **Contoso_Electronics_Company_Overview** (score: 0.033) 
   - **Contoso_Electronics_Plan_Benefits** (score: 0.016)

6. **Context Integration**: The search results are incorporated into the prompt template (Note: PromptManager.render_prompt is not yet instrumented)

7. **LLM Processing**: The OpenAIModel receives the enhanced prompt with search context and generates a structured response with citations

8. **Response Generation**: The ActionPlanner processes the LLM output and creates a response (Note: Citations formatting is not yet instrumented)

9. **Bot Output**: The final response is sent to the user: "Executive vacation days are typically part of a broader benefits package that includes paid time off (PTO) for senior management. These days allow executives to recharge and maintain work-life balance, often exceeding standard vacation policies. Companies may offer flexible scheduling or additional days based on tenure or performance."

**Key Insight**: The Azure AI Search integration enables the bot to provide accurate, contextually relevant responses by retrieving and incorporating specific document content. The current instrumentation captures both the search request (`SearchClient.search`) and detailed results (`DocumentsOperations`), providing visibility into search performance and quality.

**Technical Flow:**

1. **User**: Asks "tell me about executive vacation days"

2. **WebApp**: Receives the HTTP request and routes it to the Teams AI application

3. **ConversationState**: Loads the current conversation state from storage, including any previous context

4. **AI.run**: Starts the AI processing pipeline for this user turn

5. **ActionPlanner**: Analyzes the user's request and determines that search is needed

6. **Embeddings**: Converts the user query to vector embeddings using Azure OpenAI

7. **SearchClient.search**: Performs vector search against the contoso-electronics index with k=2 nearest neighbors (instrumented span: `azure.search.documents._search_client.SearchClient`)

8. **DocumentsOperations**: Returns relevant documents with scores and content about vacation policies (instrumented span: `azure.search.documents._generated.operations._documents_operations.DocumentsOperations`)

9. **Prompt Enhancement**: The search results are integrated into the prompt template with context tags (Note: PromptManager.render_prompt not instrumented)

10. **OpenAIModel**: Receives the enhanced prompt and generates a structured response with citations

11. **ActionPlanner**: Processes the LLM output and creates the final response

12. **AI.run**: Executes the plan, starting with `PLAN_READY` to indicate the plan is ready for execution

13. **ActionEntry**: Handles the `PLAN_READY` command

14. **ActionEntry**: Handles the `SAY_COMMAND` by formatting the response (Note: Citations formatting not instrumented)

15. **AI.run**: Returns the final response to the user

16. **User**: Receives the answer with proper citations about executive vacation policies

```mermaid
sequenceDiagram
    participant User
    participant WebApp as "aiohttp App (app.py)"
    participant ConversationState
    participant AI as "AI.run"
    participant Planner as "ActionPlanner"
    participant Embeddings as "Azure OpenAI Embeddings"
    participant SearchClient as "azure.search.documents._search_client.SearchClient"
    participant DocumentsOps as "azure.search.documents._generated.operations._documents_operations.DocumentsOperations"
    participant OpenAI as "OpenAIModel"
    participant ActionEntry as "action_entry (bot.py)"

    %% Azure AI Search flow: User asks about executive vacation days
    User->>WebApp: tell me about executive vacation days
    WebApp->>ConversationState: load()
    ConversationState-->>WebApp: state loaded
    WebApp->>AI: AI.run(context, state)
    AI->>Planner: planner.begin_task(context, state)
    Planner->>Embeddings: convert query to embeddings
    Embeddings-->>Planner: vector embeddings
    Planner->>SearchClient: vector search (k=2, contoso-electronics index)
    Note right of SearchClient: Search query: "tell me about executive vacation days"<br/>Index: contoso-electronics<br/>Vector fields: descriptionVector<br/>Span type: search
    SearchClient->>DocumentsOps: process search results
    DocumentsOps-->>Planner: Search results with scores
    Note right of DocumentsOps: Results:<br/>• Contoso_Electronics_PerkPlus_Program (0.033)<br/>• Contoso_Electronics_Company_Overview (0.033)<br/>• Contoso_Electronics_Plan_Benefits (0.016)<br/>Span type: search
    Planner->>OpenAI: OpenAIModel.complete_prompt(...)
    Note right of OpenAI: Enhanced prompt with search context<br/>System: "Use context in <context></context> tags"<br/>User: "tell me about executive vacation days"<br/>Context: [Search results with vacation policies]
    OpenAI-->>Planner: LLM returns structured response with citations
    Planner-->>AI: Response with citations
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ PLAN_READY
    Note right of ActionEntry: Handles PLAN_READY (plan is ready to execute)
    ActionEntry-->>AI: "Plan ready, proceeding to next command"
    AI->>ActionEntry: action_entry.invoke(context, state, parameters) ++ SAY_COMMAND
    Note right of ActionEntry: Handles SAY_COMMAND (send answer with citations)
    ActionEntry-->>AI: "Executive vacation days are typically part of a broader benefits package..."
    AI-->>User: Executive vacation days are typically part of a broader benefits package that includes paid time off (PTO) for senior management. These days allow executives to recharge and maintain work-life balance, often exceeding standard vacation policies. Companies may offer flexible scheduling or additional days based on tenure or performance.
```
