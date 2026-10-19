"""
System Metrics Collector for Server Guardian.
Uses psutil to monitor CPU, RAM, Network, Disk and Processes in real-time.
"""

import time
from typing import Dict, Any, List
import psutil

# Cache previous network counters for rate calculation
_last_net_io = None
_last_net_time = None


def get_system_metrics() -> Dict[str, Any]:
    """
    Collect comprehensive system health metrics.
    """
    global _last_net_io, _last_net_time

    # CPU
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_cores_logical = psutil.cpu_count(logical=True) or 1
    cpu_cores_physical = psutil.cpu_count(logical=False) or 1
    cpu_freq = psutil.cpu_freq()
    cpu_freq_current = round(cpu_freq.current, 1) if cpu_freq else 0.0

    # Memory
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Disk (root filesystem)
    try:
        disk = psutil.disk_usage("/")
        disk_data = {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": disk.percent,
        }
    except Exception:
        disk_data = {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}

    # Network IO & rates
    net_io = psutil.net_io_counters()
    current_time = time.time()
    rx_rate = 0.0
    tx_rate = 0.0

    if _last_net_io and _last_net_time:
        time_delta = current_time - _last_net_time
        if time_delta > 0:
            rx_rate = (net_io.bytes_recv - _last_net_io.bytes_recv) / time_delta
            tx_rate = (net_io.bytes_sent - _last_net_io.bytes_sent) / time_delta

    _last_net_io = net_io
    _last_net_time = current_time

    # Top Processes (by CPU and Memory)
    processes: List[Dict[str, Any]] = []
    try:
        for p in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status"]):
            try:
                info = p.info
                # psutil cpu_percent for process needs non-zero or quick snapshot
                processes.append({
                    "pid": info.get("pid"),
                    "name": info.get("name") or "unknown",
                    "user": info.get("username") or "root",
                    "cpu": round(info.get("cpu_percent") or 0.0, 1),
                    "memory": round(info.get("memory_percent") or 0.0, 1),
                    "status": info.get("status") or "running",
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU desc then memory
        processes.sort(key=lambda x: (x["cpu"], x["memory"]), reverse=True)
        top_processes = processes[:25]
    except Exception:
        top_processes = []

    # Uptime
    boot_time = psutil.boot_time()
    uptime_seconds = int(current_time - boot_time)

    return {
        "timestamp": current_time,
        "uptime_seconds": uptime_seconds,
        "cpu": {
            "percent": cpu_percent,
            "logical_cores": cpu_cores_logical,
            "physical_cores": cpu_cores_physical,
            "freq_mhz": cpu_freq_current,
        },
        "memory": {
            "total_mb": round(mem.total / (1024**2), 1),
            "used_mb": round(mem.used / (1024**2), 1),
            "available_mb": round(mem.available / (1024**2), 1),
            "percent": mem.percent,
        },
        "swap": {
            "total_mb": round(swap.total / (1024**2), 1),
            "used_mb": round(swap.used / (1024**2), 1),
            "percent": swap.percent,
        },
        "disk": disk_data,
        "network": {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "tx_rate_kbps": round(tx_rate / 1024, 2),
            "rx_rate_kbps": round(rx_rate / 1024, 2),
        },
        "processes": top_processes,
    }
