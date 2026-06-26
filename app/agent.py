import os
import sys
import json
import re
import datetime
from google.adk.workflow import Workflow, START
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.genai import types
from google.adk.apps import App, ResumabilityConfig
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from app.config import config

# Setup MCP Toolset dynamically pointing to local mcp_server.py
current_dir = os.path.dirname(os.path.abspath(__file__))
mcp_server_path = os.path.join(current_dir, "mcp_server.py")

mcp_tools = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", sys.executable, mcp_server_path],
        )
    )
)

# Specialized Sub-Agent 1: Agronomist (uses MCP tools for diagnosis and weather)
agronomist = LlmAgent(
    name="agronomist",
    model=config.model,
    instruction="""You are an expert Indian agronomist. You specialize in:
1. Diagnosing crop diseases from symptoms described by farmers. Use the diagnose_crop_symptoms tool to look up diagnoses.
2. Recommending organic, chemical, or preventative treatments.
3. Advising on soil health, fertilizers, crop rotation, and irrigation based on weather conditions. Use the get_weather_advisory tool to get local recommendations.
Keep suggestions practical, low-cost, and relevant to Indian agricultural regions.
If recommending chemical pesticides, explicitly list the dosage and safety instructions.""",
    description="Consult for crop diseases, pests, soil management, irrigation, and agronomic practices.",
    tools=[mcp_tools]
)

# Specialized Sub-Agent 2: Market Analyst (uses MCP tool for mandi prices)
market_analyst = LlmAgent(
    name="market_analyst",
    model=config.model,
    instruction="""You are an expert agricultural economist and market analyst in India. You specialize in:
1. Crop market prices (mandi rates) and price trends. Use the get_mandi_prices tool to look up live rates.
2. Market timing - when is the best time to sell or hold.
3. Logistics and transportation advice to reduce post-harvest losses.
Provide realistic market advice considering MSP (Minimum Support Price) and regional mandis.""",
    description="Consult for mandi prices, demand trends, market timing, selling strategies, and logistics.",
    tools=[mcp_tools]
)

# Orchestrator: Coordinates user queries and delegates to specialized sub-agents
orchestrator = LlmAgent(
    name="orchestrator",
    model=config.model,
    instruction="""You are FarmSense AI, the primary agricultural coordinator for Indian farmers.
Your job is to understand the farmer's query and delegate to either the Agronomist or Market Analyst.
Use your tools to query the specialist agents. Once you receive their input, synthesize the information into a single, cohesive, polite, and helpful response.
Provide your final answer in simple terms, using local names for crops where applicable.""",
    tools=[AgentTool(agronomist), AgentTool(market_analyst)]
)

# Security Checkpoint Node: PII scrubbing, injection detection, domain checking, and JSON auditing
def security_checkpoint(ctx: Context, node_input: types.Content) -> Event:
    # Extract text from START input
    text = ""
    if node_input and node_input.parts:
        text = "".join([part.text for part in node_input.parts if part.text])
    else:
        text = str(node_input)

    original_text = text

    # PII Scrubbing (Indian Phone numbers and Aadhaar card numbers)
    phone_pattern = r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b"
    aadhaar_pattern = r"\b\d{4}\s?\d{4}\s?\d{4}\b"
    
    scrubbed_text, phone_subs = re.subn(phone_pattern, "[PHONE_REDACTED]", text)
    scrubbed_text, aadhaar_subs = re.subn(aadhaar_pattern, "[AADHAAR_REDACTED]", scrubbed_text)
    
    total_scrubs = phone_subs + aadhaar_subs

    # Prompt Injection Detection
    injection_keywords = ["ignore instructions", "system prompt", "ignore previous", "developer mode", "bypass safety", "override system"]
    text_lower = original_text.lower()
    injection_detected = any(kw in text_lower for kw in injection_keywords)

    # Domain specific rule: warning on banned agricultural chemicals (e.g. DDT, Paraquat, Endosulfan)
    banned_pesticides = ["ddt", "endosulfan", "aldrin", "lindane", "paraquat", "monocrotophos"]
    has_banned_pesticide = any(pest in text_lower for pest in banned_pesticides)

    # Determine routing, log severity, and output
    if injection_detected:
        severity = "CRITICAL"
        status = "rejected_injection"
        route = "security_event"
        output_message = "🚨 Security Alert: Prompt injection attempt detected. Access denied."
    else:
        severity = "WARNING" if has_banned_pesticide else "INFO"
        status = "flagged_banned_chemical" if has_banned_pesticide else "approved"
        route = "approved"
        output_message = scrubbed_text

    # Write audit log to stderr as structured JSON
    audit_log = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "event": "security_checkpoint",
        "status": status,
        "pii_scrubbed_count": total_scrubs,
        "injection_detected": injection_detected,
        "banned_chemical_detected": has_banned_pesticide,
        "severity": severity
    }
    print(json.dumps(audit_log), file=sys.stderr)

    return Event(output=output_message, route=route, state={"scrubbed_input": output_message, "banned_chemical_flagged": has_banned_pesticide})

# Security Alert Node: Handles security incidents
def security_alert(node_input: str) -> str:
    return node_input

# Verifier Node: Inspects orchestrator's output to determine if human agronomist review is needed
def verifier(ctx: Context, node_input: types.Content) -> Event:
    text = ""
    if node_input and node_input.parts:
        text = "".join([part.text for part in node_input.parts if part.text])
    else:
        text = str(node_input)

    # Save orchestrator output to state
    ctx.state["orchestrator_output"] = text

    text_lower = text.lower()
    # Check if recommendation contains high-risk elements
    needs_review = any(keyword in text_lower for keyword in ["chemical", "pesticide", "sell now", "transaction", "buy now"])

    if needs_review:
        return Event(output=text, route="needs_review")
    else:
        return Event(output=text, route="auto_approved")

# Human-in-the-Loop Review Node
async def human_review(ctx: Context, node_input: str):
    # Check if agronomist has approved the recommendation yet
    if not ctx.resume_inputs or "approved" not in ctx.resume_inputs:
        yield RequestInput(
            interrupt_id="approved",
            message=f"⚠️ FarmSense Security Checkpoint: A high-risk agronomic or market suggestion requires verification.\nResponse to verify:\n{node_input}\n\nDo you approve this recommendation? (yes/no)"
        )
        return

    user_approval = ctx.resume_inputs["approved"]
    if user_approval.lower() in ["yes", "y", "approve"]:
        yield Event(output=node_input, state={"approved": True})
    else:
        yield Event(output="[REJECTED] The chemical pesticide or financial recommendation was not approved by our agronomy safety checkpoint. Please ask for alternative organic methods.", state={"approved": False})

# Final Output Node: Renders response in Web UI and returns the final value
def final_output(node_input: str):
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=node_input)]))
    yield Event(output=node_input)

# Create Workflow Graph (strictly avoiding duplicate edges)
root_agent = Workflow(
    name="farmsense_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {"approved": orchestrator, "security_event": security_alert}),
        (orchestrator, verifier),
        (verifier, {"needs_review": human_review, "auto_approved": final_output}),
        (human_review, final_output),  # Unconditional edge to target final_output
        (security_alert, final_output),  # Unconditional edge to target final_output
    ],
    state_schema=None
)

# App Container Configuration
app = App(
    name="app",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True)
)
