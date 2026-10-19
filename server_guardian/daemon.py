"""
Server Guardian Daemon.
Main background service running continuously under systemd.
"""

import signal
import sys
import time
import logging
from typing import Dict, Any, List

from server_guardian.config import GuardianConfig
from server_guardian.mailer import Mailer
from server_guardian.core.metrics import get_system_metrics
from server_guardian.core.system_updater import SystemUpdater
from server_guardian.core.docker_manager import DockerManager
from server_guardian.core.scheduler import GuardianScheduler
from server_guardian.ipc.server import IPCServer
from server_guardian.ipc.protocol import (
    CMD_GET_METRICS,
    CMD_GET_CONTAINERS,
    CMD_GET_PENDING_UPDATES,
    CMD_FORCE_UPDATE,
    CMD_TRIGGER_NIGHTLY,
    CMD_TEST_EMAIL,
    CMD_GET_CONFIG,
    CMD_SAVE_CONFIG,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [GuardianDaemon] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("GuardianDaemon")


class GuardianDaemon:
    def __init__(self):
        self.config = GuardianConfig.load()
        self.mailer = Mailer(self.config)
        self.system_updater = SystemUpdater(self.config)
        self.docker_manager = DockerManager(self.config)

        self.scheduler = GuardianScheduler(
            config=self.config,
            system_updater=self.system_updater,
            docker_manager=self.docker_manager,
            on_task_completed=self._on_scheduler_task_done,
        )

        # Metrics buffer (last 60 samples, 1 per 2 seconds)
        self.latest_metrics: Dict[str, Any] = {}
        self.metrics_history: List[Dict[str, Any]] = []

        self._running = False

        # IPC Server setup
        handlers = {
            CMD_GET_METRICS: self._handle_get_metrics,
            CMD_GET_CONTAINERS: self._handle_get_containers,
            CMD_GET_PENDING_UPDATES: self._handle_get_pending_updates,
            CMD_FORCE_UPDATE: self._handle_force_update,
            CMD_TRIGGER_NIGHTLY: self._handle_trigger_nightly,
            CMD_TEST_EMAIL: self._handle_test_email,
            CMD_GET_CONFIG: self._handle_get_config,
            CMD_SAVE_CONFIG: self._handle_save_config,
        }
        self.ipc_server = IPCServer(self.config, handlers)

    def _on_scheduler_task_done(self, task_name: str, results: dict):
        logger.info(f"Scheduled task '{task_name}' executed. Results: {results}")

    # IPC Handlers

    def _handle_get_metrics(self, params: dict) -> dict:
        return {
            "current": self.latest_metrics or get_system_metrics(),
            "history_count": len(self.metrics_history),
        }

    def _handle_get_containers(self, params: dict) -> list:
        return self.docker_manager.list_containers()

    def _handle_get_pending_updates(self, params: dict) -> list:
        return self.docker_manager.get_pending_updates()

    def _handle_force_update(self, params: dict) -> dict:
        container_id = params.get("container_id")
        if not container_id:
            raise ValueError("container_id parameter is required")
        ok, msg = self.docker_manager.force_manual_update(container_id)
        return {"success": ok, "message": msg}

    def _handle_trigger_nightly(self, params: dict) -> dict:
        logger.info("Manual trigger of nightly 02:00 tasks requested via IPC.")
        res = self.scheduler.run_scheduled_tasks()
        return res

    def _handle_test_email(self, params: dict) -> dict:
        ok, msg = self.mailer.notify_test_email()
        return {"success": ok, "message": msg}

    def _handle_get_config(self, params: dict) -> dict:
        return {
            "smtp_host": self.config.smtp.host,
            "smtp_port": self.config.smtp.port,
            "smtp_username": self.config.smtp.username,
            "smtp_has_password": bool(self.config.smtp.password_encrypted),
            "primary_email": self.config.smtp.primary_email,
            "backup_email": self.config.smtp.backup_email,
            "has_system_password": bool(self.config.system_password_encrypted),
            "llm_provider": self.config.llm.provider,
            "has_llm_key": bool(self.config.llm.api_key_encrypted),
            "schedule_hour": self.config.schedule.hour,
            "schedule_minute": self.config.schedule.minute,
        }

    def _handle_save_config(self, params: dict) -> dict:
        cfg_data = params.get("config", {})
        if "smtp_host" in cfg_data:
            self.config.smtp.host = str(cfg_data["smtp_host"]).strip()
        if "smtp_port" in cfg_data:
            self.config.smtp.port = int(cfg_data["smtp_port"])
        if "smtp_username" in cfg_data:
            self.config.smtp.username = str(cfg_data["smtp_username"]).strip()
        if "smtp_password" in cfg_data and cfg_data["smtp_password"]:
            self.config.set_smtp_password(cfg_data["smtp_password"])
        if "primary_email" in cfg_data:
            self.config.smtp.primary_email = str(cfg_data["primary_email"]).strip()
        if "backup_email" in cfg_data:
            self.config.smtp.backup_email = str(cfg_data["backup_email"]).strip()

        if "system_password" in cfg_data and cfg_data["system_password"]:
            self.config.set_system_password(cfg_data["system_password"])

        if "llm_api_key" in cfg_data and cfg_data["llm_api_key"]:
            self.config.set_llm_api_key(cfg_data["llm_api_key"])
        if "llm_provider" in cfg_data:
            self.config.llm.provider = str(cfg_data["llm_provider"]).strip()

        self.config.save()
        logger.info("Configuration updated and saved via IPC.")
        return {"success": True, "message": "Configuration saved successfully."}

    def start(self):
        """Start daemon components."""
        logger.info("Starting Server Guardian Daemon v1.0...")
        self._running = True

        # Register signals
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Start IPC Server
        self.ipc_server.start()
        logger.info(f"IPC Server listening on socket {self.config.socket_path}")

        # Start Scheduler
        self.scheduler.start()
        logger.info(f"Nightly scheduler active (target time: {self.config.schedule.hour:02d}:{self.config.schedule.minute:02d})")

        # Main metrics gathering loop
        try:
            while self._running:
                try:
                    metrics = get_system_metrics()
                    self.latest_metrics = metrics
                    self.metrics_history.append(metrics)
                    if len(self.metrics_history) > 60:
                        self.metrics_history.pop(0)
                except Exception as e:
                    logger.error(f"Error sampling metrics: {e}")

                time.sleep(2.0)
        except KeyboardInterrupt:
            self.stop()

    def _signal_handler(self, signum, frame):
        logger.info(f"Received termination signal ({signum}), shutting down cleanly...")
        self.stop()
        sys.exit(0)

    def stop(self):
        self._running = False
        self.scheduler.stop()
        self.ipc_server.stop()
        logger.info("Server Guardian Daemon stopped.")


def run_daemon():
    daemon = GuardianDaemon()
    daemon.start()


if __name__ == "__main__":
    run_daemon()
