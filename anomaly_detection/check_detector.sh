#!/bin/bash
# Keepalive script for anomaly detector
# Add to crontab: */5 * * * * /path/to/check_detector.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/detector_keepalive.log"

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$LOG_FILE"
}

# Check if detector is running
if ! pgrep -f "detector.py" > /dev/null; then
    log_message "Detector not running, starting..."
    cd "$SCRIPT_DIR"
    nohup ./detector.py > detector_output.log 2>&1 &
    log_message "Detector started (PID: $!)"
else
    # Detector is running, log PID
    PID=$(pgrep -f "detector.py")
    log_message "Detector running (PID: $PID)"
fi
