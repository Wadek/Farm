#!/bin/sh
set -e
mkdir -p /data
if [ ! -f /data/farm.db ]; then
  python seed.py
fi
exec uvicorn main:app --host 0.0.0.0 --port 8080
