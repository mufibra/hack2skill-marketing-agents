"""
Pipeline Health Check — Capability 7 of OpenClaw Marketing Agent (P10).

Monitors P7's marketing data pipeline: API health, ETL status, data freshness,
and BigQuery connectivity.

Usage:
    python scripts/pipeline_health.py --output json
    python scripts/pipeline_health.py --api-url http://localhost:8000 --output text
"""

import sys
import os
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# P7 repo path
P7_ROOT = Path(r"C:\Users\ahmad\Downloads\Hack2Skill\marketing-data-pipeline")
if str(P7_ROOT) not in sys.path:
    sys.path.insert(0, str(P7_ROOT))

# Default API configuration
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_API_KEY = "default-dev-key"

# P7 local data paths
P7_RAW_DIR = P7_ROOT / "data" / "raw"
P7_PROCESSED_DIR = P7_ROOT / "data" / "processed"

# History
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "pipeline_health_history.json"

# Freshness thresholds (hours)
FRESHNESS_WARN = 24    # Warning if data older than 24h
FRESHNESS_CRIT = 72    # Critical if data older than 72h

# Expected pipeline tables
EXPECTED_TABLES = ["ga4_sessions", "ga4_funnel", "social_metrics", "crm_contacts"]


def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"checks": [], "last_check": None}


def save_history(history):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, default=str)


def check_api_health(api_url, api_key):
    """
    Check P7's FastAPI health endpoint.
    Returns health info dict and any errors.
    """
    import urllib.request
    import urllib.error

    health_result = {
        "api_reachable": False,
        "api_status": "unknown",
        "bigquery_connected": False,
        "tables_available": [],
        "api_response_time_ms": None,
        "error": None,
    }

    # Check health endpoint (no auth required)
    health_url = f"{api_url}/api/v1/health"
    start = datetime.now()
    try:
        req = urllib.request.Request(health_url, method="GET")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            data = json.loads(resp.read().decode("utf-8"))
            health_result["api_reachable"] = True
            health_result["api_status"] = data.get("status", "unknown")
            health_result["bigquery_connected"] = data.get("bigquery_connected", False)
            health_result["tables_available"] = data.get("tables_available", [])
            health_result["api_response_time_ms"] = round(elapsed, 1)
    except urllib.error.URLError as e:
        health_result["error"] = f"API unreachable: {e.reason}"
    except Exception as e:
        health_result["error"] = f"API check failed: {str(e)}"

    # Check pipeline status (requires auth)
    pipeline_result = {
        "pipeline_status_available": False,
        "tables": [],
        "total_tables": 0,
        "total_rows": 0,
        "error": None,
    }

    pipeline_url = f"{api_url}/api/v1/pipeline/status"
    try:
        req = urllib.request.Request(pipeline_url, method="GET")
        req.add_header("Accept", "application/json")
        req.add_header("X-API-Key", api_key)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            pipeline_result["pipeline_status_available"] = True
            pipeline_result["tables"] = data.get("tables", [])
            pipeline_result["total_tables"] = data.get("total_tables", 0)
            pipeline_result["total_rows"] = data.get("total_rows", 0)
    except urllib.error.URLError:
        pipeline_result["error"] = "Pipeline status endpoint unreachable"
    except Exception as e:
        pipeline_result["error"] = f"Pipeline status check failed: {str(e)}"

    return health_result, pipeline_result


def check_local_data_freshness():
    """
    Check local P7 data files for freshness.
    Falls back to file modification times when API is unavailable.
    """
    freshness = {
        "raw_data_files": [],
        "processed_data_files": [],
        "newest_raw_file": None,
        "newest_raw_age_hours": None,
        "pipeline_config_exists": False,
        "source_code_exists": False,
    }

    # Check raw data directory
    if P7_RAW_DIR.exists():
        for f in P7_RAW_DIR.iterdir():
            if f.is_file() and f.name != ".gitkeep":
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                age_hours = (datetime.now() - mtime).total_seconds() / 3600
                entry = {
                    "file": f.name,
                    "size_bytes": f.stat().st_size,
                    "last_modified": mtime.isoformat(),
                    "age_hours": round(age_hours, 1),
                }
                freshness["raw_data_files"].append(entry)

                if freshness["newest_raw_age_hours"] is None or age_hours < freshness["newest_raw_age_hours"]:
                    freshness["newest_raw_file"] = f.name
                    freshness["newest_raw_age_hours"] = round(age_hours, 1)

    # Check processed data directory
    if P7_PROCESSED_DIR.exists():
        for f in P7_PROCESSED_DIR.iterdir():
            if f.is_file() and f.name != ".gitkeep":
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                age_hours = (datetime.now() - mtime).total_seconds() / 3600
                freshness["processed_data_files"].append({
                    "file": f.name,
                    "size_bytes": f.stat().st_size,
                    "last_modified": mtime.isoformat(),
                    "age_hours": round(age_hours, 1),
                })

    # Check P7 source files exist
    freshness["pipeline_config_exists"] = (P7_ROOT / "src" / "pipeline.py").exists()
    freshness["source_code_exists"] = (P7_ROOT / "src" / "api" / "main.py").exists()

    return freshness


def check_pipeline_config():
    """
    Verify P7's pipeline configuration is valid.
    """
    config_check = {
        "pipeline_file_exists": False,
        "api_file_exists": False,
        "extractors_present": [],
        "transformers_present": [],
        "validators_present": [],
        "requirements_file": False,
        "config_file": False,
        "issues": [],
    }

    # Check core files
    config_check["pipeline_file_exists"] = (P7_ROOT / "src" / "pipeline.py").exists()
    config_check["api_file_exists"] = (P7_ROOT / "src" / "api" / "main.py").exists()
    config_check["requirements_file"] = (P7_ROOT / "requirements.txt").exists()
    config_check["config_file"] = (P7_ROOT / "config" / "settings.py").exists()

    # Check extractors
    extractors_dir = P7_ROOT / "src" / "extractors"
    if extractors_dir.exists():
        for f in extractors_dir.glob("*.py"):
            if f.name != "__init__.py":
                config_check["extractors_present"].append(f.stem)
    else:
        config_check["issues"].append("Extractors directory missing")

    # Check transformers
    transformers_dir = P7_ROOT / "src" / "transformers"
    if transformers_dir.exists():
        for f in transformers_dir.glob("*.py"):
            if f.name != "__init__.py":
                config_check["transformers_present"].append(f.stem)
    else:
        config_check["issues"].append("Transformers directory missing")

    # Check validators
    validators_dir = P7_ROOT / "src" / "validators"
    if validators_dir.exists():
        for f in validators_dir.glob("*.py"):
            if f.name != "__init__.py":
                config_check["validators_present"].append(f.stem)
    else:
        config_check["issues"].append("Validators directory missing")

    # Verify expected components
    expected_extractors = {"ga4_extractor", "social_extractor", "crm_extractor", "runner"}
    found_extractors = set(config_check["extractors_present"])
    missing = expected_extractors - found_extractors
    if missing:
        config_check["issues"].append(f"Missing extractors: {', '.join(missing)}")

    return config_check


def determine_overall_status(api_health, pipeline_status, freshness, config_check):
    """
    Determine overall pipeline health status.
    Returns: status (healthy/degraded/down), errors list, warnings list.
    """
    errors = []
    warnings = []

    # API checks
    if not api_health["api_reachable"]:
        warnings.append(f"API not reachable at configured URL — {api_health.get('error', 'connection refused')}")
    elif api_health["api_status"] == "degraded":
        warnings.append("API reports degraded status (BigQuery may be disconnected)")

    if api_health["api_reachable"] and not api_health["bigquery_connected"]:
        errors.append("BigQuery is disconnected — pipeline cannot load data")

    if api_health.get("api_response_time_ms") and api_health["api_response_time_ms"] > 5000:
        warnings.append(f"API response time is slow: {api_health['api_response_time_ms']}ms")

    # Pipeline status checks
    if pipeline_status["pipeline_status_available"]:
        if pipeline_status["total_tables"] == 0:
            errors.append("No tables found in BigQuery warehouse — pipeline may not have run")
        else:
            missing_tables = set(EXPECTED_TABLES) - {
                t.get("table_name", t) if isinstance(t, dict) else t
                for t in pipeline_status["tables"]
            }
            if missing_tables:
                warnings.append(f"Missing expected tables: {', '.join(missing_tables)}")

        # Check table freshness from pipeline status
        for table in pipeline_status["tables"]:
            if isinstance(table, dict) and table.get("last_modified"):
                try:
                    modified = datetime.fromisoformat(
                        table["last_modified"].replace("Z", "+00:00")
                    )
                    age_hours = (datetime.now(modified.tzinfo) - modified).total_seconds() / 3600
                    if age_hours > FRESHNESS_CRIT:
                        errors.append(
                            f"Table '{table['table_name']}' is {age_hours:.0f}h old (>72h threshold)"
                        )
                    elif age_hours > FRESHNESS_WARN:
                        warnings.append(
                            f"Table '{table['table_name']}' is {age_hours:.0f}h old (>24h threshold)"
                        )
                except (ValueError, TypeError):
                    pass

    # Local data freshness checks
    if freshness["newest_raw_age_hours"] is not None:
        if freshness["newest_raw_age_hours"] > FRESHNESS_CRIT:
            warnings.append(
                f"Newest local data is {freshness['newest_raw_age_hours']:.0f}h old"
            )

    # Config checks
    if not config_check["pipeline_file_exists"]:
        errors.append("Pipeline source file (pipeline.py) not found")
    if config_check["issues"]:
        for issue in config_check["issues"]:
            warnings.append(f"Config: {issue}")

    # Determine status
    if errors:
        status = "down"
    elif warnings:
        status = "degraded"
    else:
        status = "healthy"

    return status, errors, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Health Check — OpenClaw Capability 7"
    )
    parser.add_argument(
        "--output", type=str, choices=["json", "text"], default="text",
    )
    parser.add_argument(
        "--api-url", type=str, default=DEFAULT_API_URL,
        help=f"P7 API base URL (default: {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--api-key", type=str, default=DEFAULT_API_KEY,
        help="API key for authenticated endpoints",
    )
    args = parser.parse_args()

    # Run all checks
    api_health, pipeline_status = check_api_health(args.api_url, args.api_key)
    freshness = check_local_data_freshness()
    config_check = check_pipeline_config()

    # Determine overall status
    status, errors, warnings = determine_overall_status(
        api_health, pipeline_status, freshness, config_check
    )

    # Save to history
    history = load_history()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "api_reachable": api_health["api_reachable"],
        "error_count": len(errors),
        "warning_count": len(warnings),
    }
    history["checks"].append(entry)
    history["last_check"] = entry["timestamp"]
    if len(history["checks"]) > 100:
        history["checks"] = history["checks"][-100:]
    save_history(history)

    # Build output
    output = {
        "timestamp": datetime.now().isoformat(),
        "pipeline_status": status,
        "api_url": args.api_url,
        "api_health": api_health,
        "pipeline_tables": pipeline_status,
        "data_freshness": freshness,
        "pipeline_config": config_check,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "checks_in_history": len(history["checks"]),
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, default=str))
    else:
        _print_text(output)


def _print_text(output):
    """Render pipeline health as formatted text."""
    status = output["pipeline_status"]
    status_icons = {"healthy": "[OK]", "degraded": "[WARN]", "down": "[FAIL]"}
    icon = status_icons.get(status, "[?]")

    print("=" * 60)
    print(f"PIPELINE HEALTH CHECK  {icon} {status.upper()}")
    print(f"Checked: {output['api_url']}")
    print("=" * 60)

    # API Health
    api = output["api_health"]
    print(f"\n  API Health:")
    if api["api_reachable"]:
        print(f"    Status: {api['api_status']}  |  Response: {api['api_response_time_ms']}ms")
        print(f"    BigQuery: {'connected' if api['bigquery_connected'] else 'DISCONNECTED'}")
        if api["tables_available"]:
            print(f"    Tables: {', '.join(api['tables_available'])}")
    else:
        print(f"    API NOT REACHABLE — {api.get('error', 'unknown error')}")

    # Pipeline Tables
    pt = output["pipeline_tables"]
    if pt["pipeline_status_available"]:
        print(f"\n  Pipeline Tables ({pt['total_tables']}):")
        print(f"    Total rows: {pt['total_rows']:,}")
        for table in pt["tables"]:
            name = table.get("table_name", table) if isinstance(table, dict) else table
            rows = table.get("row_count", "?") if isinstance(table, dict) else "?"
            modified = table.get("last_modified", "?") if isinstance(table, dict) else "?"
            print(f"    {name:25s}  rows: {rows:>8}  modified: {modified}")

    # Data Freshness
    fresh = output["data_freshness"]
    print(f"\n  Local Data Freshness:")
    if fresh["raw_data_files"]:
        for f in fresh["raw_data_files"]:
            age_icon = "[OK]" if f["age_hours"] < FRESHNESS_WARN else (
                "[WARN]" if f["age_hours"] < FRESHNESS_CRIT else "[OLD]"
            )
            print(f"    {age_icon} {f['file']:25s}  {f['size_bytes']:>8} bytes  "
                  f"age: {f['age_hours']:.0f}h")
    else:
        print("    No raw data files found")

    if fresh["processed_data_files"]:
        for f in fresh["processed_data_files"]:
            print(f"    {f['file']:25s}  {f['size_bytes']:>8} bytes  "
                  f"age: {f['age_hours']:.0f}h")

    # Config
    cfg = output["pipeline_config"]
    print(f"\n  Pipeline Config:")
    print(f"    Pipeline code: {'OK' if cfg['pipeline_file_exists'] else 'MISSING'}")
    print(f"    API code:      {'OK' if cfg['api_file_exists'] else 'MISSING'}")
    print(f"    Extractors:    {', '.join(cfg['extractors_present']) or 'NONE'}")
    print(f"    Transformers:  {', '.join(cfg['transformers_present']) or 'NONE'}")

    # Errors and Warnings
    if output["errors"]:
        print(f"\n  Errors ({output['error_count']}):")
        for e in output["errors"]:
            print(f"    [FAIL] {e}")

    if output["warnings"]:
        print(f"\n  Warnings ({output['warning_count']}):")
        for w in output["warnings"]:
            print(f"    [WARN] {w}")

    if not output["errors"] and not output["warnings"]:
        print(f"\n  No errors or warnings detected.")


if __name__ == "__main__":
    main()
