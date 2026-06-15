import os
import glob
import psutil
import subprocess
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from pathlib import Path

from ..database import get_db, CustomObject, User
from ..auth import require_admin

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/metrics")
async def get_metrics(current_user: User = Depends(require_admin)):
    cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()

    gpu_info = None
    try:
        import torch
        if torch.cuda.is_available():
            gpu_info = {
                "name": torch.cuda.get_device_name(0),
                "memory_total_mb": round(torch.cuda.get_device_properties(0).total_mem / 1024**2),
                "memory_used_mb": round(torch.cuda.memory_allocated(0) / 1024**2),
                "memory_free_mb": round((torch.cuda.get_device_properties(0).total_mem - torch.cuda.memory_allocated(0)) / 1024**2),
                "utilization": torch.cuda.utilization(0) if hasattr(torch.cuda, 'utilization') else 0,
            }
    except Exception:
        pass

    return {
        "cpu": {
            "percent_total": round(sum(cpu_percent) / len(cpu_percent), 1),
            "percent_per_core": cpu_percent,
            "cores_physical": psutil.cpu_count(logical=False),
            "cores_logical": psutil.cpu_count(logical=True),
            "freq_current_mhz": round(cpu_freq.current) if cpu_freq else None,
            "freq_max_mhz": round(cpu_freq.max) if cpu_freq else None,
        },
        "memory": {
            "total_mb": round(mem.total / 1024**2),
            "used_mb": round(mem.used / 1024**2),
            "available_mb": round(mem.available / 1024**2),
            "percent": mem.percent,
        },
        "disk": {
            "total_gb": round(disk.total / 1024**3, 1),
            "used_gb": round(disk.used / 1024**3, 1),
            "free_gb": round(disk.free / 1024**3, 1),
            "percent": disk.percent,
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "bytes_sent_mb": round(net.bytes_sent / 1024**2),
            "bytes_recv_mb": round(net.bytes_recv / 1024**2),
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
        },
        "gpu": gpu_info,
    }


@router.get("/logs")
async def get_logs(lines: int = 200, current_user: User = Depends(require_admin)):
    log_entries = []
    cutoff = datetime.now() - timedelta(hours=24)

    try:
        result = subprocess.run(
            ["journalctl", "-u", "cv-system", "--since", "24 hours ago", "--no-pager", "-n", str(lines), "--output=short-iso"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                log_entries.append(line)
    except Exception:
        pass

    return {"logs": log_entries, "total": len(log_entries)}


@router.post("/restart")
async def restart_server(current_user: User = Depends(require_admin)):
    import threading
    def _restart():
        import time
        time.sleep(1)
        subprocess.run(["systemctl", "restart", "cv-system"])
    threading.Thread(target=_restart, daemon=True).start()
    return {"message": "Server restarting..."}


@router.get("/custom-models")
async def list_custom_models(current_user: User = Depends(require_admin), db=Depends(get_db)):
    models_dir = Path("/root/cv_system/models")

    objects = db.query(CustomObject).filter(CustomObject.model_path.isnot(None)).all()
    obj_map = {o.model_path: o for o in objects if o.model_path}

    result = []
    for f in models_dir.glob("*.pt"):
        obj = obj_map.get(str(f))
        if obj:
            result.append({
                "filename": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / 1024**2, 1),
                "object_id": obj.id,
                "object_name": obj.name,
            })

    for d in models_dir.iterdir():
        if d.is_dir() and not d.name.startswith("yolo"):
            result.append({
                "filename": d.name,
                "path": str(d),
                "size_mb": round(sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1024**2, 1),
                "object_id": None,
                "object_name": None,
                "type": "training_dir",
            })

    return result


@router.delete("/custom-models/{filename}")
async def delete_custom_model(filename: str, current_user: User = Depends(require_admin), db=Depends(get_db)):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    models_dir = Path("/root/cv_system/models")
    model_path = models_dir / filename

    if model_path.exists():
        if model_path.is_dir():
            import shutil
            shutil.rmtree(model_path)
        else:
            model_path.unlink()

    obj = db.query(CustomObject).filter(CustomObject.model_path == str(model_path)).first()
    if obj:
        obj.model_path = None
        obj.status = "collecting"
        db.commit()

    return {"message": f"Deleted {filename}"}


@router.post("/custom-models/cleanup")
async def cleanup_training_dirs(current_user: User = Depends(require_admin)):
    models_dir = Path("/root/cv_system/models")
    removed = 0
    for d in models_dir.iterdir():
        if d.is_dir() and not d.name.startswith("yolo"):
            import shutil
            shutil.rmtree(d)
            removed += 1
    return {"message": f"Removed {removed} training directories"}
