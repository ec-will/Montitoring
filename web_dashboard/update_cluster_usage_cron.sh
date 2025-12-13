#!/bin/bash
# EarthCast Dashboard Cluster Usage Update Script

# Set environment variables for myusage command
export PATH="/usr/login/bin:$PATH"
export PERL5LIB="/usr/login/share/perl5"
# Runs less frequently than main dashboard (e.g., every hour)

SCRIPT_DIR="/e/08/erthch01/monitoring/web_dashboard"
LOG_DIR="/e/08/erthch01/logs/dashboard"
LOCK_FILE="/tmp/cluster_usage_update.lock"
LOG_FILE="$LOG_DIR/update_cluster_usage.log"

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
        log_message "Cluster usage update already running (lock file exists), skipping"
        exit 0
    else
        log_message "Stale lock file detected, removing and continuing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
touch "$LOCK_FILE"

log_message "Starting cluster usage data update"

cd "$SCRIPT_DIR" || {
    log_message "ERROR: Could not change to script directory $SCRIPT_DIR"
    rm -f "$LOCK_FILE"
    exit 1
}

# Generate cluster usage data
if python3 dashboard_cluster_usage.py > /tmp/cluster_usage_update_output.log 2>&1; then
    log_message "Cluster usage data generated successfully"
    
    # Generate HTML timeline from JSON
    if python3 web_server_timeline_plot.py dashboard_cluster_usage.json cluster_usage_timeline.html >> /tmp/cluster_usage_update_output.log 2>&1; then
        log_message "Cluster usage timeline HTML generated successfully"
        
        # Push HTML to primary server
        if scp cluster_usage_timeline.html will@rcity2.cottay.net:/srv/www/earthcast >> "$LOG_FILE" 2>&1; then
            log_message "Cluster usage timeline deployed to rcity2.cottay.net successfully"
            
            # Push HTML to secondary server
            if scp cluster_usage_timeline.html will@ect-hpc.wx-farms.com:/srv/www/earthcast >> "$LOG_FILE" 2>&1; then
                log_message "Cluster usage timeline deployed to ect-hpc.wx-farms.com successfully"
            else
                log_message "WARNING: Failed to deploy cluster usage timeline to ect-hpc.wx-farms.com"
            fi
            
            # Log summary info
            HTML_SIZE=$(ls -lh cluster_usage_timeline.html | awk '{print $5}')
            JSON_SIZE=$(ls -lh dashboard_cluster_usage.json | awk '{print $5}')
            UNIQUE_JOBS=$(cat dashboard_cluster_usage.json | jq '.job_usage.summary.total_unique_jobs' 2>/dev/null || echo "unknown")
            CORE_HOURS=$(cat dashboard_cluster_usage.json | jq '.job_usage.summary.total_core_hours' 2>/dev/null || echo "unknown")
            log_message "Update complete: JSON=$JSON_SIZE, HTML=$HTML_SIZE, $UNIQUE_JOBS unique jobs, $CORE_HOURS core-hours"
        else
            log_message "ERROR: Failed to deploy cluster usage timeline to primary server (rcity2.cottay.net)"
        fi
    else
        log_message "ERROR: Failed to generate cluster usage timeline HTML"
        cat /tmp/cluster_usage_update_output.log >> "$LOG_FILE"
    fi
else
    log_message "ERROR: Failed to generate cluster usage data"
    cat /tmp/cluster_usage_update_output.log >> "$LOG_FILE"
fi

# Clean up
rm -f "$LOCK_FILE"
rm -f /tmp/cluster_usage_update_output.log

# Keep only last 100 lines of log
tail -100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"

log_message "Cluster usage data update completed"
