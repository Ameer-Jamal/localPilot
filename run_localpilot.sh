#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/ajamal/Documents/PythonProjects/localPilot"
PYTHON_BIN="/Users/ajamal/.pyenv/versions/3.13.0/bin/python3"
LOG_DIR="${HOME}/.localpilot"
LOG_FILE="${LOG_DIR}/localpilot.log"

mkdir -p "${LOG_DIR}"
cd "${PROJECT_DIR}"

exec "${PYTHON_BIN}" main.py >>"${LOG_FILE}" 2>&1
