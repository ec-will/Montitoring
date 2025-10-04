#!/bin/bash

# EarthCast HPC Monitoring Dashboard - JSON Export Version
# Enhanced data collection for web dashboard display

# Check for JSON output flag
OUTPUT_JSON=false
if [[ "$1" == "--json" ]]; then
    OUTPUT_JSON=true
fi

# Colors for terminal output (only used when not JSON mode)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
ORANGE='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

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

# Function to get wrfout file count for WRF workflows
get_wrfout_count() {
    local workflow="$1"
    local logfile="$2"
    
    case $workflow in
        "global_wrf")
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
            echo "0"
            ;;
    esac
}

# Enhanced log analysis for JSON export
analyze_log_status_detailed() {
    local logfile="$1"
    local workflow="$2"
    
    if [[ ! -f "$logfile" ]]; then
        echo '{"status":"no_log","message":"No log file found","details":""}'
        return
    fi
    
    local tail_content=$(tail -15 "$logfile" 2>/dev/null)
    local age=$(get_file_age "$logfile")
    local last_modified=$(stat -c %Y "$logfile" 2>/dev/null)
    
    # Check for clear failure indicators
    if echo "$tail_content" | grep -qi "killed\|abort\|fatal\|exception"; then
        local error_msg=$(echo "$tail_content" | grep -i "killed\|abort\|fatal\|exception" | tail -1 | head -c 100)
        echo "{\"status\":\"failed\",\"message\":\"Job failed\",\"details\":\"$error_msg\",\"age_minutes\":$age,\"last_modified\":$last_modified}"
        return
    fi
    
    # Check for external data waiting
    if echo "$tail_content" | grep -qi "404.*not found.*nomads\|404.*not found.*ncep\|404.*not found.*gfs"; then
        if [[ $age -lt 30 ]]; then
            echo "{\"status\":\"waiting_data\",\"message\":\"Waiting for GFS data from NOAA\",\"details\":\"External data delay\",\"age_minutes\":$age,\"last_modified\":$last_modified}"
        else
            echo "{\"status\":\"failed\",\"message\":\"Data unavailable\",\"details\":\"Upstream data timeout\",\"age_minutes\":$age,\"last_modified\":$last_modified}"
        fi
        return
    fi
    
    # Check for active running state
    if [[ $age -lt 5 ]] && echo "$tail_content" | grep -qi "still waiting\|qsub\|date.*UTC\|PBS"; then
        echo "{\"status\":\"running\",\"message\":\"Job currently running\",\"details\":\"Active processing\",\"age_minutes\":$age,\"last_modified\":$last_modified}"
        return
    fi
    
    # Check for success
    if echo "$tail_content" | grep -q "^exit$\|cycle.*complete\|processing.*complete"; then
        echo "{\"status\":\"success\",\"message\":\"Job completed successfully\",\"details\":\"Normal completion\",\"age_minutes\":$age,\"last_modified\":$last_modified}"
        return
    fi
    
    # Default running or unknown
    if [[ $age -lt 30 ]]; then
        echo "{\"status\":\"running\",\"message\":\"Job appears to be running\",\"details\":\"Recent activity detected\",\"age_minutes\":$age,\"last_modified\":$last_modified}"
    else
        echo "{\"status\":\"unknown\",\"message\":\"Status unclear\",\"details\":\"No recent activity\",\"age_minutes\":$age,\"last_modified\":$last_modified}"
    fi
}

# Function to get comprehensive system information for JSON
get_system_info_json() {
    local uptime_info=$(uptime)
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | sed 's/^[ \t]*//')
    local disk_usage=$(df $HOME | tail -1 | awk '{print $5}' | sed 's/%//')
    local disk_usage_gb=$(df -h $HOME | tail -1 | awk '{print $3 "/" $2}')
    local memory_info=$(free -h | grep '^Mem:')
    local memory_used=$(echo $memory_info | awk '{print $3}')
    local memory_total=$(echo $memory_info | awk '{print $2}')
    local recent_logs=$(find $HOME/logs -name "*.log" -mmin -60 2>/dev/null | wc -l)
    
    cat << JSON_EOF
{
    "timestamp": $NOW,
    "current_time": "$CURRENT_TIME",
    "current_date": "$CURRENT_DATE",
    "uptime": "$uptime_info",
    "load_average": "$load_avg",
    "disk": {
        "usage_percent": $disk_usage,
        "usage_human": "$disk_usage_gb"
    },
    "memory": {
        "used": "$memory_used",
        "total": "$memory_total"
    },
    "recent_log_activity": $recent_logs
}
JSON_EOF
}

# Function to get PBS job details in JSON format
get_pbs_jobs_json() {
    local job_output=$(qstat -f -u erthch01 2>/dev/null)
    if [[ -z "$job_output" ]]; then
        echo "[]"
        return
    fi
    
    local jobs_json="["
    local first_job=true
    local current_job_id=""
    local job_name=""
    local job_state=""
    local exec_host=""
    local job_owner=""
    local queue=""
    local walltime=""
    
    while IFS= read -r line; do
        if [[ $line =~ ^Job\ Id:\ ([0-9]+)\. ]]; then
            # If we have a previous job, add it to JSON
            if [[ -n "$current_job_id" && -n "$job_name" && -n "$job_state" ]]; then
                if [[ $first_job == false ]]; then
                    jobs_json+=","
                fi
                local nodes_count="0"
                local tasks_count="0"
                if [[ -n "$exec_host" ]]; then
                    nodes_count=$(echo "$exec_host" | grep -o 'n[0-9]*' | sort -u | wc -l)
                    tasks_count=$(echo "$exec_host" | grep -o '/[0-9]*' | wc -l)
                fi
                jobs_json+="{\"job_id\":\"$current_job_id\",\"name\":\"$job_name\",\"state\":\"$job_state\",\"queue\":\"$queue\",\"nodes\":$nodes_count,\"tasks\":$tasks_count,\"walltime\":\"$walltime\",\"exec_host\":\"$exec_host\"}"
                first_job=false
            fi
            
            # Start new job
            current_job_id="${BASH_REMATCH[1]}"
            job_name=""
            job_state=""
            exec_host=""
            queue=""
            walltime=""
            
        elif [[ $line =~ ^[[:space:]]*Job_Name[[:space:]]*=[[:space:]]*(.*) ]]; then
            job_name="${BASH_REMATCH[1]}"
        elif [[ $line =~ ^[[:space:]]*job_state[[:space:]]*=[[:space:]]*(.*) ]]; then
            job_state="${BASH_REMATCH[1]}"
        elif [[ $line =~ ^[[:space:]]*exec_host[[:space:]]*=[[:space:]]*(.*) ]]; then
            exec_host="${BASH_REMATCH[1]}"
        elif [[ $line =~ ^[[:space:]]*queue[[:space:]]*=[[:space:]]*(.*) ]]; then
            queue="${BASH_REMATCH[1]}"
        elif [[ $line =~ ^[[:space:]]*Resource_List\.walltime[[:space:]]*=[[:space:]]*(.*) ]]; then
            walltime="${BASH_REMATCH[1]}"
        fi
    done <<< "$job_output"
    
    # Add the last job
    if [[ -n "$current_job_id" && -n "$job_name" && -n "$job_state" ]]; then
        if [[ $first_job == false ]]; then
            jobs_json+=","
        fi
        local nodes_count="0"
        local tasks_count="0"
        if [[ -n "$exec_host" ]]; then
            nodes_count=$(echo "$exec_host" | grep -o 'n[0-9]*' | sort -u | wc -l)
            tasks_count=$(echo "$exec_host" | grep -o '/[0-9]*' | wc -l)
        fi
        jobs_json+="{\"job_id\":\"$current_job_id\",\"name\":\"$job_name\",\"state\":\"$job_state\",\"queue\":\"$queue\",\"nodes\":$nodes_count,\"tasks\":$tasks_count,\"walltime\":\"$walltime\",\"exec_host\":\"$exec_host\"}"
    fi
    
    jobs_json+="]"
    echo "$jobs_json"
}

# Main data collection
if [[ $OUTPUT_JSON == true ]]; then
    # JSON Export Mode
    echo "{"
    echo "  \"system\": $(get_system_info_json),"
    echo "  \"workflows\": {"
    
    # Global WRF
    latest_wrf_log=$(ls -t $HOME/logs/wrf/run_master.global* 2>/dev/null | head -1)
    if [[ -n "$latest_wrf_log" ]]; then
        wrf_status_json=$(analyze_log_status_detailed "$latest_wrf_log" "global_wrf")
        wrf_file_count=$(get_wrfout_count "global_wrf" "$latest_wrf_log")
        echo "    \"global_wrf\": {\"status\": $wrf_status_json, \"file_count\": $wrf_file_count, \"log_file\": \"$(basename $latest_wrf_log)\"},"
    else
        echo "    \"global_wrf\": {\"status\": {\"status\":\"no_log\",\"message\":\"No logs found\"}, \"file_count\": 0, \"log_file\": null},"
    fi
    
    # AccuWeather Asia
    latest_accuwx_asia_log=$(ls -t $HOME/logs/wrf/accuwx_asia_seq* 2>/dev/null | head -1)
    if [[ -n "$latest_accuwx_asia_log" ]]; then
        asia_status_json=$(analyze_log_status_detailed "$latest_accuwx_asia_log" "accuwx_asia")
        asia_file_count=$(get_wrfout_count "accuwx_asia" "$latest_accuwx_asia_log")
        echo "    \"accuwx_asia\": {\"status\": $asia_status_json, \"file_count\": $asia_file_count, \"log_file\": \"$(basename $latest_accuwx_asia_log)\"},"
    else
        echo "    \"accuwx_asia\": {\"status\": {\"status\":\"no_log\",\"message\":\"No logs found\"}, \"file_count\": 0, \"log_file\": null},"
    fi
    
    # AccuWeather Europe
    latest_accuwx_euro_log=$(ls -t $HOME/logs/wrf/accuwx_euro_seq* 2>/dev/null | head -1)
    if [[ -n "$latest_accuwx_euro_log" ]]; then
        euro_status_json=$(analyze_log_status_detailed "$latest_accuwx_euro_log" "accuwx_europe")
        euro_file_count=$(get_wrfout_count "accuwx_europe" "$latest_accuwx_euro_log")
        echo "    \"accuwx_europe\": {\"status\": $euro_status_json, \"file_count\": $euro_file_count, \"log_file\": \"$(basename $latest_accuwx_euro_log)\"},"
    else
        echo "    \"accuwx_europe\": {\"status\": {\"status\":\"no_log\",\"message\":\"No logs found\"}, \"file_count\": 0, \"log_file\": null},"
    fi
    
    # MRMS
    latest_mrms_log=$(ls -t $HOME/logs/mrms/wget_mrms_QCEchoHgt* 2>/dev/null | head -1)
    if [[ -n "$latest_mrms_log" ]]; then
        mrms_status_json=$(analyze_log_status_detailed "$latest_mrms_log" "mrms")
        echo "    \"mrms\": {\"status\": $mrms_status_json, \"log_file\": \"$(basename $latest_mrms_log)\"},"
    else
        echo "    \"mrms\": {\"status\": {\"status\":\"no_log\",\"message\":\"No logs found\"}, \"log_file\": null},"
    fi
    
    # Drone Weather
    latest_drone_log=$(ls -t $HOME/logs/wrf/drone_wx_seq* 2>/dev/null | head -1)
    if [[ -n "$latest_drone_log" ]]; then
        drone_status_json=$(analyze_log_status_detailed "$latest_drone_log" "drone")
        echo "    \"drone_weather\": {\"status\": $drone_status_json, \"log_file\": \"$(basename $latest_drone_log)\"}"
    else
        echo "    \"drone_weather\": {\"status\": {\"status\":\"no_log\",\"message\":\"No logs found\"}, \"log_file\": null}"
    fi
    
    echo "  },"
    echo "  \"pbs_jobs\": $(get_pbs_jobs_json),"
    
    # Get cron jobs for future web dashboard enhancements
    echo "  \"cron_summary\": {"
    echo "    \"total_jobs\": $(crontab -l 2>/dev/null | grep -v '^#' | grep -v '^$' | wc -l),"
    echo "    \"last_updated\": $(date -r $(which crontab) +%s 2>/dev/null || echo 0)"
    echo "  }"
    
    echo "}"
else
    # Terminal mode - use existing dashboard_v18 logic
    # ... (keeping original terminal output code from dashboard_v18.sh)
    echo "Terminal mode not yet implemented in JSON version"
    echo "Use: $0 --json for JSON output"
    echo "Or use: dashboard for terminal output"
fi
