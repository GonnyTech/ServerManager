"""
Pending Updates View for Server Guardian.
Allows reviewing incremental/patch releases and manually triggering upgrades.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, DataTable, Button


class UpdatesView(Container):
    """View managing incremental and :latest pending container updates."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="btn-row"):
            yield Static("Pending Incremental & :latest Releases", classes="pending-title")
            yield Button("Force Upgrade Selected", id="btn_force_upgrade", classes="btn-warning")
            yield Button("Refresh", id="btn_refresh_updates")

        table = DataTable(id="updates_table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        yield table

        yield Static("Status: Ready", id="update_action_status", classes="metric-sub")

    def on_mount(self) -> None:
        table = self.query_one("#updates_table", DataTable)
        table.add_columns(
            "CONTAINER ID", "NAME", "CURRENT VERSION", "TARGET VERSION", "UPDATE TYPE"
        )

    def update_pending_list(self, pending_list: list):
        table = self.query_one("#updates_table", DataTable)
        table.clear()

        if not pending_list:
            self.query_one("#update_action_status", Static).update(
                "No pending updates. All containers are current or awaiting scheduled checks."
            )
            return

        self.query_one("#update_action_status", Static).update(
            f"Found {len(pending_list)} container(s) awaiting manual update confirmation."
        )

        for item in pending_list:
            cid = str(item.get("container_id", ""))[:12]
            name = str(item.get("container_name", ""))
            curr = str(item.get("current_version", ""))
            target = str(item.get("target_version", ""))
            utype = "Patch / Incremental" if item.get("type") == "incremental" else ":latest Remote Digest"

            table.add_row(cid, name, curr, target, utype)

    def get_selected_container_id(self) -> str:
        table = self.query_one("#updates_table", DataTable)
        if table.row_count == 0:
            return ""
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        row_data = table.get_row(row_key)
        return str(row_data[0]) if row_data else ""
