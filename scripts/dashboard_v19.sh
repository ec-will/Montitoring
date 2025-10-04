#!/bin/bash

# EarthCast HPC System Dashboard v18
# Fixed AccuWeather Europe path to data/accuwx_plus

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
ORANGE='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
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

# Function to analyze log file for success/failure/waiting states
analyze_log_status() {
    local logfile="$1"
    local workflow="$2"
    
    if [[ ! -f "$logfile" ]]; then
        echo "no_log"
        return
    fi
    
    # Get last 15 lines for analysis (increased to catch more context)
    local tail_content=$(tail -15 "$logfile" 2>/dev/null)
    local age=$(get_file_age "$logfile")
    
    # Check for clear failure indicators first (excluding data wait errors)
    if echo "$tail_content" | grep -qi "killed\|abort\|fatal\|exception"; then
        # Get the specific error for context
        local error_msg=$(echo "$tail_content" | grep -i "killed\|abort\|fatal\|exception" | tail -1 | cut -c1-50)
        echo "failed:$error_msg"
        return
    fi
    
    # Check for external data waiting (GFS, NOAA data delays) - these are true waiting states
    if echo "$tail_content" | grep -qi "404.*not found.*nomads\|404.*not found.*ncep\|404.*not found.*gfs"; then
        if [[ $age -lt 30 ]]; then
            echo "waiting_data:Waiting for GFS data from NOAA"
        else
            echo "failed:Data unavailable - upstream delay"
        fi
        return
    fi
    
    # Check for other download failures that indicate external data issues
    if echo "$tail_content" | grep -qi "waiting.*download.*gfs\|waiting.*download.*nomads"; then
        if [[ $age -lt 30 ]]; then
            echo "waiting_data:Waiting for external data download"
        else
            echo "failed:External data timeout"
        fi
        return
    fi
    
    # If file is recent (< 5 min) and has recent activity, consider it running
    # even if it contains "still waiting" (internal processing waits)
    if [[ $age -lt 5 ]] && echo "$tail_content" | grep -qi "still waiting\|qsub\|date.*UTC\|PBS"; then
        echo "running"
        return
    fi
    
    # Check for failed errors that are not data availability issues
    if echo "$tail_content" | grep -qi "error\|failed"; then
        if echo "$tail_content" | grep -qi "connection.*refused\|network.*error\|timeout"; then
            echo "failed:Network/connection error"
        else
            # Other errors that might be real failures
            local error_msg=$(echo "$tail_content" | grep -i "error\|failed" | tail -1 | cut -c1-40)
            echo "failed:$error_msg"
        fi
        return
    fi
    
    # Check for success indicators
    case $workflow in
        "global_wrf"|"accuwx_asia"|"accuwx_europe"|"hiresw"|"drone")
            # These workflows end with "exit" when successful
            if echo "$tail_content" | grep -q "^exit$"; then
                echo "success"
            elif echo "$tail_content" | grep -qi "cycle.*complete\|processing.*complete"; then
                echo "success"
            else
                # Check if it looks like it is still running (recent activity)
                if [[ $age -lt 30 ]]; then
                    echo "running"
                else
                    echo "unknown"
                fi
            fi
            ;;
        "mrms")
            # MRMS logs end with timestamp when successful
            if echo "$tail_content" | grep -q "^exit$\|$(date -u '+%a %b %d .* UTC %Y')"; then
                echo "success"
            else
                if [[ $age -lt 15 ]]; then
                    echo "running"
                else
                    echo "unknown"
                fi
            fi
            ;;
        *)
            # Default analysis
            if echo "$tail_content" | grep -q "^exit$"; then
                echo "success"
            else
                if [[ $age -lt 60 ]]; then
                    echo "running"
                else
                    echo "unknown"
                fi
            fi
            ;;
    esac
}

# Function to get status symbol and detail based on log analysis
get_workflow_status() {
    local logfile="$1"
    local workflow="$2"
    local age_minutes="$3"
    local max_age="$4"
    
    local log_status=$(analyze_log_status "$logfile" "$workflow")
    local status_type=$(echo "$log_status" | cut -d: -f1)
    local error_detail=$(echo "$log_status" | cut -d: -f2-)
    
    case $status_type in
        "success")
            if [[ $age_minutes -lt $max_age ]]; then
                echo "good:[Success] Last: $(format_time $age_minutes)"
            else
                echo "warning:[Success] Last: $(format_time $age_minutes) - Overdue"
            fi
            ;;
        "failed")
            echo "error:[Failed] $(echo $error_detail | cut -c1-35)"
            ;;
        "waiting_data")
            echo "warning:[Waiting] $(echo $error_detail | cut -c1-35)"
            ;;
        "running")
            echo "good:[Running] Active: $(format_time $age_minutes) ago"
            ;;
        "no_log")
            echo "critical:[No logs found]"
            ;;
        *)
            if [[ $age_minutes -lt $max_age ]]; then
                echo "warning:[Unknown] Last: $(format_time $age_minutes)"
            else
                echo "error:[Stale] Last: $(format_time $age_minutes)"
            fi
            ;;
    esac
}

# Function to get wrfout file count for WRF workflows
get_wrfout_count() {
    local workflow="$1"
    local logfile="$2"
    
    case $workflow in
        "global_wrf")
            # Extract date/cycle from Global WRF log filename
            local log_basename=$(basename "$logfile")
            if [[ $log_basename =~ run_master\.global([0-9]{2})Z\.36hr\.([0-9]{10})\.log ]]; then
                local cycle="${BASH_REMATCH[1]}"
                local datetime="${BASH_REMATCH[2]}"
                local date_str="${datetime:0:8}"
                local cycle_dir="$HOME/data/intel/global_0.25deg/${date_str}${cycle}"
                if [[ -d "$cycle_dir" ]]; then
                    ls "$cycle_dir"/wrfout* 2>/dev/null | wc -l
                else
                    echo "0"
                fi
            else
                echo "0"
            fi
            ;;
        "accuwx_asia")
            # Extract date/cycle from Asia log filename
            local log_basename=$(basename "$logfile")
            if [[ $log_basename =~ accuwx_asia_seq\.([0-9]{2})\.([0-9]{10})\.log ]]; then
                local cycle="${BASH_REMATCH[1]}"
                local datetime="${BASH_REMATCH[2]}"
                local date_str="${datetime:0:8}"
                local cycle_dir="$HOME/data/accuwx_asia/${date_str}${cycle}"
                if [[ -d "$cycle_dir" ]]; then
                    ls "$cycle_dir"/wrfout* 2>/dev/null | wc -l
                else
                    echo "0"
                fi
            else
                echo "0"
            fi
            ;;
        "accuwx_europe")
            # Extract date/cycle from Euro log filename
            local log_basename=$(basename "$logfile")
            if [[ $log_basename =~ accuwx_euro_seq\.([0-9]{2})\.([0-9]{10})\.log ]]; then
                local cycle="${BASH_REMATCH[1]}"
                local datetime="${BASH_REMATCH[2]}"
                local date_str="${datetime:0:8}"
                local cycle_dir="$HOME/data/accuwx_plus/${date_str}${cycle}"
                if [[ -d "$cycle_dir" ]]; then
                    ls "$cycle_dir"/wrfout* 2>/dev/null | wc -l
                else
                    echo "0"
                fi
            else
                echo "0"
            fi
            ;;
        *)
            echo "N/A"
            ;;
    esac
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
        echo "${minutes}m"
    elif [[ $minutes -lt 1440 ]]; then
        echo "$((minutes/60))h $((minutes%60))m"
    else
        echo "$((minutes/1440))d"
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

# Function to get next scheduled time for workflow
get_next_schedule() {
    local workflow="$1"
    case $workflow in
        "global_wrf")
            local next_00z=$(minutes_until 3 25)
            local next_12z=$(minutes_until 15 25)
            if [[ $next_00z -lt $next_12z ]]; then
                if [[ $next_00z -lt 60 ]]; then
                    echo "03:25 (${next_00z}m)"
                else
                    echo "03:25 UTC"
                fi
            else
                if [[ $next_12z -lt 60 ]]; then
                    echo "15:25 (${next_12z}m)"
                else
                    echo "15:25 UTC"
                fi
            fi
            ;;
        "accuwx_asia")
            local times=(4 10 16 22)
            local next_time=""
            local min_diff=9999
            for t in "${times[@]}"; do
                local diff=$(minutes_until $t 29)
                if [[ $diff -lt $min_diff ]]; then
                    min_diff=$diff
                    next_time=$(printf "%02d:29" $t)
                fi
            done
            if [[ $min_diff -lt 60 ]]; then
                echo "$next_time (${min_diff}m)"
            else
                echo "$next_time UTC"
            fi
            ;;
        "accuwx_europe")
            local times=(4 10 16 22)
            local next_time=""
            local min_diff=9999
            for t in "${times[@]}"; do
                local diff=$(minutes_until $t 28)
                if [[ $diff -lt $min_diff ]]; then
                    min_diff=$diff
                    next_time=$(printf "%02d:28" $t)
                fi
            done
            if [[ $min_diff -lt 60 ]]; then
                echo "$next_time (${min_diff}m)"
            else
                echo "$next_time UTC"
            fi
            ;;
        "hiresw")
            local next_00z=$(minutes_until 4 38)
            local next_12z=$(minutes_until 16 38)
            if [[ $next_00z -lt $next_12z ]]; then
                if [[ $next_00z -lt 60 ]]; then
                    echo "04:38 (${next_00z}m)"
                else
                    echo "04:38 UTC"
                fi
            else
                if [[ $next_12z -lt 60 ]]; then
                    echo "16:38 (${next_12z}m)"
                else
                    echo "16:38 UTC"
                fi
            fi
            ;;
        "mrms")
            local current_min=$(date -u +%M)
            local next_mins=(1 6 11 16 21 26 31 36 41 46 51 56)
            for m in "${next_mins[@]}"; do
                if [[ $current_min -lt $m ]]; then
                    local diff=$((m - current_min))
                    echo "$(printf "%02d:%02d (%dm)" $CURRENT_HOUR $m $diff)"
                    return
                fi
            done
            local next_hour=$(((CURRENT_HOUR + 1) % 24))
            local diff=$((61 - current_min))
            echo "$(printf "%02d:01 (%dm)" $next_hour $diff)"
            ;;
        "drone")
            if [[ $CURRENT_MIN -lt 10 ]]; then
                local diff=$((10 - CURRENT_MIN))
                echo "$(printf "%02d:10 (%dm)" $CURRENT_HOUR $diff)"
            else
                local next_hour=$(((CURRENT_HOUR + 1) % 24))
                local diff=$((70 - CURRENT_MIN))
                echo "$(printf "%02d:10 (%dm)" $next_hour $diff)"
            fi
            ;;
    esac
}

# Function to get PBS job details with full script names
get_pbs_job_details() {
    local job_output=$(qstat -f -u erthch01 2>/dev/null)
    if [[ -z "$job_output" ]]; then
        echo "  No active PBS jobs"
        return
    fi
    
    echo -e "  ${PURPLE}Active PBS Jobs:${NC}"
    
    # Parse the full format output
    local current_job_id=""
    local job_name=""
    local job_state=""
    local exec_host=""
    local nodes_count=""
    local tasks_count=""
    
    while IFS= read -r line; do
        if [[ $line =~ ^Job\ Id:\ ([0-9]+)\. ]]; then
            # If we have a previous job, display it
            if [[ -n "$current_job_id" && -n "$job_name" && -n "$job_state" ]]; then
                display_pbs_job "$current_job_id" "$job_name" "$job_state" "$exec_host"
            fi
            
            # Start new job
            current_job_id="${BASH_REMATCH[1]}"
            job_name=""
            job_state=""
            exec_host=""
            nodes_count=""
            tasks_count=""
            
        elif [[ $line =~ ^[[:space:]]*Job_Name[[:space:]]*=[[:space:]]*(.*) ]]; then
            job_name="${BASH_REMATCH[1]}"
            
        elif [[ $line =~ ^[[:space:]]*job_state[[:space:]]*=[[:space:]]*(.*) ]]; then
            job_state="${BASH_REMATCH[1]}"
            
        elif [[ $line =~ ^[[:space:]]*exec_host[[:space:]]*=[[:space:]]*(.*) ]]; then
            exec_host="${BASH_REMATCH[1]}"
            # Count nodes and tasks from exec_host format like "n944005/0+n944005/1"
            nodes_count=$(echo "$exec_host" | grep -o 'n[0-9]*' | sort -u | wc -l)
            tasks_count=$(echo "$exec_host" | grep -o '/[0-9]*' | wc -l)
        fi
    done <<< "$job_output"
    
    # Display the last job if it exists
    if [[ -n "$current_job_id" && -n "$job_name" && -n "$job_state" ]]; then
        display_pbs_job "$current_job_id" "$job_name" "$job_state" "$exec_host"
    fi
}

# Function to display a single PBS job
display_pbs_job() {
    local job_id="$1"
    local jobname="$2"
    local status="$3"
    local exec_host="$4"
    
    # Count nodes and tasks from exec_host
    local nodes_count="0"
    local tasks_count="0"
    if [[ -n "$exec_host" ]]; then
        nodes_count=$(echo "$exec_host" | grep -o 'n[0-9]*' | sort -u | wc -l)
        tasks_count=$(echo "$exec_host" | grep -o '/[0-9]*' | wc -l)
    fi
    
    # Format status with proper color handling
    local status_display
    case $status in
        "R") status_display="Running" ;;
        "Q") status_display="Queued" ;;
        "C") status_display="Completing" ;;
        "H") status_display="Held" ;;
        *) status_display="$status" ;;
    esac
    
    # Truncate job name if too long for display
    local display_name="$jobname"
    if [[ ${#jobname} -gt 25 ]]; then
        display_name="${jobname:0:22}..."
    fi
    
    # Format the line with colors properly applied
    case $status in
        "R") printf "    %-8s %-25s ${GREEN}%-10s${NC} (%s nodes, %s tasks)\n" "$job_id" "$display_name" "$status_display" "$nodes_count" "$tasks_count" ;;
        "Q") printf "    %-8s %-25s ${YELLOW}%-10s${NC} (%s nodes, %s tasks)\n" "$job_id" "$display_name" "$status_display" "$nodes_count" "$tasks_count" ;;
        "C") printf "    %-8s %-25s ${BLUE}%-10s${NC} (%s nodes, %s tasks)\n" "$job_id" "$display_name" "$status_display" "$nodes_count" "$tasks_count" ;;
        "H") printf "    %-8s %-25s ${ORANGE}%-10s${NC} (%s nodes, %s tasks)\n" "$job_id" "$display_name" "$status_display" "$nodes_count" "$tasks_count" ;;
        *) printf "    %-8s %-25s %-10s (%s nodes, %s tasks)\n" "$job_id" "$display_name" "$status_display" "$nodes_count" "$tasks_count" ;;
    esac
}

# Function to get upcoming jobs in next 12 hours
# Function to get upcoming jobs in next 12 hours
get_upcoming_jobs() {
    local upcoming_jobs=()
    local current_total=$((CURRENT_HOUR * 60 + CURRENT_MIN))
    
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
        
        # Handle day transition - if job time is less than current time, it's tomorrow
        if [[ $job_total -le $current_total ]]; then
            job_total=$((job_total + 1440))  # Add 24 hours for tomorrow
        fi
        
        local diff=$((job_total - current_total))
        if [[ $diff -gt 0 && $diff -le 720 ]]; then
            upcoming_jobs+=("$job")
        fi
    done
    
    # Hourly jobs
    local hourly_jobs=(
        "00:10 Drone Weather"
        "01:10 Drone Weather"
        "02:10 Drone Weather"
        "03:10 Drone Weather"
        "04:10 Drone Weather"
        "05:10 Drone Weather"
        "06:10 Drone Weather"
        "07:10 Drone Weather"
        "08:10 Drone Weather"
        "09:10 Drone Weather"
        "10:10 Drone Weather"
        "11:10 Drone Weather"
        "12:10 Drone Weather"
        "13:10 Drone Weather"
        "14:10 Drone Weather"
        "15:10 Drone Weather"
        "16:10 Drone Weather"
        "17:10 Drone Weather"
        "18:10 Drone Weather"
        "19:10 Drone Weather"
        "20:10 Drone Weather"
        "21:10 Drone Weather"
        "22:10 Drone Weather"
        "23:10 Drone Weather"
        "00:40 Log Monitoring"
        "01:40 Log Monitoring"
        "02:40 Log Monitoring"
        "03:40 Log Monitoring"
        "04:40 Log Monitoring"
        "05:40 Log Monitoring"
        "06:40 Log Monitoring"
        "07:40 Log Monitoring"
        "08:40 Log Monitoring"
        "09:40 Log Monitoring"
        "10:40 Log Monitoring"
        "11:40 Log Monitoring"
        "12:40 Log Monitoring"
        "13:40 Log Monitoring"
        "14:40 Log Monitoring"
        "15:40 Log Monitoring"
        "16:40 Log Monitoring"
        "17:40 Log Monitoring"
        "18:40 Log Monitoring"
        "19:40 Log Monitoring"
        "20:40 Log Monitoring"
        "21:40 Log Monitoring"
        "22:40 Log Monitoring"
        "23:40 Log Monitoring"
    )
    
    for job in "${hourly_jobs[@]}"; do
        local job_time=${job%% *}
        local job_hour=${job_time%%:*}
        local job_min=${job_time##*:}
        local job_total=$((${job_hour#0} * 60 + ${job_min#0}))
        
        # Handle day transition
        if [[ $job_total -le $current_total ]]; then
            job_total=$((job_total + 1440))  # Add 24 hours for tomorrow
        fi
        
        local diff=$((job_total - current_total))
        if [[ $diff -gt 0 && $diff -le 720 ]]; then
            upcoming_jobs+=("$job")
        fi
    done
    
    # Sort by time and limit to 8 jobs
    printf '%s\n' "${upcoming_jobs[@]}" | sort | head -8
}

# Main dashboard display
clear
echo "================================================================="
echo "                     EarthCast HPC Status"
echo "================================================================="
echo "  System Time: $CURRENT_TIME   Date: $CURRENT_DATE"
echo "================================================================="
echo "  CORE PROCESSING WORKFLOWS"
echo ""

# Global WRF Status Analysis
latest_wrf_log=$(ls -t $HOME/logs/wrf/run_master.global* 2>/dev/null | head -1)
if [[ -n "$latest_wrf_log" ]]; then
    wrf_age=$(get_file_age "$latest_wrf_log")
    wrf_status_detail=$(get_workflow_status "$latest_wrf_log" "global_wrf" "$wrf_age" 720)
    wrf_status=$(echo "$wrf_status_detail" | cut -d: -f1)
    wrf_detail=$(echo "$wrf_status_detail" | cut -d: -f2-)
else
    wrf_status="critical"
    wrf_detail="[No logs found]"
fi
wrf_symbol=$(get_status_symbol "$wrf_status")
wrf_next=$(get_next_schedule "global_wrf")
wrf_file_count=$(get_wrfout_count "global_wrf" "$latest_wrf_log")
printf "  %s %-20s %-35s Files: %-3s Next: %s\n" "$wrf_symbol" "Global WRF" "$wrf_detail" "$wrf_file_count" "$wrf_next"

# AccuWeather Asia Status
latest_accuwx_asia_log=$(ls -t $HOME/logs/wrf/accuwx_asia_seq* 2>/dev/null | head -1)
if [[ -n "$latest_accuwx_asia_log" ]]; then
    asia_age=$(get_file_age "$latest_accuwx_asia_log")
    asia_status_detail=$(get_workflow_status "$latest_accuwx_asia_log" "accuwx_asia" "$asia_age" 360)
    asia_status=$(echo "$asia_status_detail" | cut -d: -f1)
    asia_detail=$(echo "$asia_status_detail" | cut -d: -f2-)
else
    asia_status="critical"
    asia_detail="[No logs found]"
fi
asia_symbol=$(get_status_symbol "$asia_status")
asia_next=$(get_next_schedule "accuwx_asia")
asia_file_count=$(get_wrfout_count "accuwx_asia" "$latest_accuwx_asia_log")
printf "  %s %-20s %-35s Files: %-3s Next: %s\n" "$asia_symbol" "AccuWeather Asia" "$asia_detail" "$asia_file_count" "$asia_next"

# AccuWeather Europe Status
latest_accuwx_euro_log=$(ls -t $HOME/logs/wrf/accuwx_euro_seq* 2>/dev/null | head -1)
if [[ -n "$latest_accuwx_euro_log" ]]; then
    euro_age=$(get_file_age "$latest_accuwx_euro_log")
    euro_status_detail=$(get_workflow_status "$latest_accuwx_euro_log" "accuwx_europe" "$euro_age" 360)
    euro_status=$(echo "$euro_status_detail" | cut -d: -f1)
    euro_detail=$(echo "$euro_status_detail" | cut -d: -f2-)
else
    euro_status="critical"
    euro_detail="[No logs found]"
fi
euro_symbol=$(get_status_symbol "$euro_status")
euro_next=$(get_next_schedule "accuwx_europe")
euro_file_count=$(get_wrfout_count "accuwx_europe" "$latest_accuwx_euro_log")
printf "  %s %-20s %-35s Files: %-3s Next: %s\n" "$euro_symbol" "AccuWeather Europe" "$euro_detail" "$euro_file_count" "$euro_next"

# HiResW Status
latest_hiresw_log=$(ls -t $HOME/logs/hiresw/master_hiresw_seq* 2>/dev/null | head -1)
if [[ -n "$latest_hiresw_log" ]]; then
    hiresw_age=$(get_file_age "$latest_hiresw_log")
    hiresw_status_detail=$(get_workflow_status "$latest_hiresw_log" "hiresw" "$hiresw_age" 720)
    hiresw_status=$(echo "$hiresw_status_detail" | cut -d: -f1)
    hiresw_detail=$(echo "$hiresw_status_detail" | cut -d: -f2-)
else
    hiresw_status="critical"
    hiresw_detail="[No logs found]"
fi
hiresw_symbol=$(get_status_symbol "$hiresw_status")
hiresw_next=$(get_next_schedule "hiresw")
printf "  %s %-20s %-35s Next: %s\n" "$hiresw_symbol" "HiResW Processing" "$hiresw_detail" "$hiresw_next"

echo ""
echo "================================================================="
echo "  REAL-TIME SYSTEMS"
echo ""

# MRMS Status  
latest_mrms_log=$(ls -t $HOME/logs/mrms/wget_mrms_QCEchoHgt* 2>/dev/null | head -1)
if [[ -n "$latest_mrms_log" ]]; then
    mrms_age=$(get_file_age "$latest_mrms_log")
    mrms_status_detail=$(get_workflow_status "$latest_mrms_log" "mrms" "$mrms_age" 20)
    mrms_status=$(echo "$mrms_status_detail" | cut -d: -f1)
    mrms_detail=$(echo "$mrms_status_detail" | cut -d: -f2-)
else
    mrms_status="critical"
    mrms_detail="[No logs found]"
fi
mrms_symbol=$(get_status_symbol "$mrms_status")
mrms_next=$(get_next_schedule "mrms")
printf "  %s %-20s %-35s Next: %s\n" "$mrms_symbol" "MRMS Radar" "$mrms_detail" "$mrms_next"

# Drone WX Status
latest_drone_log=$(ls -t $HOME/logs/wrf/drone_wx_seq* 2>/dev/null | head -1)
if [[ -n "$latest_drone_log" ]]; then
    drone_age=$(get_file_age "$latest_drone_log")
    drone_status_detail=$(get_workflow_status "$latest_drone_log" "drone" "$drone_age" 120)
    drone_status=$(echo "$drone_status_detail" | cut -d: -f1)
    drone_detail=$(echo "$drone_status_detail" | cut -d: -f2-)
else
    drone_status="critical"
    drone_detail="[No logs found]"
fi
drone_symbol=$(get_status_symbol "$drone_status")
drone_next=$(get_next_schedule "drone")
printf "  %s %-20s %-35s Next: %s\n" "$drone_symbol" "Drone Weather" "$drone_detail" "$drone_next"

echo ""
echo "================================================================="
echo -e "  ${CYAN}UPCOMING JOBS (Next 12 Hours)${NC}"
echo ""

# Show upcoming jobs
mapfile -t upcoming < <(get_upcoming_jobs)
for job in "${upcoming[@]}"; do
    scheduled_symbol=$(get_status_symbol "scheduled")
    printf "  %s %s\n" "$scheduled_symbol" "$job"
done

# Show empty lines if less than 8 jobs
while [[ ${#upcoming[@]} -lt 8 ]]; do
    echo ""
    upcoming+=("")
done

echo "================================================================="
echo "  SYSTEM HEALTH"
echo ""

# PBS Queue Status with job details using -f flag
PBS_SUMMARY=$(qstat -u erthch01 2>/dev/null | grep erthch01 | wc -l)
if [[ $PBS_SUMMARY -eq 0 ]]; then
    pbs_symbol=$(get_status_symbol "warning")
    printf "  %s %-20s %s\n" "$pbs_symbol" "PBS Queue Status" "No jobs active"
else
    pbs_symbol=$(get_status_symbol "good")
    printf "  %s %-20s %d jobs active\n" "$pbs_symbol" "PBS Queue Status" "$PBS_SUMMARY"
fi

# Show detailed job information with full script names
get_pbs_job_details

echo ""

# Disk Usage
DISK_USAGE=$(df $HOME | tail -1 | awk '{print $5}' | sed 's/%//')
if [[ $DISK_USAGE -lt 80 ]]; then
    disk_symbol=$(get_status_symbol "good")
elif [[ $DISK_USAGE -lt 90 ]]; then
    disk_symbol=$(get_status_symbol "warning")
else
    disk_symbol=$(get_status_symbol "error")
fi
printf "  %s %-20s %s%% used in home directory\n" "$disk_symbol" "Disk Usage" "$DISK_USAGE"

# Recent log activity
RECENT_LOGS=$(find $HOME/logs -name "*.log" -mmin -60 | wc -l)
if [[ $RECENT_LOGS -gt 10 ]]; then
    log_symbol=$(get_status_symbol "good")
    printf "  %s %-20s %d log files updated in last hour\n" "$log_symbol" "Recent Activity" "$RECENT_LOGS"
elif [[ $RECENT_LOGS -gt 0 ]]; then
    log_symbol=$(get_status_symbol "warning")
    printf "  %s %-20s Only %d log files updated recently\n" "$log_symbol" "Recent Activity" "$RECENT_LOGS"
else
    log_symbol=$(get_status_symbol "error")
    printf "  %s %-20s %s\n" "$log_symbol" "Recent Activity" "No recent log activity detected"
fi

echo "================================================================="
echo ""
echo -e "Legend: ${GREEN}●●● Green${NC} (Success/Running)  ${YELLOW}●●○ Yellow${NC} (Warning/Waiting)  ${ORANGE}●○○ Orange${NC} (Error/Failed)  ${RED}○○○ Red${NC} (Critical)  ${BLUE}◐◐◐ Blue${NC} (Scheduled)"
echo ""
