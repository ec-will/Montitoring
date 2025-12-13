#!/bin/bash
# EarthCast Usage Report Update Script

# Set environment variables for myusage command
export PATH="/usr/login/bin:$PATH"
export PERL5LIB="/usr/login/share/perl5"

# Web servers to deploy to (add/remove as needed)
WEB_SERVERS=(
    "will@rcity2.cottay.net:/srv/www/earthcast"
    "will@ect-hpc.wx-farms.com:/srv/www/earthcast"
)

SCRIPT_DIR="/e/08/erthch01/monitoring/web_dashboard"
LOG_DIR="/e/08/erthch01/logs/dashboard"
LOCK_FILE="/tmp/usage_report_update.lock"
LOG_FILE="$LOG_DIR/update_usage_report.log"
OUTPUT_FILE="$SCRIPT_DIR/usage_report_data.json"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$LOG_FILE"
}

# Check for existing lock file
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE") ))
    if [ $LOCK_AGE -lt 1800 ]; then  # If lock is less than 30 minutes old
        log_message "Usage report update already running (lock file exists), skipping"
        exit 0
    else
        log_message "Stale lock file detected, removing and continuing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
touch "$LOCK_FILE"

log_message "Starting usage report data update"

cd "$SCRIPT_DIR" || {
    log_message "ERROR: Could not change to script directory $SCRIPT_DIR"
    rm -f "$LOCK_FILE"
    exit 1
}

# Generate usage report data
if python3 usage_report_json.py > "$OUTPUT_FILE" 2>/tmp/usage_report_stderr.log; then
    log_message "Usage report data generated successfully"
    
    # Deploy to all servers independently
    SUCCESS_COUNT=0
    FAIL_COUNT=0
    
    for server in "${WEB_SERVERS[@]}"; do
        if scp usage_report_data.json "$server" >> "$LOG_FILE" 2>&1; then
            log_message "Usage report deployed to $server successfully"
            ((SUCCESS_COUNT++))
        else
            log_message "ERROR: Failed to deploy usage report to $server"
            ((FAIL_COUNT++))
        fi
    done
    
    # Log summary info
    FILE_SIZE=$(ls -lh usage_report_data.json | awk '{print $5}')
    TOTAL_JOBS=$(cat usage_report_data.json | jq '.job_usage.summary.total_jobs' 2>/dev/null || echo "unknown")
    CORE_HOURS=$(cat usage_report_data.json | jq '.job_usage.summary.total_core_hours' 2>/dev/null || echo "unknown")
    CLUSTERS=$(cat usage_report_data.json | jq '.job_usage.summary.unique_clusters' 2>/dev/null || echo "unknown")
    log_message "Update complete: $FILE_SIZE, $TOTAL_JOBS jobs, $CORE_HOURS core-hours, $CLUSTERS clusters (deployed to $SUCCESS_COUNT/$((SUCCESS_COUNT+FAIL_COUNT)) servers)"
else
    log_message "ERROR: Failed to generate usage report data"
    cat /tmp/usage_report_stderr.log >> "$LOG_FILE"
fi

# Clean up
rm -f "$LOCK_FILE"
rm -f /tmp/usage_report_stderr.log

# Keep only last 200 lines of log
tail -200 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"

log_message "Usage report data update completed"
