from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams
from mcp.client.stdio import StdioServerParameters

import sys
from pathlib import Path

PYTHON = sys.executable
MCP_DIR = str(Path(__file__).resolve().parent.parent / "mcp_servers")


def _mcp(server_script):
    return MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=PYTHON,
                args=[str(Path(MCP_DIR) / server_script)],
            ),
            timeout=60,
        )
    )


marketing_intel_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="marketing_intel",
    description="Handles marketing analytics, morning briefings, and anomaly detection",
    instruction=(
        "You are a marketing intelligence analyst. You provide morning briefings on "
        "marketing performance, detect anomalies in marketing metrics, and analyze "
        "campaign effectiveness. Present data clearly with key takeaways. "
        "Use your tools to fetch real data before responding."
    ),
    tools=[_mcp("analytics_server.py")],
)

competitive_intel_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="competitive_intel",
    description="Monitors competitors, scans for market changes and competitive moves",
    instruction=(
        "You are a competitive intelligence analyst. You monitor competitor activities, "
        "scan for market changes, track competitive positioning, and identify emerging "
        "threats and opportunities in the competitive landscape. "
        "Use your tools to run competitor scans before responding."
    ),
    tools=[_mcp("competitive_server.py")],
)

customer_intel_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="customer_intel",
    description="Analyzes customer sentiment, scores leads, and segments customers",
    instruction=(
        "You are a customer intelligence analyst. You analyze customer sentiment from "
        "reviews and feedback, score and prioritize leads based on engagement signals, "
        "and segment customers for targeted campaign strategies. "
        "Use your tools to fetch real data before responding."
    ),
    tools=[_mcp("customer_server.py")],
)

operations_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="operations",
    description="Checks pipeline health and marketing attribution analysis",
    instruction=(
        "You are a marketing operations analyst. You monitor pipeline health across "
        "marketing channels, analyze attribution models to determine which touchpoints "
        "drive conversions, and flag operational issues that need attention. "
        "Use your tools to check pipeline status and run attribution analysis."
    ),
    tools=[_mcp("operations_server.py")],
)

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="marketing_orchestrator",
    description="Root orchestrator that coordinates marketing intelligence sub-agents",
    instruction=(
        "You are a marketing intelligence orchestrator. You coordinate 4 specialized "
        "sub-agents and log all workflows to the database.\n\n"
        "SUB-AGENTS:\n"
        "- marketing_intel: morning briefings, analytics, anomaly detection\n"
        "- competitive_intel: competitor monitoring, market scanning\n"
        "- customer_intel: sentiment analysis, lead scoring, customer segmentation\n"
        "- operations: pipeline health, marketing attribution analysis\n\n"
        "ROUTING RULES:\n"
        "1. For simple queries, delegate to the single appropriate sub-agent.\n"
        "2. For complex queries, chain multiple sub-agents in sequence and synthesize.\n"
        "3. Always log workflows to the database using your log_workflow and log_action tools.\n\n"
        "MULTI-STEP WORKFLOWS:\n\n"
        'Workflow: "Full marketing status update" or "executive summary"\n'
        "→ Step 1: marketing_intel for briefing and anomalies\n"
        "→ Step 2: competitive_intel for competitor scan\n"
        "→ Step 3: customer_intel for sentiment overview\n"
        "→ Step 4: Synthesize into executive summary with key metrics, risks, and actions\n\n"
        'Workflow: "A competitor launched a product" or "competitive threat"\n'
        "→ Step 1: competitive_intel for detailed competitor scan\n"
        "→ Step 2: customer_intel for sentiment impact analysis\n"
        "→ Step 3: operations for pipeline health check\n"
        "→ Step 4: Synthesize into threat assessment and action plan\n\n"
        'Workflow: "Analyze leads and pipeline" or "sales readiness"\n'
        "→ Step 1: customer_intel for lead scores and customer segments\n"
        "→ Step 2: operations for pipeline health and attribution\n"
        "→ Step 3: Synthesize into prioritized recommendations\n\n"
        "SYNTHESIS GUIDELINES:\n"
        "- After collecting data from sub-agents, produce a clear executive summary\n"
        "- Highlight the top 3 risks and top 3 opportunities\n"
        "- Include specific numbers and metrics from the sub-agent responses\n"
        "- End with prioritized action items\n"
        "- Log the completed workflow and each agent action to the database"
    ),
    tools=[_mcp("database_server.py")],
    sub_agents=[
        marketing_intel_agent,
        competitive_intel_agent,
        customer_intel_agent,
        operations_agent,
    ],
)
