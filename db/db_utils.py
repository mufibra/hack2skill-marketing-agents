"""Helper functions for logging workflow runs, agent actions, tasks, and query results."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "marketing_intel.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def log_workflow_run(workflow_name, status="completed", result_summary=None):
    conn = _conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO workflow_runs (workflow_name, started_at, completed_at, status, result_summary) "
        "VALUES (?, ?, ?, ?, ?)",
        (workflow_name, now, now if status == "completed" else None, status, result_summary),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id


def log_agent_action(workflow_run_id, agent_name, tool_name, input_params=None, output_summary=None):
    conn = _conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO agent_actions (workflow_run_id, agent_name, tool_name, input_params, output_summary) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            workflow_run_id,
            agent_name,
            tool_name,
            json.dumps(input_params) if isinstance(input_params, (dict, list)) else input_params,
            output_summary,
        ),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id


def create_task(title, description=None, assigned_agent=None, priority="medium"):
    conn = _conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (title, description, assigned_agent, priority) VALUES (?, ?, ?, ?)",
        (title, description, assigned_agent, priority),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id


def save_query_result(query_text, agent_name=None, result_data=None):
    conn = _conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO query_results (query_text, agent_name, result_data) VALUES (?, ?, ?)",
        (
            query_text,
            agent_name,
            json.dumps(result_data) if isinstance(result_data, (dict, list)) else result_data,
        ),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id


def get_recent_workflows(limit=10):
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM workflow_runs ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_agent_actions(workflow_run_id):
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM agent_actions WHERE workflow_run_id = ? ORDER BY executed_at", (workflow_run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
