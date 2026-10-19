"""
Docker Containers View for Server Guardian.
Displays active containers, health status, and update flags.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static, DataTable, Button


class ContainersView(Container):
    """View displaying running and stopped Docker containers."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="btn-row"):
            yield Static("Docker Containers Management", classes="metric-title")
            yield Button("Refresh", id="btn_refresh_containers")

        table = DataTable(id="containers_table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#containers_table", DataTable)
        table.add_columns(
            "ID", "NAME", "STATUS", "HEALTH", "IMAGE", "UPDATE PENDING"
        )

    def update_containers(self, containers: list):
        table = self.query_one("#containers_table", DataTable)
        table.clear()

        for c in containers:
            status = c.get("status", "unknown")
            health = c.get("health", "none")
            pending = "⚠️ YES (Review Tab 3)" if c.get("pending_update") else "✓ Up-to-date"

            table.add_row(
                str(c.get("id")),
                str(c.get("name")),
                str(status).upper(),
                str(health),
                str(c.get("image")),
                pending,
            )
