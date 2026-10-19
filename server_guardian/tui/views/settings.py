"""
Settings and Configuration View for Server Guardian.
Handles SMTP parameters, dual email recipients, system password, and LLM API keys.
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, Input, Button


class SettingsView(Container):
    """View allowing dynamic editing of emails, SMTP, system passwords, and LLM keys."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="settings-container"):
            # Section: Email & SMTP
            yield Static("1. Email & SMTP Notifications (Dual Recipient)", classes="section-title")

            yield Static("Primary Recipient Email:", classes="form-label")
            yield Input(id="input_primary_email", placeholder="admin@example.com")

            yield Static("Backup Recipient Email:", classes="form-label")
            yield Input(id="input_backup_email", placeholder="backup-alerts@example.com")

            with Horizontal(classes="form-row"):
                with Vertical():
                    yield Static("SMTP Host:", classes="form-label")
                    yield Input(id="input_smtp_host", placeholder="smtp.gmail.com")
                with Vertical():
                    yield Static("SMTP Port:", classes="form-label")
                    yield Input(id="input_smtp_port", placeholder="587")

            with Horizontal(classes="form-row"):
                with Vertical():
                    yield Static("SMTP Username:", classes="form-label")
                    yield Input(id="input_smtp_user", placeholder="username@example.com")
                with Vertical():
                    yield Static("SMTP Password / App Token:", classes="form-label")
                    yield Input(id="input_smtp_pass", placeholder="Enter new password (optional)", password=True)

            # Section: System Security
            yield Static("2. Administrative System Password (for scheduled apt upgrades)", classes="section-title")
            yield Static("System sudo Password (stored locally with symmetric encryption):", classes="form-label")
            yield Input(id="input_sys_pass", placeholder="Enter password if user requires sudo prompt", password=True)

            # Section: Agentic LLM Setup
            yield Static("3. Agentic LLM API Integration", classes="section-title")
            with Horizontal(classes="form-row"):
                with Vertical():
                    yield Static("LLM Provider:", classes="form-label")
                    yield Input(id="input_llm_provider", placeholder="openai / anthropic / gemini")
                with Vertical():
                    yield Static("API Key:", classes="form-label")
                    yield Input(id="input_llm_key", placeholder="sk-...", password=True)

            # Actions Row
            with Horizontal(classes="btn-row"):
                yield Button("Save Configuration", id="btn_save_config", classes="btn-success")
                yield Button("Send Test Email", id="btn_test_email")
                yield Button("Trigger 02:00 Tasks Now", id="btn_trigger_nightly", classes="btn-warning")

            yield Static("Settings Status: Ready", id="settings_status", classes="metric-sub")

    def load_data(self, data: dict):
        if not data:
            return

        self.query_one("#input_primary_email", Input).value = data.get("primary_email") or ""
        self.query_one("#input_backup_email", Input).value = data.get("backup_email") or ""
        self.query_one("#input_smtp_host", Input).value = data.get("smtp_host") or ""
        self.query_one("#input_smtp_port", Input).value = str(data.get("smtp_port") or 587)
        self.query_one("#input_smtp_user", Input).value = data.get("smtp_username") or ""
        self.query_one("#input_llm_provider", Input).value = data.get("llm_provider") or "generic"

        # Show indicator if passwords exist
        has_sys_pw = data.get("has_system_password")
        if has_sys_pw:
            self.query_one("#input_sys_pass", Input).placeholder = "Password already saved (leave empty to keep)"

        has_smtp_pw = data.get("smtp_has_password")
        if has_smtp_pw:
            self.query_one("#input_smtp_pass", Input).placeholder = "Password already saved (leave empty to keep)"

        has_llm_key = data.get("has_llm_key")
        if has_llm_key:
            self.query_one("#input_llm_key", Input).placeholder = "API Key already saved (leave empty to keep)"

    def get_form_payload(self) -> dict:
        port_str = self.query_one("#input_smtp_port", Input).value.strip()
        port = int(port_str) if port_str.isdigit() else 587

        payload = {
            "primary_email": self.query_one("#input_primary_email", Input).value.strip(),
            "backup_email": self.query_one("#input_backup_email", Input).value.strip(),
            "smtp_host": self.query_one("#input_smtp_host", Input).value.strip(),
            "smtp_port": port,
            "smtp_username": self.query_one("#input_smtp_user", Input).value.strip(),
            "llm_provider": self.query_one("#input_llm_provider", Input).value.strip(),
        }

        smtp_pw = self.query_one("#input_smtp_pass", Input).value.strip()
        if smtp_pw:
            payload["smtp_password"] = smtp_pw

        sys_pw = self.query_one("#input_sys_pass", Input).value.strip()
        if sys_pw:
            payload["system_password"] = sys_pw

        llm_key = self.query_one("#input_llm_key", Input).value.strip()
        if llm_key:
            payload["llm_api_key"] = llm_key

        return payload
