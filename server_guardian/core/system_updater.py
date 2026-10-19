"""
System Updater module for Ubuntu Linux (apt).
Handles non-interactive package updates with smart privilege elevation.
"""

import os
import subprocess
from typing import Tuple, Optional

from server_guardian.config import GuardianConfig
from server_guardian.mailer import Mailer


class SystemUpdater:
    def __init__(self, config: Optional[GuardianConfig] = None):
        self.config = config or GuardianConfig.load()
        self.mailer = Mailer(self.config)

    def _execute_privileged_cmd(self, cmd_args: list[str]) -> Tuple[bool, str]:
        """
        Execute command with necessary administrative privileges:
        1. If running as root (UID 0), execute directly.
        2. Test if passwordless sudo works (`sudo -n ...`).
        3. If password is required, decrypt saved password and pipe to `sudo -S`.
        """
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        env["NEEDRESTART_MODE"] = "a"  # Avoid interactive needrestart prompts

        # If already root
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            try:
                proc = subprocess.run(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    timeout=900,  # 15 min max
                )
                return proc.returncode == 0, proc.stdout
            except Exception as e:
                return False, str(e)

        # Non-root user: test passwordless sudo first
        test_proc = subprocess.run(
            ["sudo", "-n", "true"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if test_proc.returncode == 0:
            # Sudo works without password
            try:
                full_cmd = ["sudo", "-E"] + cmd_args
                proc = subprocess.run(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    timeout=900,
                )
                return proc.returncode == 0, proc.stdout
            except Exception as e:
                return False, str(e)

        # Sudo requires password: use securely decrypted password
        password = self.config.get_system_password()
        if not password:
            return False, "Sudo requires password, but no system password is saved in Guardian config."

        try:
            full_cmd = ["sudo", "-S", "-p", "", "-E"] + cmd_args
            proc = subprocess.run(
                full_cmd,
                input=f"{password}\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                timeout=900,
            )
            return proc.returncode == 0, proc.stdout
        except Exception as e:
            return False, str(e)

    def run_apt_update_and_upgrade(self) -> Tuple[bool, str]:
        """
        Execute `apt-get update` and `apt-get dist-upgrade -y --autoremove`.
        Sends notification email on failure.
        """
        # Step 1: apt-get update
        ok, update_out = self._execute_privileged_cmd(["apt-get", "update", "-y"])
        if not ok:
            err_msg = f"apt-get update failed:\n{update_out}"
            self.mailer.notify_system_update_failure(err_msg)
            return False, err_msg

        # Step 2: apt-get dist-upgrade
        ok, upgrade_out = self._execute_privileged_cmd(
            ["apt-get", "-o", "Dpkg::Options::=--force-confold", "dist-upgrade", "-y"]
        )
        if not ok:
            err_msg = f"apt-get upgrade failed:\n{upgrade_out}"
            self.mailer.notify_system_update_failure(err_msg)
            return False, err_msg

        # Step 3: apt-get autoremove -y (cleanup)
        self._execute_privileged_cmd(["apt-get", "autoremove", "-y"])

        combined_output = f"Update Output:\n{update_out}\n\nUpgrade Output:\n{upgrade_out}"
        return True, combined_output
