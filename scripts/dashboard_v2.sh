#!/bin/bash

# EarthCast HPC System Dashboard v2
# ASCII Status Monitor - Enhanced with better log parsing

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
CURRENT_HOUR=$(date -u +%H)
CURRENT_MIN=$(date -u +%M)

# Function to get file age in minutes
get_file_age() {
    local file="$1"
    if [[ -f "$file" ]]; then
        local file_time=$(stat -c %Y "$file" 2>/dev/null)
        echo $(( (NOW - file_time) / 60 ))
    else
        echo "999"
    fi
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

# Function to format time display
format_time() {
    local minutes="$1"
    if [[ $minutes -lt 60 ]]; then
        echo "${minutes}m ago"
    elif [[ $minutes -lt 1440 ]]; then
        echo "$((minutes/60))h $((minutes%60))m ago"
    else
        echo "$((minutes/1440))d ago"
    fi
}

# Function to get next scheduled time for workflow
get_next_schedule() {
    local workflow="$1"
    case $workflow in
        "global_wrf")
            if [[ $CURRENT_HOUR -lt 3 ]]; then
                echo "03:25 UTC"
            elif [[ $CURRENT_HOUR -lt 15 ]]; then
                echo "15:25 UTC" 
            else
                echo "03:25 UTC (next day)"
            fi
            ;;
        "hiresw")
            if [[ $CURRENT_HOUR -lt 4 ]]; then
                echo "04:38 UTC"
            elif [[ $CURRENT_HOUR -lt 16 ]]; then
                echo "16:38 UTC"
            else
                echo "04:38 UTC (next day)"
            fi
            ;;
        "mrms")
            local next_min=$((($CURRENT_MIN / 5 + 1) * 5))
            if [[ $next_min -ge 60 ]]; then
                echo "$(printf "%02d" $(($CURRENT_HOUR + 1))):00 UTC"
            else
                echo "${CURRENT_HOUR}:$(printf "%02d" $next_min) UTC"
            fi
            ;;
        "drone")
            if [[ $CURRENT_MIN -lt 10 ]]; then
                echo "${CURRENT_HOUR}:10 UTC"
            else
                echo "$(printf "%02d" $(($CURRENT_HOUR + 1))):10 UTC"
            fi
            ;;
    esac
}

# Function to check PBS queue details
check_pbs_details() {
    qstat -a 2>/dev/null | grep erthch01 | wc -l
}

# Get PBS job summary
get_pbs_summary() {
    local running=$(qstat -u erthch01 -s R 2>/dev/null | grep -c erthch01)
    local queued=$(qstat -u erthch01 -s Q 2>/dev/null | grep -c erthch01)
    echo "$running running, $queued queued"
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

# Global WRF Status Analysis
latest_wrf_log=$(ls -t $HOME/logs/wrf/run_master.global* 2>/dev/null | head -1)
if [[ -n "$latest_wrf_log" ]]; then
    wrf_age=$(get_file_age "$latest_wrf_log")
    if [[ $wrf_age -lt 720 ]]; then  # 12 hours
        wrf_status="good"
        wrf_detail="[Active] Last: $(format_time $wrf_age)"
    elif [[ $wrf_age -lt 1440 ]]; then  # 24 hours
        wrf_status="warning"
        wrf_detail="[Delayed] Last: $(format_time $wrf_age)"
    else
        wrf_status="error"
        wrf_detail="[Stale] Last: $(format_time $wrf_age)"
    fi
else
    wrf_status="critical"
    wrf_detail="[No logs found]"
fi
wrf_symbol=$(get_status_symbol "$wrf_status")
next_wrf=$(get_next_schedule "global_wrf")
echo "│  $wrf_symbol Global WRF        $wrf_detail Next: $next_wrf │"

# HiResW Status
latest_hiresw_log=$(ls -t $HOME/logs/hiresw/master_hiresw_seq* 2>/dev/null | head -1)
if [[ -n "$latest_hiresw_log" ]]; then
    hiresw_age=$(get_file_age "$latest_hiresw_log")
    if [[ $hiresw_age -lt 720 ]]; then
        hiresw_status="good"
        hiresw_detail="[Active] Last: $(format_time $hiresw_age)"
    else
        hiresw_status="warning" 
        hiresw_detail="[Check] Last: $(format_time $hiresw_age)"
    fi
else
    hiresw_status="error"
    hiresw_detail="[No logs found]"
fi
hiresw_symbol=$(get_status_symbol "$hiresw_status")
next_hiresw=$(get_next_schedule "hiresw")
echo "│  $hiresw_symbol HiResW Processing $hiresw_detail Next: $next_hiresw │"

# Drone WX Status
latest_drone_log=$(ls -t $HOME/logs/wrf/drone_wx_seq* 2>/dev/null | head -1)
if [[ -n "$latest_drone_log" ]]; then
    drone_age=$(get_file_age "$latest_drone_log")
    if [[ $drone_age -lt 70 ]]; then
        drone_status="good"
        drone_detail="[Current] Last: $(format_time $drone_age)"
    elif [[ $drone_age -lt 120 ]]; then
        drone_status="warning"
        drone_detail="[Delayed] Last: $(format_time $drone_age)"
    else
        drone_status="error"
        drone_detail="[Stale] Last: $(format_time $drone_age)"
    fi
else
    drone_status="critical"
    drone_detail="[No logs found]"
fi
drone_symbol=$(get_status_symbol "$drone_status")
next_drone=$(get_next_schedule "drone")
echo "│  $drone_symbol Drone Weather     $drone_detail Next: $next_drone │"

echo "│                                                             │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  REAL-TIME SYSTEMS                                          │"
echo "│                                                             │"

# MRMS Status
latest_mrms_log=$(ls -t $HOME/logs/mrms/wget_mrms_QCEchoHgt* 2>/dev/null | head -1)
if [[ -n "$latest_mrms_log" ]]; then
    mrms_age=$(get_file_age "$latest_mrms_log")
    if [[ $mrms_age -lt 10 ]]; then
        mrms_status="good"
        mrms_detail="[Current] Last: $(format_time $mrms_age)"
    elif [[ $mrms_age -lt 20 ]]; then
        mrms_status="warning"
        mrms_detail="[Delayed] Last: $(format_time $mrms_age)"
    else
        mrms_status="error"
        mrms_detail="[Stale] Last: $(format_time $mrms_age)"
    fi
else
    mrms_status="critical"
    mrms_detail="[No logs found]"
fi
mrms_symbol=$(get_status_symbol "$mrms_status")
next_mrms=$(get_next_schedule "mrms")
echo "│  $mrms_symbol MRMS Radar        $mrms_detail Next: $next_mrms │"

# Log cleanup status
latest_clean_log=$(ls -t $HOME/logs/clean/check_logs* 2>/dev/null | head -1)
if [[ -n "$latest_clean_log" ]]; then
    clean_age=$(get_file_age "$latest_clean_log")
    if [[ $clean_age -lt 70 ]]; then
        clean_status="good"
        clean_detail="[Current] Last: $(format_time $clean_age)"
    else
        clean_status="warning"
        clean_detail="[Check] Last: $(format_time $clean_age)"
    fi
else
    clean_status="error"
    clean_detail="[No logs found]"
fi
clean_symbol=$(get_status_symbol "$clean_status")
echo "│  $clean_symbol Log Monitoring   $clean_detail Next: :40 min  │"

echo "│                                                             │"
echo "├─────────────────────────────────────────────────────────────┤"
echo "│  SYSTEM HEALTH                                              │"
echo "│                                                             │"

# PBS Queue Status
PBS_SUMMARY=$(get_pbs_summary)
if echo "$PBS_SUMMARY" | grep -q "0 running, 0 queued"; then
    pbs_symbol=$(get_status_symbol "warning")
    echo "│  $pbs_symbol PBS Queue Status   No jobs active                           │"
else
    pbs_symbol=$(get_status_symbol "good")
    printf "│  %s PBS Queue Status   %-39s │\n" "$pbs_symbol" "$PBS_SUMMARY"
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
printf "│  %s Disk Usage        %s%% used in home directory              │\n" "$disk_symbol" "$DISK_USAGE"

# Recent log activity
RECENT_LOGS=$(find $HOME/logs -name "*.log" -mmin -60 | wc -l)
if [[ $RECENT_LOGS -gt 10 ]]; then
    log_symbol=$(get_status_symbol "good")
    printf "│  %s Recent Activity    %d log files updated in last hour      │\n" "$log_symbol" "$RECENT_LOGS"
elif [[ $RECENT_LOGS -gt 0 ]]; then
    log_symbol=$(get_status_symbol "warning")
    printf "│  %s Recent Activity    Only %d log files updated recently       │\n" "$log_symbol" "$RECENT_LOGS"
else
    log_symbol=$(get_status_symbol "error")
    echo "│  $log_symbol Recent Activity    No recent log activity detected           │"
fi

echo "└─────────────────────────────────────────────────────────────┘"
echo ""
echo "Legend: ●●● Green (Normal)  ●●○ Yellow (Warning)  ●○○ Orange (Error)  ○○○ Red (Critical)"
echo ""
echo "Refresh: watch -c $HOME/monitoring/scripts/dashboard_v2.sh"
echo "Last updated: $(date -u)"
