"""
System Monitoring View (htop style) for Server Guardian.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, DataTable


class MetricCard(Static):
    """A card displaying a key metric (CPU, RAM, Disk, Network)."""

    def __init__(self, title: str, id_prefix: str, **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.id_prefix = id_prefix

    def compose(self) -> ComposeResult:
        yield Static(self.title_text, classes="metric-title")
        yield Static("--", id=f"{self.id_prefix}_val", classes="metric-val")
        yield Static("--", id=f"{self.id_prefix}_sub", classes="metric-sub")

    def update_values(self, main_val: str, sub_val: str):
        try:
            self.query_one(f"#{self.id_prefix}_val", Static).update(main_val)
            self.query_one(f"#{self.id_prefix}_sub", Static).update(sub_val)
        except Exception:
            pass


class MonitorView(Container):
    """System Monitoring View featuring resource gauges and process list."""

    def compose(self) -> ComposeResult:
        # 4 Metric Cards
        with Horizontal(classes="metrics-grid"):
            yield MetricCard("CPU USAGE", "cpu", classes="metric-card")
            yield MetricCard("MEMORY (RAM)", "mem", classes="metric-card")
            yield MetricCard("DISK USAGE (/)", "disk", classes="metric-card")
            yield MetricCard("NETWORK I/O", "net", classes="metric-card")

        # Process Table
        table = DataTable(id="process_table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#process_table", DataTable)
        table.add_columns("PID", "USER", "CPU %", "MEM %", "STATUS", "PROCESS NAME")

    def update_data(self, metrics: dict):
        if not metrics:
            return

        # CPU Card
        cpu = metrics.get("cpu", {})
        cpu_pct = cpu.get("percent", 0.0)
        cores = cpu.get("logical_cores", 1)
        freq = cpu.get("freq_mhz", 0)
        self.query_one(Horizontal).query(MetricCard)[0].update_values(
            f"{cpu_pct}%", f"{cores} Cores @ {freq} MHz"
        )

        # Memory Card
        mem = metrics.get("memory", {})
        mem_pct = mem.get("percent", 0.0)
        used_mb = mem.get("used_mb", 0)
        total_mb = mem.get("total_mb", 0)
        self.query_one(Horizontal).query(MetricCard)[1].update_values(
            f"{mem_pct}%", f"{used_mb} MB / {total_mb} MB"
        )

        # Disk Card
        disk = metrics.get("disk", {})
        disk_pct = disk.get("percent", 0.0)
        disk_used = disk.get("used_gb", 0)
        disk_total = disk.get("total_gb", 0)
        self.query_one(Horizontal).query(MetricCard)[2].update_values(
            f"{disk_pct}%", f"{disk_used} GB / {disk_total} GB"
        )

        # Network Card
        net = metrics.get("network", {})
        rx = net.get("rx_rate_kbps", 0.0)
        tx = net.get("tx_rate_kbps", 0.0)
        self.query_one(Horizontal).query(MetricCard)[3].update_values(
            f"↓ {rx} KB/s", f"↑ {tx} KB/s"
        )

        # Update Process Table
        table = self.query_one("#process_table", DataTable)
        table.clear()
        processes = metrics.get("processes", [])
        for p in processes:
            table.add_row(
                str(p.get("pid")),
                str(p.get("user")),
                f"{p.get('cpu')}%",
                f"{p.get('memory')}%",
                str(p.get("status")),
                str(p.get("name")),
            )
