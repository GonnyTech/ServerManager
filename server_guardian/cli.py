"""
Command-Line Interface for Server Guardian.
Provides command routing for TUI dashboard, Daemon, and configuration setup.
"""

import sys
import argparse
import getpass

from server_guardian.config import GuardianConfig
from server_guardian.security import get_or_create_key, get_config_dir
from server_guardian.ipc.client import IPCClient
from server_guardian.daemon import run_daemon
from server_guardian.tui.app import run_tui


def interactive_configure():
    """Interactive command to setup encryption and initial credentials."""
    print("=" * 60)
    print(" Server Guardian v1.0 - Interactive Configuration Setup")
    print("=" * 60)

    cfg_dir = get_config_dir()
    print(f"[i] Secure configuration directory: {cfg_dir}")
    key = get_or_create_key()
    print("[✓] Local symmetric encryption key active and secured (chmod 0600).")

    config = GuardianConfig.load()

    print("\n--- 1. Administrative Privileges ---")
    sys_pw = getpass.getpass("Enter system sudo password (hidden, leave empty if passwordless sudo): ")
    if sys_pw:
        config.set_system_password(sys_pw)
        print("[✓] System password securely encrypted.")

    print("\n--- 2. Dual-Recipient Email Notifications ---")
    primary = input(f"Primary Recipient Email [{config.smtp.primary_email}]: ").strip()
    if primary:
        config.smtp.primary_email = primary

    backup = input(f"Backup Recipient Email [{config.smtp.backup_email}]: ").strip()
    if backup:
        config.smtp.backup_email = backup

    host = input(f"SMTP Server Host [{config.smtp.host}]: ").strip()
    if host:
        config.smtp.host = host

    port_in = input(f"SMTP Port [{config.smtp.port}]: ").strip()
    if port_in and port_in.isdigit():
        config.smtp.port = int(port_in)

    user = input(f"SMTP Username [{config.smtp.username}]: ").strip()
    if user:
        config.smtp.username = user

    smtp_pw = getpass.getpass("SMTP Password / App Token (hidden, leave empty to keep): ")
    if smtp_pw:
        config.set_smtp_password(smtp_pw)
        print("[✓] SMTP credentials encrypted.")

    print("\n--- 3. Agentic LLM Setup (Optional) ---")
    provider = input(f"LLM Provider (openai/anthropic/gemini) [{config.llm.provider}]: ").strip()
    if provider:
        config.llm.provider = provider

    llm_key = getpass.getpass("LLM API Key (hidden, leave empty to keep): ")
    if llm_key:
        config.set_llm_api_key(llm_key)
        print("[✓] LLM API key encrypted.")

    config.save()
    print("\n[✓] Configuration saved successfully to secure storage!")


def check_status():
    """Check if the background daemon is reachable via IPC."""
    client = IPCClient()
    ok, data = client.send_command("ping")
    if ok:
        print("[✓] Server Guardian Daemon is RUNNING and responding via IPC.")
        print(f"    Daemon Details: {data}")
    else:
        print(f"[✗] Server Guardian Daemon is NOT responding: {data}")
        print("    You can start it with: sudo systemctl start server-guardian")


def main():
    parser = argparse.ArgumentParser(
        description="Server Guardian - Semiautomatic Server Management System"
    )
    subparsers = parser.add_subparsers(dest="command")

    # daemon
    subparsers.add_parser("daemon", help="Run the background service (called by systemd)")

    # configure
    subparsers.add_parser("configure", help="Run interactive initial configuration setup")

    # status
    subparsers.add_parser("status", help="Check status of the background daemon")

    # trigger-nightly
    subparsers.add_parser("trigger-nightly", help="Manually execute scheduled 02:00 maintenance tasks")

    # tui (default)
    subparsers.add_parser("tui", help="Launch the interactive terminal dashboard (default)")

    args = parser.parse_args()

    if args.command == "daemon":
        run_daemon()
    elif args.command == "configure":
        interactive_configure()
    elif args.command == "status":
        check_status()
    elif args.command == "trigger-nightly":
        client = IPCClient()
        ok, res = client.trigger_nightly()
        if ok:
            print("[✓] Nightly tasks triggered successfully:")
            print(res)
        else:
            print(f"[✗] Failed to trigger tasks: {res}")
    else:
        # Default action: launch TUI
        run_tui()


if __name__ == "__main__":
    main()
