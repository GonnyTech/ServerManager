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


def _detect_pci_gpu() -> Dict[str, str]:
    """
    Query lspci to find commercial GPU name and vendor (e.g. ATI Radeon HD 4650).
    """
    lspci = shutil.which("lspci")
    if not lspci:
        return {}

    try:
        res = subprocess.run([lspci], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.5)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                lower = line.lower()
                if any(k in lower for k in ["vga compatible controller", "3d controller", "display controller"]):
                    parts = line.split(":", 2)
                    raw_name = parts[2].strip() if len(parts) >= 3 else line.strip()

                    vendor = "Unknown"
                    if "amd" in lower or "ati" in lower:
                        vendor = "ATI/AMD"
                    elif "nvidia" in lower:
                        vendor = "NVIDIA"
                    elif "intel" in lower:
                        vendor = "Intel"

                    clean_name = raw_name
                    import re
                    brackets = re.findall(r"\[(.*?)\]", raw_name)
                    if brackets:
                        last = brackets[-1]
                        if "radeon" in last.lower() or "geforce" in last.lower() or "hd" in last.lower():
                            clean_name = f"ATI {last}" if "ati" in lower and not last.lower().startswith("ati") else last
                        elif len(brackets) >= 2 and ("ati" in brackets[0].lower() or "amd" in brackets[0].lower()):
                            clean_name = f"{brackets[0]} {brackets[-1]}"
                        else:
                            clean_name = f"{vendor} {last}"

                    return {
                        "vendor": vendor,
                        "raw_name": raw_name,
                        "name": clean_name,
                    }
    except Exception:
        pass
    return {}


def _scan_pci_sysfs_gpus() -> List[Dict[str, Any]]:
    """
    Direct kernel sysfs scanner for PCI Display / 3D / VGA controllers.
    Works on 100% of Linux kernels even without lspci or DRM.
    """
    gpus = []
    try:
        pci_dirs = glob.glob("/sys/bus/pci/devices/*")
        for dev in pci_dirs:
            class_path = Path(dev) / "class"
            if not class_path.exists():
                continue
            try:
                pci_class = class_path.read_text().strip().lower()
            except Exception:
                continue

            # Class 0x03xxxx = Display / VGA / 3D Controller
            if pci_class.startswith("0x03"):
                vendor_id = ""
                device_id = ""
                try:
                    v_p = Path(dev) / "vendor"
                    if v_p.exists():
                        vendor_id = v_p.read_text().strip().lower()
                except Exception:
                    pass

                try:
                    d_p = Path(dev) / "device"
                    if d_p.exists():
                        device_id = d_p.read_text().strip().lower()
                except Exception:
                    pass

                driver_name = ""
                try:
                    drv_p = Path(dev) / "driver"
                    if drv_p.exists():
                        driver_name = drv_p.resolve().name
                except Exception:
                    pass

                # Temperature from device hwmon
                temp_c = None
                try:
                    hwmon_dirs = glob.glob(f"{dev}/hwmon/hwmon*")
                    for h in hwmon_dirs:
                        t_file = Path(h) / "temp1_input"
                        if t_file.exists():
                            temp_c = int(t_file.read_text().strip()) // 1000
                            break
                except Exception:
                    pass

                vendor = "PCI Display"
                name = f"VGA Controller ({vendor_id}:{device_id})"
                if vendor_id == "0x1002":
                    vendor = "ATI/AMD"
                    if device_id in ["0x9498", "0x9495", "0x9490", "0x9480", "0x9488"]:
                        name = "ATI Radeon HD 4650"
                    elif device_id.startswith("0x94") or device_id.startswith("0x95"):
                        name = "ATI Radeon HD 4000 Series"
                    elif device_id.startswith("0x67") or device_id.startswith("0x68"):
                        name = "AMD Radeon HD Series"
                    else:
                        name = "ATI/AMD Radeon GPU"
                elif vendor_id == "0x10de":
                    vendor = "NVIDIA"
                    name = "NVIDIA GPU"
                elif vendor_id == "0x8086":
                    vendor = "Intel"
                    name = "Intel HD/UHD Graphics (iGPU)"

                gpus.append({
                    "vendor": vendor,
                    "vendor_id": vendor_id,
                    "device_id": device_id,
                    "name": name,
                    "driver": driver_name or ("radeon" if vendor_id == "0x1002" else driver_name),
                    "temperature_c": temp_c,
                    "pci_path": dev,
                })
    except Exception:
        pass
    return gpus


def get_gpu_metrics() -> Dict[str, Any]:
    """
    Detect and gather GPU metrics (NVIDIA NVENC/NVDEC, AMD/ATI Radeon HD, Intel QuickSync iGPU).
    Optimized for media servers (Jellyfin/Plex) and hardware detection.
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
                        "driver": "nvidia",
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

    # 2. Check PCI detection via lspci
    pci_info = _detect_pci_gpu()

    # 3. Direct Kernel PCI Sysfs check (guarantees finding hardware even without lspci or DRM)
    sysfs_gpus = _scan_pci_sysfs_gpus()

    # Global temperature check via hwmon if not found in device
    global_temp_c = None
    try:
        for h in glob.glob("/sys/class/hwmon/hwmon*"):
            name_f = Path(h) / "name"
            if name_f.exists() and any(k in name_f.read_text().lower() for k in ["radeon", "amdgpu", "nouveau"]):
                t_f = Path(h) / "temp1_input"
                if t_f.exists():
                    global_temp_c = int(t_f.read_text().strip()) // 1000
                    break
    except Exception:
        pass

    # 3. Check Linux DRM / sysfs
    drm_cards = [c for c in glob.glob("/sys/class/drm/card[0-9]*") if "-" not in Path(c).name]

    for card in drm_cards:
        vendor_id = ""
        driver_name = ""
        try:
            vendor_path = Path(card) / "device" / "vendor"
            if vendor_path.exists():
                vendor_id = vendor_path.read_text().strip().lower()
        except Exception:
            pass

        try:
            driver_path = Path(card) / "device" / "driver"
            if driver_path.exists():
                driver_name = driver_path.resolve().name
        except Exception:
            pass

        # Temperature check via hwmon
        temp_c = None
        try:
            hwmon_dirs = glob.glob(f"{card}/device/hwmon/hwmon*")
            if not hwmon_dirs:
                hwmon_dirs = glob.glob("/sys/class/hwmon/hwmon*")
            for h in hwmon_dirs:
                t_file = Path(h) / "temp1_input"
                if t_file.exists():
                    try:
                        temp_c = int(t_file.read_text().strip()) // 1000
                        break
                    except Exception:
                        pass
        except Exception:
            pass

        # Intel iGPU
        if vendor_id == "0x8086" or (pci_info and pci_info.get("vendor") == "Intel"):
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
            name = pci_info.get("name") if pci_info else "Intel QuickSync (iGPU)"

            return {
                "available": True,
                "vendor": "Intel",
                "name": name,
                "driver": driver_name or "i915",
                "percent": percent,
                "encoder_percent": 0,
                "decoder_percent": 0,
                "freq_mhz": act_freq,
                "max_freq_mhz": max_freq,
                "temperature_c": temp_c,
                "render_node_present": render_node,
                "transcoding_active": act_freq > 350 if act_freq else False,
            }

        # AMD / ATI (including legacy cards like Radeon HD 4650)
        if vendor_id == "0x1002" or (pci_info and pci_info.get("vendor") == "ATI/AMD"):
            busy = 0
            gpu_busy_path = Path(card) / "device" / "gpu_busy_percent"
            if gpu_busy_path.exists():
                try:
                    busy = int(gpu_busy_path.read_text().strip())
                except Exception:
                    pass

            name = pci_info.get("name") if pci_info else "ATI/AMD Radeon GPU"
            return {
                "available": True,
                "vendor": "ATI/AMD",
                "name": name,
                "driver": driver_name or "radeon",
                "percent": busy,
                "encoder_percent": 0,
                "decoder_percent": 0,
                "temperature_c": temp_c,
                "transcoding_active": False,
            }

    # 4. Fallback: if lspci detected a GPU even if DRM sysfs was incomplete
    if pci_info and pci_info.get("name"):
        return {
            "available": True,
            "vendor": pci_info.get("vendor", "PCI GPU"),
            "name": pci_info.get("name"),
            "driver": "detected",
            "percent": 0,
            "encoder_percent": 0,
            "decoder_percent": 0,
            "temperature_c": global_temp_c,
            "transcoding_active": False,
        }

    # 5. Fallback: Direct Kernel Sysfs PCI check (works without lspci or DRM)
    if sysfs_gpus:
        # Prioritize discrete ATI/AMD or NVIDIA GPU over generic display controller
        gpu = sysfs_gpus[0]
        for candidate in sysfs_gpus:
            if candidate["vendor"] in ["ATI/AMD", "NVIDIA"]:
                gpu = candidate
                break

        name = pci_info.get("name") if (pci_info and pci_info.get("name")) else gpu["name"]
        temp = gpu.get("temperature_c") or global_temp_c

        return {
            "available": True,
            "vendor": gpu["vendor"],
            "name": name,
            "driver": gpu.get("driver") or ("radeon" if gpu["vendor"] == "ATI/AMD" else "generic"),
            "percent": 0,
            "encoder_percent": 0,
            "decoder_percent": 0,
            "temperature_c": temp,
            "transcoding_active": False,
        }

    return {
        "available": False,
        "vendor": "None",
        "name": "No GPU detected",
        "driver": "none",
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
