"""
IPC Server running inside the Server Guardian Daemon.
Listens for commands from the TUI Client over a secure Unix Domain Socket.
"""

import os
import socket
import threading
import json
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from server_guardian.config import GuardianConfig
from server_guardian.ipc.protocol import (
    create_response,
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


class IPCServer:
    def __init__(self, config: Optional[GuardianConfig] = None, handler_callbacks: Dict[str, Callable] = None):
        self.config = config or GuardianConfig.load()
        self.socket_path = self.config.socket_path
        self.handlers = handler_callbacks or {}
        self._server_sock: Optional[socket.socket] = None
        self._running = False
        self._accept_thread: Optional[threading.Thread] = None

    def start(self):
        """Start listening for IPC connections."""
        if self._running:
            return

        # Prepare socket path
        sock_p = Path(self.socket_path)
        sock_p.parent.mkdir(parents=True, exist_ok=True)
        if sock_p.exists():
            try:
                sock_p.unlink()
            except OSError:
                pass

        # Try Unix Domain Socket
        try:
            self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_sock.bind(str(sock_p))
            # Set strict file permissions (rw-------)
            try:
                sock_p.chmod(0o600)
            except OSError:
                pass
        except (AttributeError, OSError):
            # Fallback for systems lacking full AF_UNIX support: Localhost TCP on port 49152
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind(("127.0.0.1", 49152))

        self._server_sock.listen(10)
        self._running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, name="IPCAcceptLoop", daemon=True)
        self._accept_thread.start()

    def stop(self):
        """Stop IPC server and cleanup socket file."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        sock_p = Path(self.socket_path)
        if sock_p.exists():
            try:
                sock_p.unlink()
            except OSError:
                pass

    def _accept_loop(self):
        while self._running:
            try:
                client_sock, _ = self._server_sock.accept()
                t = threading.Thread(target=self._client_handler, args=(client_sock,), daemon=True)
                t.start()
            except Exception:
                break

    def _client_handler(self, client_sock: socket.socket):
        with client_sock:
            client_file = client_sock.makefile("rwb")
            while self._running:
                try:
                    line = client_file.readline()
                    if not line:
                        break

                    ok, req = parse_message(line)
                    if not ok:
                        client_file.write(create_response(False, error="Invalid JSON message"))
                        client_file.flush()
                        continue

                    action = req.get("action")
                    params = req.get("params", {})

                    resp_bytes = self._dispatch(action, params)
                    client_file.write(resp_bytes)
                    client_file.flush()
                except Exception as e:
                    break

    def _dispatch(self, action: str, params: dict) -> bytes:
        if action == CMD_PING:
            return create_response(True, data={"status": "pong", "version": "1.0.0"})

        handler = self.handlers.get(action)
        if not handler:
            return create_response(False, error=f"Unknown action: '{action}'")

        try:
            result = handler(params)
            return create_response(True, data=result)
        except Exception as e:
            return create_response(False, error=str(e))
