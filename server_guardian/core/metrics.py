"""
System Metrics Collector for Server Guardian.
Uses psutil to monitor CPU, RAM, Network, Disk and Processes in real-time.
"""

import time
import os
import shutil
import subprocess
import glob
from pathlib import Path
from typing import Dict, Any, List
import psutil

# Cache previous network counters for rate calculation
_last_net_io = None
_last_net_time = None


def get_gpu_metrics() -> Dict[str, Any]:
    """
    Detect and gather GPU metrics (NVIDIA NVENC/NVDEC, Intel QuickSync iGPU, AMD).
    Optimized for media servers (Jellyfin/Plex) and hardware transcoding.
    """
    # 1. Check NVIDIA via nvidia-smi
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            cmd = [
                nvidia_smi,
                "--query-gpu=name,utilization.gpu,utilization.encoder,utilization.decoder,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.5)
            if res.returncode == 0 and res.stdout.strip():
                line = res.stdout.strip().split("\n")[0]
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 7:
                    name = parts[0]
                    gpu_util = int(parts[1]) if parts[1].isdigit() else 0
                    enc_util = int(parts[2]) if parts[2].isdigit() else 0
                    dec_util = int(parts[3]) if parts[3].isdigit() else 0
                    mem_used = int(parts[4]) if parts[4].isdigit() else 0
                    mem_total = int(parts[5]) if parts[5].isdigit() else 0
                    temp = int(parts[6]) if parts[6].isdigit() else 0

                    return {
                        "available": True,
                        "vendor": "NVIDIA",
                        "name": name,
                        "percent": gpu_util,
                        "encoder_percent": enc_util,
                        "decoder_percent": dec_util,
                        "memory_used_mb": mem_used,
                        "memory_total_mb": mem_total,
                        "temperature_c": temp,
                        "transcoding_active": enc_util > 0 or dec_util > 0,
                    }
        except Exception:
            pass

    # 2. Check Intel QuickSync / iGPU (DRM / sysfs)
    try:
        drm_cards = glob.glob("/sys/class/drm/card*")
        for card in drm_cards:
            vendor_path = Path(card) / "device" / "vendor"
            if vendor_path.exists():
                vendor_id = vendor_path.read_text().strip().lower()
                if vendor_id == "0x8086":  # Intel
                    act_freq = 0
                    max_freq = 0
                    for freq_file in [
                        Path(card) / "gt_act_freq_mhz",
                        Path(card) / "device" / "drm" / Path(card).name / "gt_act_freq_mhz",
                    ]:
                        if freq_file.exists():
                            try:
                                act_freq = int(freq_file.read_text().strip())
                                break
                            except Exception:
                                pass

                    for max_file in [
                        Path(card) / "gt_max_freq_mhz",
                        Path(card) / "device" / "drm" / Path(card).name / "gt_max_freq_mhz",
                    ]:
                        if max_file.exists():
                            try:
                                max_freq = int(max_file.read_text().strip())
                                break
                            except Exception:
                                pass

                    render_node = Path("/dev/dri/renderD128").exists()
                    percent = round((act_freq / max_freq) * 100) if max_freq > 0 else 0

                    return {
                        "available": True,
                        "vendor": "Intel",
                        "name": "Intel QuickSync (iGPU)",
                        "percent": percent,
                        "encoder_percent": 0,
                        "decoder_percent": 0,
                        "freq_mhz": act_freq,
                        "max_freq_mhz": max_freq,
                        "render_node_present": render_node,
                        "transcoding_active": act_freq > 350 if act_freq else False,
                    }
                elif vendor_id == "0x1002":  # AMD
                    gpu_busy_path = Path(card) / "device" / "gpu_busy_percent"
                    busy = 0
                    if gpu_busy_path.exists():
                        try:
                            busy = int(gpu_busy_path.read_text().strip())
                        except Exception:
                            pass
                    return {
                        "available": True,
                        "vendor": "AMD",
                        "name": "AMD Radeon GPU",
                        "percent": busy,
                        "encoder_percent": 0,
                        "decoder_percent": 0,
                        "transcoding_active": False,
                    }
    except Exception:
        pass

    return {
        "available": False,
        "vendor": "None",
        "name": "No GPU detected",
        "percent": 0,
        "transcoding_active": False,
    }


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
        "gpu": get_gpu_metrics(),
        "processes": top_processes,
    }
