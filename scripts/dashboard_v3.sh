#!/bin/bash

# EarthCast HPC System Dashboard v3
# Enhanced with upcoming jobs visibility

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
ORANGE='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Status symbols
GREEN_DOT="●●●"
YELLOW_DOT="●●○"
ORANGE_DOT="●○○"
RED_DOT="○○○"
BLUE_DOT="◐◐◐"

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
        "scheduled") echo -e "${BLUE}${BLUE_DOT}${NC}" ;;
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

# Function to calculate minutes until next occurrence
minutes_until() {
    local target_hour=$1
    local target_min=$2
    local current_hour=$(date -u +%H)
    local current_min=$(date -u +%M)
    
    # Convert to minutes from midnight
    local target_total=$((target_hour * 60 + target_min))
    local current_total=$((current_hour * 60 + current_min))
    
    local diff=$((target_total - current_total))
    
    # If negative, it's tomorrow
    if [[ $diff -le 0 ]]; then
        diff=$((1440 + diff))
    fi
    
    echo $diff
}

# Function to get upcoming jobs in next 4 hours
get_upcoming_jobs() {
    local upcoming_jobs=()
    local current_total=$((CURRENT_HOUR * 60 + CURRENT_MIN))
    
    # Check various job schedules
    # Hourly jobs
    for minute in 03 06 10 13 32 30 40; do
        for hour in $(seq 0 23); do
            local job_total=$((hour * 60 + ${minute#0}))
            local diff=$((job_total - current_total))
            if [[ $diff -gt 0 && $diff -le 240 ]]; then  # next 4 hours
                case $minute in
                    03) upcoming_jobs+=("$(printf "%02d:%02d Wave Processing" $hour $minute)") ;;
                    06) upcoming_jobs+=("$(printf "%02d:%02d Wind/Direction Data" $hour $minute)") ;;
                    10) upcoming_jobs+=("$(printf "%02d:%02d Drone Weather" $hour $minute)") ;;
                    13) upcoming_jobs+=("$(printf "%02d:%02d GTG Turbulence" $hour $minute)") ;;
                    30) upcoming_jobs+=("$(printf "%02d:%02d Azure Euro Main" $hour $minute)") ;;
                    32) upcoming_jobs+=("$(printf "%02d:%02d Azure Euro Push" $hour $minute)") ;;
                    40) upcoming_jobs+=("$(printf "%02d:%02d Log Monitoring" $hour $minute)") ;;
                esac
            fi
        done
    done
    
    # Major scheduled jobs
    local major_jobs=(
        "03:25 Global WRF 00Z"
        "15:25 Global WRF 12Z"
        "04:28 AccuWeather Europe 00Z"
        "04:29 AccuWeather Asia 00Z"
        "10:28 AccuWeather Europe 06Z" 
        "10:29 AccuWeather Asia 06Z"
        "16:28 AccuWeather Europe 12Z"
        "16:29 AccuWeather Asia 12Z"
        "22:28 AccuWeather Europe 18Z"
        "22:29 AccuWeather Asia 18Z"
        "04:38 HiResW 00Z"
        "16:38 HiResW 12Z"
        "07:00 Contrails 00Z"
        "19:00 Contrails 12Z"
    )
    
    for job in "${major_jobs[@]}"; do
        local job_time=${job%% *}
        local job_hour=${job_time%%:*}
        local job_min=${job_time##*:}
        local job_total=$((${job_hour#0} * 60 + ${job_min#0}))
        local diff=$((job_total - current_total))
        if [[ $diff -gt 0 && $diff -le 240 ]]; then
            upcoming_jobs+=("$job")
        fi
    done
    
    # Sort by time and return first 5
    printf '%s\n' "${upcoming_jobs[@]}" | sort | head -5
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
    if [[ $wrf_age -lt 720 ]]; then
        wrf_status="good"
        wrf_detail="[Active] Last: $(format_time $wrf_age)"
    elif [[ $wrf_age -lt 1440 ]]; then
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

# Check if Global WRF should be starting soon
wrf_next_mins=$(minutes_until 3 25)
if [[ $wrf_next_mins -le 30 ]]; then
    wrf_detail="$wrf_detail ⚡STARTING IN ${wrf_next_mins}m!"
fi
echo "│  $wrf_symbol Global WRF        $wrf_detail"

# AccuWeather Asia/Europe Status
latest_accuwx_asia_log=$(ls -t $HOME/logs/wrf/accuwx_asia_seq* 2>/dev/null | head -1)
if [[ -n "$latest_accuwx_asia_log" ]]; then
    asia_age=$(get_file_age "$latest_accuwx_asia_log")
    if [[ $asia_age -lt 360 ]]; then
        asia_status="good"
        asia_detail="[Active] Last: $(format_time $asia_age)"
    else
        asia_status="warning"
        asia_detail="[Check] Last: $(format_time $asia_age)"
    fi
else
    asia_status="error"  
    asia_detail="[No logs found]"
fi
asia_symbol=$(get_status_symbol "$asia_status")
echo "│  $asia_symbol AccuWeather Asia   $asia_detail"

latest_accuwx_euro_log=$(ls -t $HOME/logs/wrf/accuwx_euro_seq* 2>/dev/null | head -1)
if [[ -n "$latest_accuwx_euro_log" ]]; then
    euro_age=$(get_file_age "$latest_accuwx_euro_log")
    if [[ $euro_age -lt 360 ]]; then
        euro_status="good"
        euro_detail="[Active] Last: $(format_time $euro_age)"
    else
        euro_status="warning"
        euro_detail="[Check] Last: $(format_time $euro_age)"
    fi
else
    euro_status="error"
    euro_detail="[No logs found]"
fi
euro_symbol=$(get_status_symbol "$euro_status")
echo "│  $euro_symbol AccuWeather Europe $euro_detail"

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
echo "│  $hiresw_symbol HiResW Processing $hiresw_detail"

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
echo "│  $mrms_symbol MRMS Radar        $mrms_detail"

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

# Check if drone job is coming up soon
drone_next_mins=$(minutes_until $CURRENT_HOUR 10)
if [[ $drone_next_mins -le 10 && $drone_next_mins -gt 0 ]]; then
    drone_detail="$drone_detail (Next in ${drone_next_mins}m)"
fi
echo "│  $drone_symbol Drone Weather     $drone_detail"

echo "│                                                             │"
echo "├─────────────────────────────────────────────────────────────┤"
echo -e "│  ${CYAN}UPCOMING JOBS (Next 4 Hours)${NC}                               │"
echo "│                                                             │"

# Show upcoming jobs
mapfile -t upcoming < <(get_upcoming_jobs)
for job in "${upcoming[@]}"; do
    scheduled_symbol=$(get_status_symbol "scheduled")
    printf "│  %s %-55s │\n" "$scheduled_symbol" "$job"
done

# Pad if less than 5 jobs
while [[ ${#upcoming[@]} -lt 5 ]]; do
    echo "│                                                             │"
    upcoming+=("")
done

echo "├─────────────────────────────────────────────────────────────┤"
echo "│  SYSTEM HEALTH                                              │"
echo "│                                                             │"

# PBS Queue Status
PBS_SUMMARY=$(qstat -u erthch01 2>/dev/null | grep erthch01 | wc -l)
if [[ $PBS_SUMMARY -eq 0 ]]; then
    pbs_symbol=$(get_status_symbol "warning")
    echo "│  $pbs_symbol PBS Queue Status   No jobs active                           │"
else
    pbs_symbol=$(get_status_symbol "good")
    printf "│  %s PBS Queue Status   %d jobs active                        │\n" "$pbs_symbol" "$PBS_SUMMARY"
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
echo "Legend: ●●● Green (Normal)  ●●○ Yellow (Warning)  ●○○ Orange (Error)  ○○○ Red (Critical)  ◐◐◐ Blue (Scheduled)"
echo ""
echo "Auto-refresh: watch -c -n 30 $HOME/monitoring/scripts/dashboard_v3.sh"
echo "Last updated: $(date -u)"
