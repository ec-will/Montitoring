# Login Node Job Tracker

## Overview

`dashboard_login_jobs.py` tracks cron jobs that actually run on the login node, as opposed to scripts that just submit work to the cluster and wait for completion.

## How It Works

### 1. Script Discovery (On Startup)
```python
# Dynamically reads crontab -l
for each cron_script:
    # Find the script file path
    script_path = find_script_path(cron_script)
    
    # Read and analyze the script content
    if is_cluster_submission_script(script_path):
        # Skip - submits jobs to cluster
        continue
    else:
        # Track - runs on login node
        login_scripts.add(cron_script)
```

This gives us the list of scripts that:
- Are scheduled in cron
- Do NOT contain job submission commands like `qsub`, `sbatch`, etc.

### 2. Process Monitoring (Every Second)
```bash
# Runs: ps -u erthch01 -o comm=
# Checks if any of the login_scripts are currently running
```

### 3. Job Lifecycle Tracking
- **Start Detection**: When a script appears in `ps` output but wasn't there before
- **End Detection**: When a script disappears from `ps` output
- **Duration Calculation**: `end_time - start_time`

### 4. Data Storage
- Saves to `dashboard_login_jobs.json` after each job completion
- Maintains 48-hour rolling window (configurable)
- Atomic writes using temp file + rename

## Output Format

The JSON output matches the structure of `dashboard_cluster_usage.json`:

```json
{
  "metadata": {
    "generator": "dashboard_login_jobs.py",
    "version": "1.0",
    "generated_at": 1699999999,
    "generated_time": "2025-11-15 01:23:45 UTC",
    "description": "48-hour login node cron job tracking",
    "data_retention_hours": 48
  },
  "job_runs": {
    "summary": {
      "total_unique_scripts": 5,
      "total_job_runs": 123,
      "total_duration_seconds": 4567.89
    },
    "jobs": {
      "update_dashboard.py": {
        "total_runs": 288,
        "total_duration_seconds": 864.50,
        "avg_duration_seconds": 3.00,
        "runs_detail": [...]
      }
    },
    "runs_detail": [
      {
        "script_name": "update_dashboard.py",
        "start": "2025-11-15T01:15:00",
        "end": "2025-11-15T01:15:03",
        "duration_seconds": 3.12
      }
    ]
  }
}
```

## Usage

### Manual Execution
```bash
cd /e/08/erthch01/monitoring/web_dashboard

# Start monitoring (runs continuously)
./dashboard_login_jobs.py

# Stop with Ctrl+C (gracefully saves state)
```

### Run as Background Service
```bash
# Start in background
nohup ./dashboard_login_jobs.py > logs/login_jobs.log 2>&1 &

# Check status
ps aux | grep dashboard_login_jobs

# Stop gracefully
kill -TERM $(cat /tmp/dashboard_login_jobs.lock)
```

### As a systemd Service (Recommended)
Create `/etc/systemd/system/dashboard-login-jobs.service`:
```ini
[Unit]
Description=EarthCast Login Node Job Tracker
After=network.target

[Service]
Type=simple
User=erthch01
WorkingDirectory=/e/08/erthch01/monitoring/web_dashboard
ExecStart=/usr/bin/python3 /e/08/erthch01/monitoring/web_dashboard/dashboard_login_jobs.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dashboard-login-jobs
sudo systemctl start dashboard-login-jobs
sudo systemctl status dashboard-login-jobs
```

## Configuration

Edit the constants at the top of `dashboard_login_jobs.py`:

```python
JSON_FILE = 'dashboard_login_jobs.json'        # Output file
CHECK_INTERVAL = 1                              # Seconds between checks
DATA_RETENTION_HOURS = 48                       # Keep data for 48 hours
LOCK_FILE = '/tmp/dashboard_login_jobs.lock'   # Single-instance lock

# Job submission commands to detect cluster submission scripts
JOB_SUBMISSION_COMMANDS = ['qsub', 'sbatch', 'msub', 'bsub', 'llsubmit']
```

## Features

### Automatic Script Discovery
- Reads `crontab -l` dynamically on startup
- No hardcoded script names
- Adapts to crontab changes (requires restart)

### Cluster Job Filtering
- Reads each cron script's content to detect job submission commands
- Looks for: `qsub`, `sbatch`, `msub`, `bsub`, `llsubmit`
- Only tracks scripts that run locally on login node
- Avoids tracking scripts that just submit work and wait

### Process Detection
- Uses `ps -u erthch01 -o comm=` for process detection
- Matches script basenames (handles full paths)
- Polls every second for responsive tracking

### Data Management
- Automatic cleanup of entries > 48 hours old
- Atomic JSON writes (temp file + rename)
- Persists state across restarts
- Graceful shutdown saves running jobs

### Safety Features
- **Lock File**: Prevents multiple instances
- **Stale Lock Detection**: Removes locks from dead processes
- **Signal Handling**: SIGINT/SIGTERM for graceful shutdown
- **Error Handling**: Continues on transient errors

## Troubleshooting

### Lock File Issues
```bash
# Check if another instance is running
ps aux | grep dashboard_login_jobs

# If no process but lock exists, remove it
rm /tmp/dashboard_login_jobs.lock
```

### Scripts Not Being Filtered Correctly
If a cluster submission script is being tracked:
```bash
# Check if the script contains job submission commands
grep -E 'qsub|sbatch|msub|bsub' /path/to/script.sh

# If it does but isn't being detected, check the search paths in find_script_path()
# or add the path to the search_paths list in dashboard_login_jobs.py
```

### Scripts Not Detected
- Check crontab: `crontab -l`
- Verify script can be found by checking common paths in `find_script_path()`
- Test: `ps -u erthch01 -o comm=` while script is running
- Check if script path is readable: `ls -l /path/to/script.sh`

### JSON Output Issues
- Check disk space: `df -h`
- Check permissions: `ls -l dashboard_login_jobs.json`
- View logs if running as service: `journalctl -u dashboard-login-jobs -f`

## Integration with Web Dashboard

To display this data on the web dashboard:

1. **Update `update_dashboard.py`** to read `dashboard_login_jobs.json`
2. **Add to dashboard JSON** alongside cluster usage data
3. **Create visualization** in `index.html` to show:
   - Login job activity timeline
   - Most frequent login jobs
   - Average duration per script
   - Comparison: cluster vs login node utilization

Example integration in `update_dashboard.py`:
```python
def get_login_jobs_data():
    try:
        with open('dashboard_login_jobs.json', 'r') as f:
            return json.load(f)
    except:
        return None

# In main dashboard data:
dashboard_data['login_jobs'] = get_login_jobs_data()
```

## Differences from Cluster Job Tracking

| Aspect | Cluster Jobs (`dashboard_cluster_usage.py`) | Login Jobs (`dashboard_login_jobs.py`) |
|--------|---------------------------------------------|----------------------------------------|
| **Data Source** | `myusage` command (historical) | `ps` command (real-time) |
| **Execution** | One-time snapshot | Continuous monitoring |
| **Detection** | Completed jobs from scheduler | Active processes in real-time |
| **Duration Source** | Scheduler records | Start/end timestamps |
| **Resource Usage** | Core-hours on cluster nodes | Runtime on login node |
| **Update Frequency** | Hourly via cron | Every second |

## Future Enhancements

1. **CPU Usage Tracking**: Add `ps -u erthch01 -o comm,pcpu` to track CPU percentage
2. **Memory Usage**: Track memory consumption per job
3. **Multiple Users**: Extend to track multiple users
4. **Historical Trends**: Add daily/weekly aggregations
5. **Alerting**: Detect jobs taking unusually long
6. **Web API**: REST endpoint for live job status

## Testing

Test the script on your development machine:

```bash
# Create a simple cron job to test
(crontab -l 2>/dev/null; echo "* * * * * sleep 5") | crontab -

# Run the tracker
./dashboard_login_jobs.py

# In another terminal, trigger the cron manually
sleep 5

# Should see the job detected and tracked
```
