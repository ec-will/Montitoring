#!/bin/bash
# Disk Usage Dashboard Update Script
# Runs via cron to update disk usage dashboard data

# Web servers to deploy to (add/remove as needed)
WEB_SERVERS=(
    "will@rcity2.cottay.net:/srv/www/earthcast/disk-usage"
    "will@ect-hpc.wx-farms.com:/srv/www/earthcast/disk-usage"
)

SCRIPT_DIR="/e/08/erthch01/monitoring/disk-usage"
LOG_DIR="/e/08/erthch01/logs/disk-usage"
LOCK_FILE="/tmp/disk_usage_update.lock"
LOG_FILE="$LOG_DIR/update_disk_usage.log"
DATA_FILE="$SCRIPT_DIR/disk_usage_data.json"
COLLECTION_SCRIPT="$SCRIPT_DIR/collect_disk_usage.py"
HTML_FILE="$SCRIPT_DIR/disk-usage.html"

# Root directory to scan (home directory)
ROOT_DIR="/e/08/erthch01"
MAX_DEPTH=3

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$LOG_FILE"
}

# Check for existing lock file to prevent overlapping runs
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE") ))
    if [ $LOCK_AGE -lt 7200 ]; then  # If lock is less than 2 hours old
        log_message "Disk usage update already running (lock file exists), skipping"
        exit 0
    else
        log_message "Stale lock file detected, removing and continuing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
touch "$LOCK_FILE"

log_message "Starting disk usage update"

cd "$SCRIPT_DIR" || {
    log_message "ERROR: Could not change to script directory $SCRIPT_DIR"
    rm -f "$LOCK_FILE"
    exit 1
}

# Check if collection script exists
if [ ! -f "$COLLECTION_SCRIPT" ]; then
    log_message "ERROR: Collection script not found at $COLLECTION_SCRIPT"
    rm -f "$LOCK_FILE"
    exit 1
fi

# Generate fresh disk usage data
log_message "Collecting disk usage data from $ROOT_DIR (depth $MAX_DEPTH)..."
if python3 "$COLLECTION_SCRIPT" "$ROOT_DIR" --max-depth "$MAX_DEPTH" > "$DATA_FILE" 2>/tmp/disk_usage_collection.log; then
    # Verify JSON is valid
    if python3 -m json.tool "$DATA_FILE" > /dev/null 2>&1; then
        log_message "Disk usage data collected successfully"
        
        # Get summary info
        TOTAL_SIZE=$(python3 -c "import json; d=json.load(open('$DATA_FILE')); print(d['total_size_human'])" 2>/dev/null || echo "unknown")
        TOTAL_COST=$(python3 -c "import json; d=json.load(open('$DATA_FILE')); print(f\"\\${d['total_cost']:.2f}\")" 2>/dev/null || echo "unknown")
        DIR_COUNT=$(python3 -c "import json; d=json.load(open('$DATA_FILE')); print(len(d['directories']))" 2>/dev/null || echo "unknown")
        
        log_message "Summary: $TOTAL_SIZE ($TOTAL_COST) across $DIR_COUNT directories"
        
        # Deploy to all servers independently
        SUCCESS_COUNT=0
        FAIL_COUNT=0
        
        for server in "${WEB_SERVERS[@]}"; do
            # Create remote directory if needed
            SERVER_HOST=$(echo "$server" | cut -d: -f1)
            SERVER_PATH=$(echo "$server" | cut -d: -f2)
            
            if ssh "$SERVER_HOST" "mkdir -p $SERVER_PATH" >> "$LOG_FILE" 2>&1; then
                # Deploy both JSON data and HTML
                if scp "$DATA_FILE" "$server/" >> "$LOG_FILE" 2>&1 && \
                   scp "$HTML_FILE" "$server/" >> "$LOG_FILE" 2>&1; then
                    log_message "Disk usage data deployed to $server successfully"
                    ((SUCCESS_COUNT++))
                else
                    log_message "ERROR: Failed to deploy disk usage data to $server"
                    ((FAIL_COUNT++))
                fi
            else
                log_message "ERROR: Failed to create directory on $server"
                ((FAIL_COUNT++))
            fi
        done
        
        log_message "Deployment complete: $SUCCESS_COUNT/$((SUCCESS_COUNT+FAIL_COUNT)) servers successful"
    else
        log_message "ERROR: Generated JSON is invalid"
        cat /tmp/disk_usage_collection.log >> "$LOG_FILE"
        rm -f "$LOCK_FILE"
        exit 1
    fi
else
    log_message "ERROR: Failed to collect disk usage data"
    cat /tmp/disk_usage_collection.log >> "$LOG_FILE"
    rm -f "$LOCK_FILE"
    exit 1
fi

# Clean up
rm -f "$LOCK_FILE"
rm -f /tmp/disk_usage_collection.log

# Keep only last 200 lines of log
tail -200 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"

log_message "Disk usage update completed"
