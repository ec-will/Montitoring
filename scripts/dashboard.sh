#!/bin/bash

# EarthCast HPC System Dashboard
# ASCII Status Monitor - No modifications to operational scripts

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
ORANGE='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Status symbols
GREEN_DOT="●●●"
YELLOW_DOT="●●○"
ORANGE_DOT="●○○"
RED_DOT="○○○"

# Get current time
NOW=$(date +%s)
CURRENT_TIME=$(date -u +"%H:%M UTC")
CURRENT_DATE=$(date -u +"%Y-%m-%d")

# Function to get time difference in minutes
time_diff_minutes() {
    local file_time="$1"
    local current_time="$2"
    echo $(( (current_time - file_time) / 60 ))
}

# Function to get file age in minutes
get_file_age() {
    local file="$1"
    if [[ -f "$file" ]]; then
        local file_time=$(stat -c %Y "$file" 2>/dev/null)
        time_diff_minutes "$file_time" "$NOW"
    else
        echo "999"
    fi
}

# Function to check PBS queue
check_pbs_queue() {
    local queue_info=$(qstat -u erthch01 2>/dev/null | wc -l)
    local running_jobs=$((queue_info - 2))
    if [[ $running_jobs -lt 0 ]]; then running_jobs=0; fi
    echo "$running_jobs"
}

# Function to get status symbol based on condition
get_status_symbol() {
    local status="$1"
    case $status in
        "good") echo -e "${GREEN}${GREEN_DOT}${NC}" ;;
        "warning") echo -e "${YELLOW}${YELLOW_DOT}${NC}" ;;
        "error") echo -e "${ORANGE}${ORANGE_DOT}${NC}" ;;
        "critical") echo -e "${RED}${RED_DOT}${NC}" ;;
        *) echo -e "${RED}${RED_DOT}${NC}" ;;
    esac
}

# Function to check workflow status based on expected schedule
check_workflow_status() {
    local workflow="$1"
    local log_pattern="$2" 
    local expected_interval="$3"  # in minutes
    local timeout_threshold="$4" # in minutes
    
    # Find most recent log file
    local latest_log=$(ls -t $HOME/logs/*/${log_pattern}* 2>/dev/null | head -1)
    
    if [[ -z "$latest_log" ]]; then
        echo "critical"
        return
    fi
    
    local age=$(get_file_age "$latest_log")
    
    if [[ $age -lt $expected_interval ]]; then
        echo "good"
    elif [[ $age -lt $timeout_threshold ]]; then
        echo "warning"
    else
        echo "error"
    fi
}

# Main dashboard display
clear
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│                  EarthCast HPC Status                      │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  System Time: $CURRENT_TIME   Date: $CURRENT_DATE        │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  CORE PROCESSING WORKFLOWS                                  │"
echo "│                                                             │"

# Global WRF Status (should run twice daily at 03:25 and 15:25)
HOUR=$(date -u +%H)
if [[ $HOUR -ge 3 && $HOUR -le 13 ]]; then
    # 00Z cycle should be running/recently completed
    wrf_status=$(check_workflow_status "global_wrf_00z" "run_master.global00Z" 600 720)
    wrf_symbol=$(get_status_symbol "$wrf_status")
    echo "│  $wrf_symbol Global WRF 00Z    [Running/Recent] Started: 03:25 UTC        │"
elif [[ $HOUR -ge 15 ]] || [[ $HOUR -le 1 ]]; then
    # 12Z cycle should be running/recently completed  
    wrf_status=$(check_workflow_status "global_wrf_12z" "run_master.global00Z" 600 720)
    wrf_symbol=$(get_status_symbol "$wrf_status")
    echo "│  $wrf_symbol Global WRF 12Z    [Running/Recent] Started: 15:25 UTC        │"
else
    echo "│  ●●○ Global WRF        [Scheduled] Next: 15:25 UTC                │"
fi

# HiResW Status (runs at 04:38 and 16:38)
hiresw_status=$(check_workflow_status "hiresw" "master_hiresw_seq" 660 720)
hiresw_symbol=$(get_status_symbol "$hiresw_status")
echo "│  $hiresw_symbol HiResW Processing [Check Logs] Last: Check logs            │"

# Drone WX (runs every hour at :10)
drone_status=$(check_workflow_status "drone_wx" "drone_wx_seq" 60 90)
drone_symbol=$(get_status_symbol "$drone_status")
echo "│  $drone_symbol Drone Weather     [Hourly] Last: Check recent logs         │"

echo "│                                                             │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  REAL-TIME SYSTEMS                                          │"
echo "│                                                             │"

# MRMS (every 5 minutes)
mrms_status=$(check_workflow_status "mrms" "wget_mrms" 5 15)
mrms_symbol=$(get_status_symbol "$mrms_status")
echo "│  $mrms_symbol MRMS Radar        [Every 5min] Last: Check logs             │"

# Check logs cleanup (every hour at :40)
clean_status=$(check_workflow_status "cleanup" "check_logs" 60 90)  
clean_symbol=$(get_status_symbol "$clean_status")
echo "│  $clean_symbol Log Monitoring   [Hourly :40] Last: Check recent          │"

echo "│                                                             │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  SYSTEM HEALTH                                              │"
echo "│                                                             │"

# PBS Queue Status
PBS_JOBS=$(check_pbs_queue)
if [[ $PBS_JOBS -gt 0 ]]; then
    pbs_symbol=$(get_status_symbol "good")
    echo "│  $pbs_symbol PBS Queue Status   $PBS_JOBS jobs running                        │"
else
    pbs_symbol=$(get_status_symbol "warning")
    echo "│  $pbs_symbol PBS Queue Status   No jobs running                          │"
fi

# Disk Usage
DISK_USAGE=$(df $HOME | tail -1 | awk '{print $5}' | sed 's/%//')
if [[ $DISK_USAGE -lt 80 ]]; then
    disk_symbol=$(get_status_symbol "good")
elif [[ $DISK_USAGE -lt 90 ]]; then
    disk_symbol=$(get_status_symbol "warning")
else
    disk_symbol=$(get_status_symbol "error")
fi
echo "│  $disk_symbol Disk Usage        ${DISK_USAGE}% used in home directory              │"

# Recent log activity
RECENT_LOGS=$(find $HOME/logs -name "*.log" -mmin -60 | wc -l)
if [[ $RECENT_LOGS -gt 5 ]]; then
    log_symbol=$(get_status_symbol "good")
    echo "│  $log_symbol Recent Activity    $RECENT_LOGS log files updated in last hour      │"
else
    log_symbol=$(get_status_symbol "warning") 
    echo "│  $log_symbol Recent Activity    Only $RECENT_LOGS log files updated recently       │"
fi

echo "└─────────────────────────────────────────────────────────────┘"
echo ""
echo "Legend: ●●● Green (Normal)  ●●○ Yellow (Warning)  ●○○ Orange (Error)  ○○○ Red (Critical)"
echo ""
echo "Last updated: $(date -u)"
