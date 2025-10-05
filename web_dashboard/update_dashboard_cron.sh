#!/bin/bash
# EarthCast Dashboard Update Script
# Runs every minute via cron to update dashboard data

SCRIPT_DIR="/e/08/erthch01/monitoring/web_dashboard"
LOG_DIR="/e/08/erthch01/logs/dashboard"
LOCK_FILE="/tmp/dashboard_update.lock"
LOG_FILE="$LOG_DIR/update_dashboard.log"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$LOG_FILE"
}

# Check for existing lock file to prevent overlapping runs
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE") ))
    if [ $LOCK_AGE -lt 120 ]; then  # If lock is less than 2 minutes old
        log_message "Dashboard update already running (lock file exists), skipping"
        exit 0
    else
        log_message "Stale lock file detected, removing and continuing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
touch "$LOCK_FILE"

# Ensure PATH includes Torque PBS tools
export PATH="/usr/local/torque-4.2.8/bin:/e/08/erthch01/bin:$PATH"

log_message "Starting dashboard update"

cd "$SCRIPT_DIR" || {
    log_message "ERROR: Could not change to script directory $SCRIPT_DIR"
    rm -f "$LOCK_FILE"
    exit 1
}

# Generate fresh dashboard data
if python3 update_dashboard.py > /tmp/dashboard_update_output.log 2>&1; then
    log_message "Dashboard data generated successfully"
    
    # Push to server using scp (more reliable than rsync for single files)
    if scp dashboard_data.json will@rcity2.cottay.net:/srv/www/earthcast/ >> "$LOG_FILE" 2>&1; then
        log_message "Dashboard data deployed to server successfully"
        
        # Log summary info
        PBS_COUNT=$(cat dashboard_data.json | jq '.pbs_jobs | length' 2>/dev/null || echo "unknown")
        WORKFLOW_COUNT=$(cat dashboard_data.json | jq '.workflows | keys | length' 2>/dev/null || echo "unknown")
        log_message "Update complete: $PBS_COUNT PBS jobs, $WORKFLOW_COUNT workflows"
    else
        log_message "ERROR: Failed to deploy dashboard data to server"
    fi
else
    log_message "ERROR: Failed to generate dashboard data"
    cat /tmp/dashboard_update_output.log >> "$LOG_FILE"
fi

# Clean up
rm -f "$LOCK_FILE"
rm -f /tmp/dashboard_update_output.log

# Keep only last 100 lines of log
tail -100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"

log_message "Dashboard update completed"
