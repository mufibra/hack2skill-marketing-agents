"""
Database MCP Server — exposes workflow logging and task management tools.

Run:  python mcp_servers/database_server.py
"""

import sys
import json
from pathlib import Path

# Add project root to import path for db package
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("database")


@mcp.tool()
def log_workflow(workflow_name: str, status: str = "completed", result_summary: str = "") -> str:
    """Log a workflow run to the database. Returns the workflow run ID."""
    from db.db_utils import log_workflow_run
    row_id = log_workflow_run(workflow_name, status, result_summary)
    return json.dumps({"workflow_run_id": row_id, "status": status})


@mcp.tool()
def log_action(workflow_run_id: int, agent_name: str, tool_name: str, input_params: str = "", output_summary: str = "") -> str:
    """Log an agent action within a workflow run. Returns the action ID."""
    from db.db_utils import log_agent_action
    row_id = log_agent_action(workflow_run_id, agent_name, tool_name, input_params, output_summary)
    return json.dumps({"action_id": row_id, "workflow_run_id": workflow_run_id})


@mcp.tool()
def get_recent_workflows(limit: int = 10) -> str:
    """Get recent workflow runs from the database."""
    from db.db_utils import get_recent_workflows as _get
    workflows = _get(limit)
    return json.dumps(workflows, indent=2, default=str)


@mcp.tool()
def create_task(title: str, description: str = "", assigned_agent: str = "", priority: str = "medium") -> str:
    """Create a task in the database and assign it to an agent."""
    from db.db_utils import create_task as _create
    row_id = _create(title, description, assigned_agent, priority)
    return json.dumps({"task_id": row_id, "title": title, "assigned_agent": assigned_agent})


if __name__ == "__main__":
    mcp.run(transport="stdio")
