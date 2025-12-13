#!/bin/bash
#
# Disk usage collection and deployment script for jeffsc8
# Run daily via cron to update disk usage web dashboard
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FILE="disk_usage_data.json"
LOCK_FILE="/tmp/disk_usage_update.lock"
LOG_DIR="$HOME/logs/disk-usage"
LOG_FILE="$LOG_DIR/update.log"
COLLECTION_SCRIPT="$SCRIPT_DIR/collect_disk_usage.py"
WEB_SERVER="rcity2.cottay.net"
WEB_PATH="/srv/www/earthcast/disk-usage"

# Default root directory to scan (can be overridden with first argument)
ROOT_DIR="${1:-~}"

# Maximum depth for directory scanning
MAX_DEPTH=3

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Error handler
error_exit() {
    log "ERROR: $1"
    rm -f "$LOCK_FILE"
    exit 1
}

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Check for lock file to prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    # Check if lock is stale (older than 2 hours)
    if [ -n "$(find "$LOCK_FILE" -mmin +120 2>/dev/null)" ]; then
        log "Removing stale lock file"
        rm -f "$LOCK_FILE"
    else
        log "Update already in progress (lock file exists)"
        exit 0
    fi
fi

# Create lock file
touch "$LOCK_FILE"

log "========================================="
log "Starting disk usage update"
log "Root directory: $ROOT_DIR"
log "Max depth: $MAX_DEPTH"

# Change to script directory
cd "$SCRIPT_DIR" || error_exit "Failed to change to script directory: $SCRIPT_DIR"

# Check if collection script exists
if [ ! -f "$COLLECTION_SCRIPT" ]; then
    error_exit "Collection script not found: $COLLECTION_SCRIPT"
fi

# Make collection script executable
chmod +x "$COLLECTION_SCRIPT"

# Collect disk usage data
log "Collecting disk usage data..."
if ! python3 "$COLLECTION_SCRIPT" "$ROOT_DIR" --max-depth "$MAX_DEPTH" > "$DATA_FILE" 2>> "$LOG_FILE"; then
    error_exit "Failed to collect disk usage data"
fi

# Verify JSON is valid
if ! python3 -m json.tool "$DATA_FILE" > /dev/null 2>&1; then
    error_exit "Generated JSON is invalid"
fi

log "Data collection complete"

# Get file size for logging
FILE_SIZE=$(du -h "$DATA_FILE" | cut -f1)
log "Generated data file: $DATA_FILE ($FILE_SIZE)"

# Deploy to web server
log "Deploying to web server..."

# Create remote directory if it doesn't exist
if ! ssh "$WEB_SERVER" "mkdir -p $WEB_PATH" 2>> "$LOG_FILE"; then
    error_exit "Failed to create remote directory on $WEB_SERVER"
fi

# Copy data file to web server
if ! scp "$DATA_FILE" "$WEB_SERVER:$WEB_PATH/" 2>> "$LOG_FILE"; then
    error_exit "Failed to copy data file to $WEB_SERVER"
fi

# Copy HTML file to web server
if [ -f "disk-usage.html" ]; then
    if ! scp disk-usage.html "$WEB_SERVER:$WEB_PATH/" 2>> "$LOG_FILE"; then
        error_exit "Failed to copy disk-usage.html to $WEB_SERVER"
    fi
    log "Deployed disk-usage.html to $WEB_SERVER"
fi

log "Deployment complete"
log "Web dashboard available at: http://$WEB_SERVER/disk-usage/"

# Clean up lock file
rm -f "$LOCK_FILE"

log "Disk usage update finished successfully"
log "========================================="

exit 0
