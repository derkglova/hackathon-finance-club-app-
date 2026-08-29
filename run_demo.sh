#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() { kill $(jobs -p) 2>/dev/null; }
trap cleanup EXIT

cd "$DIR/Receipt OCR refund app"
python3 -m http.server 5500 > /dev/null 2>&1 &

cd "$DIR/app"
source .venv/bin/activate

(sleep 1 && open "http://127.0.0.1:5500/Ledger.dc.html") &

python app.py
