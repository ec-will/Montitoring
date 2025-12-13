#!/bin/bash
# EarthCast Dashboard Login Jobs Timeline Deployment Script

SCRIPT_DIR="/e/08/erthch01/monitoring/web_dashboard"
LOG_DIR="/e/08/erthch01/logs/dashboard"
LOCK_FILE="/tmp/login_timeline_deploy.lock"
LOG_FILE="$LOG_DIR/deploy_login_timeline.log"

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
        log_message "Login timeline deployment already running (lock file exists), skipping"
        exit 0
    else
        log_message "Stale lock file detected, removing and continuing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
touch "$LOCK_FILE"

log_message "Starting login jobs timeline deployment"

cd "$SCRIPT_DIR" || {
    log_message "ERROR: Could not change to script directory $SCRIPT_DIR"
    rm -f "$LOCK_FILE"
    exit 1
}

# Check if login jobs JSON exists
if [ ! -f "dashboard_login_jobs.json" ]; then
    log_message "ERROR: dashboard_login_jobs.json not found (login tracker may not be running)"
    rm -f "$LOCK_FILE"
    exit 1
fi

# Generate HTML timeline from JSON
if python3 web_server_login_timeline_plot.py dashboard_login_jobs.json login_jobs_timeline.html > /tmp/login_timeline_deploy_output.log 2>&1; then
    log_message "Login jobs timeline HTML generated successfully"
    
    # Push HTML to primary server
    if scp login_jobs_timeline.html will@rcity2.cottay.net:/srv/www/earthcast >> "$LOG_FILE" 2>&1; then
        log_message "Login jobs timeline deployed to rcity2.cottay.net successfully"
        
        # Push HTML to secondary server
        if scp login_jobs_timeline.html will@ect-hpc.wx-farms.com:/srv/www/earthcast >> "$LOG_FILE" 2>&1; then
            log_message "Login jobs timeline deployed to ect-hpc.wx-farms.com successfully"
        else
            log_message "WARNING: Failed to deploy login jobs timeline to ect-hpc.wx-farms.com"
        fi
        
        # Log summary info
        HTML_SIZE=$(ls -lh login_jobs_timeline.html | awk '{print $5}')
        JSON_SIZE=$(ls -lh dashboard_login_jobs.json | awk '{print $5}')
        UNIQUE_SCRIPTS=$(cat dashboard_login_jobs.json | jq '.metadata.total_unique_scripts' 2>/dev/null || echo "unknown")
        TOTAL_JOBS=$(cat dashboard_login_jobs.json | jq '.metadata.total_jobs' 2>/dev/null || echo "unknown")
        log_message "Deployment complete: JSON=$JSON_SIZE, HTML=$HTML_SIZE, $UNIQUE_SCRIPTS unique scripts, $TOTAL_JOBS total jobs"
    else
        log_message "ERROR: Failed to deploy login jobs timeline to primary server (rcity2.cottay.net)"
    fi
else
    log_message "ERROR: Failed to generate login jobs timeline HTML"
    cat /tmp/login_timeline_deploy_output.log >> "$LOG_FILE"
fi

# Clean up
rm -f "$LOCK_FILE"
rm -f /tmp/login_timeline_deploy_output.log

# Keep only last 100 lines of log
tail -100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"

log_message "Login jobs timeline deployment completed"
