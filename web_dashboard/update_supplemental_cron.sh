#!/bin/bash
# EarthCast Dashboard Supplemental Data Update Script
# Runs less frequently than main dashboard (e.g., every hour)

SCRIPT_DIR="/e/08/erthch01/monitoring/web_dashboard"
LOG_DIR="/e/08/erthch01/logs/dashboard"
LOCK_FILE="/tmp/supplemental_update.lock"
LOG_FILE="$LOG_DIR/update_supplemental.log"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$LOG_FILE"
}

# Check for existing lock file
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE") ))
    if [ $LOCK_AGE -lt 300 ]; then  # If lock is less than 5 minutes old
        log_message "Supplemental update already running (lock file exists), skipping"
        exit 0
    else
        log_message "Stale lock file detected, removing and continuing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
touch "$LOCK_FILE"

log_message "Starting supplemental data update"

cd "$SCRIPT_DIR" || {
    log_message "ERROR: Could not change to script directory $SCRIPT_DIR"
    rm -f "$LOCK_FILE"
    exit 1
}

# Generate supplemental data
if python3 generate_supplemental_data.py > /tmp/supplemental_update_output.log 2>&1; then
    log_message "Supplemental data generated successfully"
    
    # Push to server
    if scp dashboard_supplemental.json will@rcity2.cottay.net:/srv/www/earthcast/ >> "$LOG_FILE" 2>&1; then
        log_message "Supplemental data deployed to server successfully"
        
        # Log summary info
        FILE_SIZE=$(ls -lh dashboard_supplemental.json | awk '{print $5}')
        log_message "Update complete: supplemental data file size $FILE_SIZE"
    else
        log_message "ERROR: Failed to deploy supplemental data to server"
    fi
else
    log_message "ERROR: Failed to generate supplemental data"
    cat /tmp/supplemental_update_output.log >> "$LOG_FILE"
fi

# Clean up
rm -f "$LOCK_FILE"
rm -f /tmp/supplemental_update_output.log

# Keep only last 100 lines of log
tail -100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"

log_message "Supplemental data update completed"
