#!/bin/bash
# Transfer Log Dashboard Update Script
# Runs via cron to update transfer dashboard data

# Web servers to deploy to (add/remove as needed)
WEB_SERVERS=(
    "will@rcity2.cottay.net:/srv/www/earthcast"
    "will@ect-hpc.wx-farms.com:/srv/www/earthcast"
)

SCRIPT_DIR="/e/08/erthch01/monitoring/log_monitoring"
LOG_DIR="/e/08/erthch01/logs/dashboard"
TRANSFER_LOG_DIR="/e/08/erthch01/logs/transfers"
LOCK_FILE="/tmp/transfer_dashboard_update.lock"
LOG_FILE="$LOG_DIR/update_transfer_dashboard.log"

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
        log_message "Transfer dashboard update already running (lock file exists), skipping"
        exit 0
    else
        log_message "Stale lock file detected, removing and continuing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
touch "$LOCK_FILE"

log_message "Starting transfer dashboard update"

# Check if transfer log exists
if [ ! -f "$TRANSFER_LOG_DIR/transfer.log" ]; then
    log_message "ERROR: Transfer log not found at $TRANSFER_LOG_DIR/transfer.log"
    rm -f "$LOCK_FILE"
    exit 1
fi

cd "$SCRIPT_DIR" || {
    log_message "ERROR: Could not change to script directory $SCRIPT_DIR"
    rm -f "$LOCK_FILE"
    exit 1
}

# Copy parser to transfer log directory and run it there
cp parse_transfers.py "$TRANSFER_LOG_DIR/"

cd "$TRANSFER_LOG_DIR" || {
    log_message "ERROR: Could not change to transfer log directory"
    rm -f "$LOCK_FILE"
    exit 1
}

# Generate fresh transfer dashboard data
if python3 parse_transfers.py --hours 12 > /tmp/transfer_dashboard_update_output.log 2>&1; then
    log_message "Transfer dashboard data generated successfully"
    
    # Deploy to all servers independently
    SUCCESS_COUNT=0
    FAIL_COUNT=0
    
    for server in "${WEB_SERVERS[@]}"; do
        if scp transfers.json "$server" >> "$LOG_FILE" 2>&1; then
            log_message "Transfer dashboard data deployed to $server successfully"
            ((SUCCESS_COUNT++))
        else
            log_message "ERROR: Failed to deploy transfer dashboard data to $server"
            ((FAIL_COUNT++))
        fi
    done
    
    # Log summary info
    LOG_ENTRIES=$(cat transfers.json | jq '.statistics.total_log_entries' 2>/dev/null || echo "unknown")
    SESSIONS=$(cat transfers.json | jq '.statistics.total_sessions' 2>/dev/null || echo "unknown") 
    log_message "Update complete: $LOG_ENTRIES log entries, $SESSIONS transfer sessions (deployed to $SUCCESS_COUNT/$((SUCCESS_COUNT+FAIL_COUNT)) servers)"
else
    log_message "ERROR: Failed to generate transfer dashboard data"
    cat /tmp/transfer_dashboard_update_output.log >> "$LOG_FILE"
fi

# Clean up
rm -f "$LOCK_FILE"
rm -f /tmp/transfer_dashboard_update_output.log

# Keep only last 100 lines of log
tail -100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"

log_message "Transfer dashboard update completed"
