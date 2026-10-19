"""
Email Notification Service for Server Guardian.
Handles simultaneous dual-recipient email delivery over SMTP using natural US English messaging.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Tuple, Optional
import socket

from server_guardian.config import GuardianConfig


class Mailer:
    def __init__(self, config: Optional[GuardianConfig] = None):
        self.config = config or GuardianConfig.load()

    def get_recipients(self) -> List[str]:
        """Return unique configured recipient email addresses (primary and backup)."""
        recipients = []
        if self.config.smtp.primary_email and self.config.smtp.primary_email.strip():
            recipients.append(self.config.smtp.primary_email.strip())
        if self.config.smtp.backup_email and self.config.smtp.backup_email.strip():
            addr = self.config.smtp.backup_email.strip()
            if addr not in recipients:
                recipients.append(addr)
        return recipients

    def send_notification(self, subject: str, body_text: str) -> Tuple[bool, str]:
        """
        Send an email notification simultaneously to all configured recipients.
        Returns (success: bool, status_message: str).
        """
        recipients = self.get_recipients()
        if not recipients:
            return False, "No recipient email addresses configured (primary/backup are empty)."

        smtp_cfg = self.config.smtp
        if not smtp_cfg.host:
            return False, "SMTP host not configured."

        hostname = socket.gethostname()
        full_subject = f"[Server Guardian - {hostname}] {subject}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = full_subject
        msg["From"] = smtp_cfg.username or f"server-guardian@{hostname}"
        msg["To"] = ", ".join(recipients)

        # Plain text natural language body
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        try:
            password = self.config.get_smtp_password()
            if smtp_cfg.use_ssl:
                server = smtplib.SMTP_SSL(smtp_cfg.host, smtp_cfg.port, timeout=20)
            else:
                server = smtplib.SMTP(smtp_cfg.host, smtp_cfg.port, timeout=20)
                if smtp_cfg.use_tls:
                    server.starttls()

            if smtp_cfg.username and password:
                server.login(smtp_cfg.username, password)

            server.sendmail(msg["From"], recipients, msg.as_string())
            server.quit()
            return True, f"Notification sent successfully to {len(recipients)} recipient(s)."

        except Exception as e:
            return False, f"Failed to send email notification: {str(e)}"

    # Natural Language US English Email Templates

    def notify_system_update_failure(self, error_details: str) -> Tuple[bool, str]:
        """Send notification when Ubuntu apt update/upgrade fails."""
        subject = "Action Required: System Package Upgrade Failed"
        body = (
            "Hello System Administrator,\n\n"
            "This is an automated alert from Server Guardian.\n\n"
            "During the scheduled nightly maintenance at 02:00, the automatic Ubuntu "
            "package update ('apt') encountered an unexpected failure and could not complete.\n\n"
            "Diagnostic output summary:\n"
            "--------------------------------------------------\n"
            f"{error_details.strip()}\n"
            "--------------------------------------------------\n\n"
            "Please log into the server and review package manager dependencies to resolve any locks or issues.\n\n"
            "Best regards,\n"
            "Server Guardian Automated System"
        )
        return self.send_notification(subject, body)

    def notify_docker_update_failure(
        self, container_name: str, current_version: str, target_version: str, error_details: str
    ) -> Tuple[bool, str]:
        """Send notification when automatic container upgrade fails."""
        subject = f"Alert: Failed to Update Container '{container_name}'"
        body = (
            "Hello System Administrator,\n\n"
            "This is an automated alert from Server Guardian.\n\n"
            f"The scheduled automatic upgrade for Docker container '{container_name}' failed.\n\n"
            f"Container Name  : {container_name}\n"
            f"Current Release : {current_version}\n"
            f"Target Release  : {target_version}\n\n"
            "Error details:\n"
            "--------------------------------------------------\n"
            f"{error_details.strip()}\n"
            "--------------------------------------------------\n\n"
            "The previous container state has been preserved. Please inspect the container logs "
            "or review image compatibility.\n\n"
            "Best regards,\n"
            "Server Guardian Automated System"
        )
        return self.send_notification(subject, body)

    def notify_docker_incremental_pending(
        self, container_name: str, current_version: str, new_version: str
    ) -> Tuple[bool, str]:
        """Send notification when an incremental patch release is detected and blocked."""
        subject = f"Review Needed: Incremental Patch Pending for '{container_name}'"
        body = (
            "Hello System Administrator,\n\n"
            "This is an informational notice from Server Guardian.\n\n"
            f"A new incremental/patch release has been detected for Docker container '{container_name}'.\n\n"
            f"Container Name       : {container_name}\n"
            f"Active Release       : {current_version}\n"
            f"Detected Patch Version: {new_version}\n\n"
            "As defined by your policy, automatic upgrades are halted for incremental releases to avoid "
            "unintended side-effects.\n\n"
            "This update has been queued as 'Pending Approval'. You can review and trigger the manual update "
            "at any time by opening the Server Guardian Terminal Dashboard (TUI) and accessing the Updates tab.\n\n"
            "Best regards,\n"
            "Server Guardian Automated System"
        )
        return self.send_notification(subject, body)

    def notify_docker_latest_digest_pending(
        self, container_name: str, image_name: str, current_digest: str, new_digest: str
    ) -> Tuple[bool, str]:
        """Send notification when a container tagged :latest has a newer upstream digest."""
        subject = f"Review Needed: New Upstream Image for '{container_name}' (:latest)"
        body = (
            "Hello System Administrator,\n\n"
            "This is an informational notice from Server Guardian.\n\n"
            f"Container '{container_name}' uses the fixed ':latest' tag, and a new upstream image "
            "digest has been detected in the registry.\n\n"
            f"Container Name : {container_name}\n"
            f"Image          : {image_name}\n"
            f"Current Digest : {current_digest[:19]}...\n"
            f"Remote Digest  : {new_digest[:19]}...\n\n"
            "In accordance with your policy, automatic deployment is blocked for ':latest' containers. "
            "The update has been placed in the 'Pending Approval' queue.\n\n"
            "You can review and deploy this update manually via the Server Guardian TUI dashboard.\n\n"
            "Best regards,\n"
            "Server Guardian Automated System"
        )
        return self.send_notification(subject, body)

    def notify_test_email(self) -> Tuple[bool, str]:
        """Send a test email to verify SMTP credentials and connectivity."""
        subject = "Test Message - Server Guardian SMTP Verification"
        body = (
            "Hello,\n\n"
            "This is a confirmation test message from Server Guardian.\n\n"
            "If you are reading this email, your SMTP settings and recipient addresses "
            "are properly configured and operational.\n\n"
            "Best regards,\n"
            "Server Guardian"
        )
        return self.send_notification(subject, body)
