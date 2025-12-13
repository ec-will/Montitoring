#!/bin/bash
# Fetch monitoring data from jeffsc8 for anomaly detection

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_HOST="jeffsc8"
REMOTE_BASE="/e/08/erthch01/monitoring/web_dashboard"
LOCAL_DATA_DIR="$SCRIPT_DIR/data"
LOG_FILE="$SCRIPT_DIR/fetch_data.log"

# Create local data directory if it doesn't exist
mkdir -p "$LOCAL_DATA_DIR"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" | tee -a "$LOG_FILE"
}

log_message "Starting data fetch from $REMOTE_HOST"

# Fetch cluster usage data
log_message "Fetching dashboard_cluster_usage.json..."
if scp -q "$REMOTE_HOST:$REMOTE_BASE/dashboard_cluster_usage.json" "$LOCAL_DATA_DIR/"; then
    log_message "✓ dashboard_cluster_usage.json fetched successfully"
else
    log_message "✗ Failed to fetch dashboard_cluster_usage.json"
fi

# Fetch login jobs data
log_message "Fetching dashboard_login_jobs.json..."
if scp -q "$REMOTE_HOST:$REMOTE_BASE/dashboard_login_jobs.json" "$LOCAL_DATA_DIR/"; then
    log_message "✓ dashboard_login_jobs.json fetched successfully"
else
    log_message "✗ Failed to fetch dashboard_login_jobs.json"
fi

log_message "Data fetch complete"

# Show file sizes and ages
log_message "Data summary:"
for file in "$LOCAL_DATA_DIR"/*.json; do
    if [ -f "$file" ]; then
        SIZE=$(ls -lh "$file" | awk '{print $5}')
        AGE=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$file" 2>/dev/null || stat -c "%y" "$file" 2>/dev/null | cut -d. -f1)
        log_message "  $(basename "$file"): $SIZE (modified: $AGE)"
    fi
done
