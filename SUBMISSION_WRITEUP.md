# FarmSense AI — Submission Write-Up

## Problem Statement
Over 100 million small-scale farmers in India face significant crop losses and income instability due to three main issues:
1. **Undetected Crop Diseases**: Lack of access to agricultural experts leads to incorrect treatment, ruining harvests.
2. **Poor Market Timing**: Price fluctuations in local mandis leave farmers vulnerable to middle-men, selling crops at suboptimal rates.
3. **Weather Risks**: Weather advisories lack agricultural context, leading to wasted fertilizer application or unharvested crop rot.

Farming advisory services are expensive, and existing tools do not support localized crop safety checks or protect farmer data. FarmSense AI fills this gap with a free, safe, and conversational multi-agent system.

---

## Solution Architecture

The application is structured as a deterministic graph workflow using ADK 2.0. Below is the workflow diagram illustrating data flow, agent collaboration, and validation checks:

```mermaid
graph TD
    START -->|User Query| SC["Security Checkpoint<br>(PII Redaction + Injection Filter)"]
    SC -->|approved| ORC["Orchestrator Agent"]
    SC -->|security_event| SA["Security Alert Handler"]
    
    ORC -->|Consultation| AG["Agronomist Agent"]
    ORC -->|Consultation| MA["Market Analyst Agent"]
    
    AG -.->|MCP Tools| MCP["MCP Server<br>(diagnose_crop_symptoms,<br>get_weather_advisory)"]
    MA -.->|MCP Tools| MCP["MCP Server<br>(get_mandi_prices)"]
    
    ORC -->|Synthesized Output| VER["Verifier Node"]
    VER -->|needs_review<br>(Chemicals/Transactions)| HITL["Human-in-the-Loop Review<br>(Agronomist Approval Pause)"]
    VER -->|auto_approved| FO["Final Output Node"]
    HITL -->|Approved / Rejected| FO
    SA -->|Direct Output| FO
```

---

## Concepts & ADK Features Used

1. **ADK 2.0 Workflow (Graph-Based)**: Implemented in [agent.py](file:///c:/Users/sankar%20reddy/Downloads/Ai_agents/day3/adk-workspace/farmsense-ai/app/agent.py#L170-L185) using the `Workflow` API to coordinate the orchestrator, security, verification, and human-in-the-loop nodes.
2. **LlmAgent**: Three specialized agents (`orchestrator`, `agronomist`, and `market_analyst`) are declared in [agent.py](file:///c:/Users/sankar%20reddy/Downloads/Ai_agents/day3/adk-workspace/farmsense-ai/app/agent.py#L13-L64) with tailored system instructions.
3. **AgentTool**: Used by the `orchestrator` in [agent.py](file:///c:/Users/sankar%20reddy/Downloads/Ai_agents/day3/adk-workspace/farmsense-ai/app/agent.py#L56-L64) to delegate subtasks to `agronomist` and `market_analyst` agents dynamically.
4. **MCP Server**: Implemented in [mcp_server.py](file:///c:/Users/sankar%20reddy/Downloads/Ai_agents/day3/adk-workspace/farmsense-ai/app/mcp_server.py) to connect agents to localized data resources (mandi prices, crop diagnoses, agro-weather bulletins).
5. **Security Checkpoint Node**: Built as a custom workflow function node in [agent.py](file:///c:/Users/sankar%20reddy/Downloads/Ai_agents/day3/adk-workspace/farmsense-ai/app/agent.py#L66-L113) to sanitize data, inspect threats, and produce audit logs.
6. **Agents CLI**: Scaffolded using `agents-cli scaffold create` and configured with a custom `.env` and `Makefile`.

---

## Security Design

1. **PII Redaction**: Regular expressions in [agent.py](file:///c:/Users/sankar%20reddy/Downloads/Ai_agents/day3/adk-workspace/farmsense-ai/app/agent.py#L76-L82) automatically redact Indian phone numbers and 12-digit Aadhaar Card numbers to protect identity privacy before the model processes it.
2. **Prompt Injection Prevention**: Keyword inspection immediately routes threats (e.g., requests to ignore prompts) to `security_event`, bypassing the orchestrator and returning a static alert.
3. **Banned Chemical Check (Domain Guardrail)**: Automatically scans for banned toxic pesticides (like DDT or Endosulfan) and adds a warning tag in the session state to alert agronomists.
4. **Structured JSON Audit Logs**: Writes structured JSON logs of security results to `sys.stderr` on every invocation for monitoring.

---

## MCP Server Design

Exposes 3 custom tools to provide local facts to the agents:
- `get_mandi_prices`: Queries regional eNAM mandi rates (min, max, modal) for a crop and district to prevent price exploitation.
- `get_weather_advisory`: Contextualizes local weather forecasts (e.g., rains) with agricultural advice (e.g., drainage, spraying delays).
- `diagnose_crop_symptoms`: Looks up crop disease diagnoses based on visible symptoms and provides both organic and chemical options.

---

## Human-in-the-Loop (HITL) Flow

A `verifier` function node in [agent.py](file:///c:/Users/sankar%20reddy/Downloads/Ai_agents/day3/adk-workspace/farmsense-ai/app/agent.py#L119-L137) checks if the final recommendation includes chemical pesticides or financial triggers (which require agronomist supervision). If detected, it routes the workflow to `human_review` which suspends execution using a `RequestInput` yield. The workflow resumes once an agronomist responds with approval (`yes` or `no`), preventing hazardous or erroneous advice from reaching the farmer.

---

## Demo Walkthrough

The following three scenarios demonstrate FarmSense AI's functionality:
1. **Scenario 1 (Agro-Diagnosis + HITL)**: The farmer reports leaf curling. The agronomist diagnoses Yellow Leaf Curl virus and recommends a chemical pesticide (Imidacloprid). The workflow pauses, requesting agronomist approval. The user approves, completing the flow.
2. **Scenario 2 (Market Info)**: The farmer queries tomato rates in Nashik. The market analyst retrieves live prices via the mandi MCP tool, advising on selling strategy.
3. **Scenario 3 (Security Block)**: A malicious input attempts a system prompt extraction. The security checkpoint rejects it instantly, returning an alert message.

---

## Impact / Value Statement

FarmSense AI democratizes expert agricultural advice for over 100 million smallholders in India. By providing secure, localized, and verified agronomic support, it reduces crop failure losses, increases mandi negotiating power, and protects farmers from applying hazardous chemicals, improving rural livelihoods and promoting sustainable farming practices.
