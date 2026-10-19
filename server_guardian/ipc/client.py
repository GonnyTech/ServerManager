"""
IPC Client for Server Guardian.
Used by the TUI Dashboard and CLI to query and command the background Daemon.
"""

import socket
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from server_guardian.config import GuardianConfig
from server_guardian.ipc.protocol import (
    create_request,
    parse_message,
    CMD_PING,
    CMD_GET_METRICS,
    CMD_GET_CONTAINERS,
    CMD_GET_PENDING_UPDATES,
    CMD_FORCE_UPDATE,
    CMD_TRIGGER_NIGHTLY,
    CMD_TEST_EMAIL,
    CMD_GET_CONFIG,
    CMD_SAVE_CONFIG,
)


class IPCClient:
    def __init__(self, config: Optional[GuardianConfig] = None):
        self.config = config or GuardianConfig.load()
        self.socket_path = self.config.socket_path

    def _connect(self) -> socket.socket:
        sock_p = Path(self.socket_path)
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect(str(sock_p))
            return sock
        except (AttributeError, OSError):
            # Fallback for systems/environments using localhost TCP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect(("127.0.0.1", 49152))
            return sock

    def send_command(self, action: str, params: dict = None) -> Tuple[bool, Any]:
        """
        Send a command to the Daemon and await response.
        Returns (success: bool, data_or_error_message).
        """
        try:
            with self._connect() as sock:
                file_io = sock.makefile("rwb")
                req_bytes = create_request(action, params)
                file_io.write(req_bytes)
                file_io.flush()

                line = file_io.readline()
                if not line:
                    return False, "Daemon closed connection unexpectedly."

                ok, resp = parse_message(line)
                if not ok:
                    return False, "Failed to parse daemon response."

                if resp.get("success"):
                    return True, resp.get("data")
                else:
                    return False, resp.get("error", "Unknown daemon error")

        except (ConnectionRefusedError, FileNotFoundError):
            return False, "Cannot connect to Server Guardian Daemon. Is the service running?"
        except Exception as e:
            return False, f"IPC Error: {str(e)}"

    def is_daemon_running(self) -> bool:
        ok, _ = self.send_command(CMD_PING)
        return ok

    def get_metrics(self) -> Tuple[bool, Any]:
        return self.send_command(CMD_GET_METRICS)

    def get_containers(self) -> Tuple[bool, Any]:
        return self.send_command(CMD_GET_CONTAINERS)

    def get_pending_updates(self) -> Tuple[bool, Any]:
        return self.send_command(CMD_GET_PENDING_UPDATES)

    def force_update(self, container_id: str) -> Tuple[bool, Any]:
        return self.send_command(CMD_FORCE_UPDATE, {"container_id": container_id})

    def trigger_nightly(self) -> Tuple[bool, Any]:
        return self.send_command(CMD_TRIGGER_NIGHTLY)

    def test_email(self) -> Tuple[bool, Any]:
        return self.send_command(CMD_TEST_EMAIL)

    def get_config(self) -> Tuple[bool, Any]:
        return self.send_command(CMD_GET_CONFIG)

    def save_config(self, config_dict: dict) -> Tuple[bool, Any]:
        return self.send_command(CMD_SAVE_CONFIG, {"config": config_dict})
