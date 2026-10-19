"""
Main Textual Application for Server Guardian.
Provides an interactive htop-like dashboard and server control console.
"""

from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static, Button
from textual.containers import Container
from textual.binding import Binding

from server_guardian.ipc.client import IPCClient
from server_guardian.tui.views.monitor import MonitorView
from server_guardian.tui.views.containers import ContainersView
from server_guardian.tui.views.updates import UpdatesView
from server_guardian.tui.views.settings import SettingsView

CSS_PATH = Path(__file__).parent / "styles.tcss"


class ServerGuardianApp(App):
    """Server Guardian TUI Application."""

    TITLE = "Server Guardian - v1.0"
    SUB_TITLE = "Ubuntu Server & Container Management"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("1", "switch_tab('tab_monitor')", "Monitor", show=True),
        Binding("2", "switch_tab('tab_containers')", "Docker", show=True),
        Binding("3", "switch_tab('tab_updates')", "Updates", show=True),
        Binding("4", "switch_tab('tab_settings')", "Settings", show=True),
        Binding("r", "refresh_active_view", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.ipc = IPCClient()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with TabbedContent(initial="tab_monitor", id="main_tabs"):
            with TabPane("1: System Monitor", id="tab_monitor"):
                yield MonitorView(id="view_monitor")
            with TabPane("2: Docker Containers", id="tab_containers"):
                yield ContainersView(id="view_containers")
            with TabPane("3: Pending Updates", id="tab_updates"):
                yield UpdatesView(id="view_updates")
            with TabPane("4: Settings & Credentials", id="tab_settings"):
                yield SettingsView(id="view_settings")

        yield Static("Daemon Status: Checking connection...", id="status_bar")
        yield Footer()

    def on_mount(self) -> None:
        """Called when UI is initialized. Setup recurring timer."""
        self.set_interval(2.0, self._periodic_tick)
        self._load_all_views()

    def action_switch_tab(self, tab_id: str) -> None:
        tabs = self.query_one("#main_tabs", TabbedContent)
        tabs.active = tab_id
        self.action_refresh_active_view()

    def action_refresh_active_view(self) -> None:
        tabs = self.query_one("#main_tabs", TabbedContent)
        active_tab = tabs.active

        if active_tab == "tab_monitor":
            self._refresh_metrics()
        elif active_tab == "tab_containers":
            self._refresh_containers()
        elif active_tab == "tab_updates":
            self._refresh_updates()
        elif active_tab == "tab_settings":
            self._refresh_settings()

    def _periodic_tick(self) -> None:
        """Periodic refresh for live data."""
        tabs = self.query_one("#main_tabs", TabbedContent)
        if tabs.active == "tab_monitor":
            self._refresh_metrics()

    def _load_all_views(self) -> None:
        self._refresh_metrics()
        self._refresh_containers()
        self._refresh_updates()
        self._refresh_settings()

    def _update_status(self, text: str):
        try:
            self.query_one("#status_bar", Static).update(text)
        except Exception:
            pass

    def _refresh_metrics(self) -> None:
        ok, data = self.ipc.get_metrics()
        if ok and isinstance(data, dict):
            current = data.get("current", {})
            self.query_one("#view_monitor", MonitorView).update_data(current)
            self._update_status("● Daemon: Connected | Status: Healthy | Nightly Tasks: 02:00")
        else:
            self._update_status(f"⚠️ Daemon Offline: {data}")

    def _refresh_containers(self) -> None:
        ok, data = self.ipc.get_containers()
        if ok and isinstance(data, list):
            self.query_one("#view_containers", ContainersView).update_containers(data)
        else:
            self.query_one("#view_containers", ContainersView).update_containers([])

    def _refresh_updates(self) -> None:
        ok, data = self.ipc.get_pending_updates()
        if ok and isinstance(data, list):
            self.query_one("#view_updates", UpdatesView).update_pending_list(data)
        else:
            self.query_one("#view_updates", UpdatesView).update_pending_list([])

    def _refresh_settings(self) -> None:
        ok, data = self.ipc.get_config()
        if ok and isinstance(data, dict):
            self.query_one("#view_settings", SettingsView).load_data(data)

    # Button Event Handlers
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "btn_refresh_containers":
            self._refresh_containers()

        elif button_id == "btn_refresh_updates":
            self._refresh_updates()

        elif button_id == "btn_force_upgrade":
            updates_view = self.query_one("#view_updates", UpdatesView)
            cid = updates_view.get_selected_container_id()
            if not cid:
                self._update_status("⚠️ Please select a container row from the table first.")
                return

            self._update_status(f"Forcing upgrade for container {cid}...")
            ok, resp = self.ipc.force_update(cid)
            if ok:
                self._update_status(f"✓ Upgrade successful: {resp.get('message', '')}")
            else:
                self._update_status(f"✗ Upgrade failed: {resp}")
            self._refresh_updates()
            self._refresh_containers()

        elif button_id == "btn_save_config":
            settings_view = self.query_one("#view_settings", SettingsView)
            payload = settings_view.get_form_payload()
            ok, resp = self.ipc.save_config(payload)
            if ok:
                self._update_status("✓ Configuration saved and securely encrypted.")
                self._refresh_settings()
            else:
                self._update_status(f"✗ Failed to save configuration: {resp}")

        elif button_id == "btn_test_email":
            self._update_status("Sending test notification to configured recipients...")
            ok, resp = self.ipc.test_email()
            if ok and resp.get("success"):
                self._update_status(f"✓ Test email sent successfully: {resp.get('message')}")
            else:
                err = resp.get("message") if isinstance(resp, dict) else resp
                self._update_status(f"✗ Test email failed: {err}")

        elif button_id == "btn_trigger_nightly":
            self._update_status("Triggering scheduled 02:00 tasks manually...")
            ok, resp = self.ipc.trigger_nightly()
            if ok:
                self._update_status("✓ Nightly tasks executed successfully.")
            else:
                self._update_status(f"✗ Nightly tasks encountered error: {resp}")
            self._refresh_updates()
            self._refresh_containers()


def run_tui():
    app = ServerGuardianApp()
    app.run()


if __name__ == "__main__":
    run_tui()
