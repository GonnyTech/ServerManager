"""
IPC Protocol definitions and message helpers for Server Guardian.
"""

import json
from typing import Dict, Any, Tuple

# Supported IPC Commands
CMD_PING = "ping"
CMD_GET_METRICS = "get_metrics"
CMD_GET_CONTAINERS = "get_containers"
CMD_GET_PENDING_UPDATES = "get_pending_updates"
CMD_FORCE_UPDATE = "force_update"
CMD_TRIGGER_NIGHTLY = "trigger_nightly"
CMD_TEST_EMAIL = "test_email"
CMD_GET_CONFIG = "get_config"
CMD_SAVE_CONFIG = "save_config"


def create_request(action: str, params: dict = None) -> bytes:
    """Pack an action request with optional parameters as newline-terminated JSON."""
    payload = {
        "action": action,
        "params": params or {},
    }
    return (json.dumps(payload) + "\n").encode("utf-8")


def create_response(success: bool, data: Any = None, error: str = None) -> bytes:
    """Pack an IPC response payload."""
    payload = {
        "success": success,
        "data": data,
        "error": error,
    }
    return (json.dumps(payload) + "\n").encode("utf-8")


def parse_message(raw_bytes: bytes) -> Tuple[bool, dict]:
    """Parse raw bytes into a dictionary."""
    try:
        data = json.loads(raw_bytes.decode("utf-8").strip())
        return True, data
    except Exception as e:
        return False, {"error": str(e)}
