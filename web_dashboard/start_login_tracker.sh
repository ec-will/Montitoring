#!/bin/bash
#
# Start/monitor login node job tracker
# Can be called multiple times safely - won't start duplicate instances
#

SCRIPT_DIR="$HOME/monitoring/web_dashboard"
LOCKFILE="/tmp/dashboard_login_jobs.lock"
LOGFILE="$HOME/logs/dashboard/login_jobs.log"
TRACKER_SCRIPT="$SCRIPT_DIR/dashboard_login_jobs.py"

# Ensure log directory exists
mkdir -p "$(dirname "$LOGFILE")"

# Check if already running via lock file
if [ -f "$LOCKFILE" ]; then
    PID=$(cat "$LOCKFILE")
    if ps -p $PID > /dev/null 2>&1; then
        # Already running, exit quietly
        exit 0
    else
        # Stale lock file, remove it
        rm -f "$LOCKFILE"
    fi
fi

# Check if tracker script exists
if [ ! -f "$TRACKER_SCRIPT" ]; then
    echo "ERROR: Tracker script not found: $TRACKER_SCRIPT" >> "$LOGFILE"
    exit 1
fi

# Start the tracker
cd "$SCRIPT_DIR" || exit 1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting login job tracker..." >> "$LOGFILE"
nohup "$TRACKER_SCRIPT" >> "$LOGFILE" 2>&1 &

# Give it a moment to start
sleep 2

# Verify it started
if [ -f "$LOCKFILE" ]; then
    PID=$(cat "$LOCKFILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Login job tracker started successfully (PID $PID)" >> "$LOGFILE"
        exit 0
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: Failed to start login job tracker" >> "$LOGFILE"
        exit 1
    fi
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - WARNING: Tracker may not have started (no lock file)" >> "$LOGFILE"
    exit 1
fi
