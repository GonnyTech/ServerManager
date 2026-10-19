"""
Task Scheduler for Server Guardian.
Triggers nightly system upgrade (apt) and Docker container checks at 02:00 every night.
"""

import threading
import time
from datetime import datetime
from typing import Optional, Callable

from server_guardian.config import GuardianConfig
from server_guardian.core.system_updater import SystemUpdater
from server_guardian.core.docker_manager import DockerManager


class GuardianScheduler:
    def __init__(
        self,
        config: Optional[GuardianConfig] = None,
        system_updater: Optional[SystemUpdater] = None,
        docker_manager: Optional[DockerManager] = None,
        on_task_completed: Optional[Callable[[str, dict], None]] = None,
    ):
        self.config = config or GuardianConfig.load()
        self.system_updater = system_updater or SystemUpdater(self.config)
        self.docker_manager = docker_manager or DockerManager(self.config)
        self.on_task_completed = on_task_completed

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_execution_date: Optional[str] = None

    def start(self):
        """Start the background scheduler thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._scheduler_loop, name="GuardianSchedulerThread", daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the background scheduler thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _scheduler_loop(self):
        """Check current time every 20 seconds and trigger tasks at scheduled time."""
        while self._running:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            target_hour = self.config.schedule.hour
            target_min = self.config.schedule.minute

            if (
                now.hour == target_hour
                and now.minute == target_min
                and self._last_execution_date != today_str
            ):
                self._last_execution_date = today_str
                self.run_scheduled_tasks()

            time.sleep(20)

    def run_scheduled_tasks(self) -> dict:
        """
        Execute the nightly 02:00 sequence:
        1. System apt upgrade.
        2. Docker inspection and updates.
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "apt": None,
            "docker": None,
        }

        # 1. System update
        try:
            apt_ok, apt_out = self.system_updater.run_apt_update_and_upgrade()
            results["apt"] = {"success": apt_ok, "output": apt_out[:1000]}
        except Exception as e:
            results["apt"] = {"success": False, "output": str(e)}

        # 2. Docker container check and auto-updates
        try:
            docker_res = self.docker_manager.run_nightly_docker_checks()
            results["docker"] = docker_res
        except Exception as e:
            results["docker"] = {"status": "error", "message": str(e)}

        if self.on_task_completed:
            self.on_task_completed("nightly_tasks", results)

        return results
