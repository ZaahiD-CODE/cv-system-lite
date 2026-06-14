#!/bin/bash
set -e

echo "========================================"
echo "  CV System - Installation"
echo "========================================"

cd "$(dirname "$0")"

echo ""
echo "[1/5] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo ""
echo "[2/5] Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -r web/requirements.txt -q

echo ""
echo "[3/5] Detecting GPU..."
python3 -c "
import torch
if torch.cuda.is_available():
    print(f'GPU found: {torch.cuda.get_device_name(0)}')
    print(f'Memory: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB')
    print('Installing CUDA-enabled PyTorch...')
    exit(0)
else:
    print('No NVIDIA GPU detected, using CPU')
    exit(0)
"

echo ""
echo "[4/5] Downloading YOLO models..."
mkdir -p models
python3 -c "
from ultralytics import YOLO
import os

models = [
    'yolo12n.pt', 'yolo12s.pt', 'yolo12m.pt', 'yolo12l.pt', 'yolo12x.pt',
]

for m in models:
    path = os.path.join('models', m)
    if os.path.exists(path):
        print(f'  {m} - already exists')
    else:
        print(f'  {m} - downloading...')
        try:
            model = YOLO(m)
            os.replace(m, path)
            print(f'  {m} - done')
        except Exception as e:
            print(f'  {m} - failed: {e}')
"

echo ""
echo "[5/5] Initializing database..."
python3 -c "
from web.database import init_db
init_db()
print('Database initialized')
"

echo ""
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""
echo "Start the server:"
echo "  source venv/bin/activate"
echo "  python3 run_web.py"
echo ""
echo "Default login: admin / XCFqm22tYmzqCZUraP0E"
echo "Web interface: http://localhost:8000"
