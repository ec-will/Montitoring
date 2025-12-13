# Quick Start: Login Job Tracking

## What Does This Do?

Tracks cron jobs that run **on the login node** (not submitted to the cluster). This helps distinguish between:
- Scripts that submit work to the cluster and wait (tracked by `dashboard_cluster_usage.py`)
- Scripts that actually execute on the login node (tracked by `dashboard_login_jobs.py`)

## Installation

```bash
cd /e/08/erthch01/monitoring/web_dashboard

# Make executable
chmod +x dashboard_login_jobs.py
```

## Usage

### Start Monitoring
```bash
# Foreground (for testing)
./dashboard_login_jobs.py

# Background (production)
nohup ./dashboard_login_jobs.py > logs/login_jobs.log 2>&1 &

# As systemd service (best)
sudo cp systemd/dashboard-login-jobs.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dashboard-login-jobs
sudo systemctl start dashboard-login-jobs
```

### Check Status
```bash
# Is it running?
ps aux | grep dashboard_login_jobs

# View recent output
tail -f dashboard_login_jobs.json

# Check logs (if running as service)
journalctl -u dashboard-login-jobs -f
```

### Stop Monitoring
```bash
# Graceful shutdown (saves state)
kill -TERM $(cat /tmp/dashboard_login_jobs.lock)

# Or use Ctrl+C if running in foreground
```

## What It Tracks

### Automatic Discovery
1. Reads your `crontab -l` to find scheduled scripts
2. For each script, tries to find and read its contents
3. Analyzes script content for job submission commands (`qsub`, `sbatch`, etc.)
4. Tracks only scripts that:
   - Are in your crontab
   - Do NOT contain job submission commands (so they run locally)

### Data Collected
- Script name
- Start time (ISO format)
- End time (ISO format)
- Duration (seconds)

### Output File
`dashboard_login_jobs.json` - Updated after each job completes
```json
{
  "metadata": {...},
  "job_runs": {
    "summary": {
      "total_unique_scripts": 5,
      "total_job_runs": 288,
      "total_duration_seconds": 1234.56
    },
    "jobs": {
      "update_dashboard.py": {
        "total_runs": 288,
        "total_duration_seconds": 864.0,
        "avg_duration_seconds": 3.0,
        "runs_detail": [...]
      }
    }
  }
}
```

## How It Works

```
Startup:
  ┌─────────────────┐
  │ Read crontab -l │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────────────────────┐
  │ For each cron script:           │
  │   1. Find script file path      │
  │   2. Read script content        │
  │   3. Check for qsub/sbatch/etc  │
  └────────┬────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────┐
  │ Filter: Keep only scripts that  │
  │ DON'T contain job submission    │
  │ commands = login_scripts        │
  └────────┬────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────┐
  │ Load previous completed jobs    │
  └────────┬────────────────────────┘
           │
           ▼

Every Second:
  ┌─────────────────────────────────┐
  │ Run: ps -u erthch01 -o comm=   │
  └────────┬────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────┐
  │ Compare with login_scripts      │
  └────────┬────────────────────────┘
           │
           ├─ New process? ────▶ Record start_time
           │
           └─ Disappeared? ────▶ Record end_time
                                 Calculate duration
                                 Save to JSON
                                 
Every 5 Minutes:
  ┌─────────────────────────────────┐
  │ Clean up jobs > 48 hours old    │
  │ Re-save JSON                     │
  │ Print status                     │
  └─────────────────────────────────┘
```

## Example Scripts That Get Tracked

### Yes (tracked by login_jobs)
- `update_dashboard.py` - Generates dashboard data locally
- `cleanup_logs.sh` - Deletes old log files
- `backup_config.sh` - Copies config files
- `check_disk_space.sh` - Monitors disk usage

### No (tracked by cluster_usage)
- `run_accuwx_*.csh` - Submits WRF jobs to cluster
- `metgrid_*.csh` - Submits preprocessing to cluster
- `extract_*.csh` - Submits data extraction to cluster

## Troubleshooting

### "Another instance is already running"
```bash
# Check if really running
ps aux | grep dashboard_login_jobs

# If not, remove stale lock
rm /tmp/dashboard_login_jobs.lock
```

### Scripts not being detected
```bash
# 1. Check your crontab
crontab -l

# 2. Make sure script names are extracted correctly
# (Script looks for first thing with '/' or '.' in command)

# 3. Check if script contains job submission commands
grep -E 'qsub|sbatch|msub' /path/to/your/script.sh

# 4. Test process detection manually
ps -u erthch01 -o comm= | grep your_script_name
```

### JSON not updating
```bash
# Check if tracker is running
ps aux | grep dashboard_login_jobs

# Check for errors in logs
tail -f logs/login_jobs.log  # if running with nohup
journalctl -u dashboard-login-jobs -n 50  # if running as service

# Check disk space
df -h /e/08/erthch01
```

## Testing

```bash
# Run the test script
./test_login_jobs.sh

# This will:
# 1. Check if tracker is running
# 2. Create test scripts
# 3. Run them in background
# 4. Wait for completion
# 5. Show the tracked results
# 6. Clean up
```

## Integration with Web Dashboard

Once this is running, you can display the data on your web dashboard:

### 1. Update `update_dashboard.py`
```python
def get_login_jobs_data():
    """Load login node job tracking data"""
    try:
        with open('dashboard_login_jobs.json', 'r') as f:
            return json.load(f)
    except:
        return None

# Add to main dashboard data
dashboard_data['login_jobs'] = get_login_jobs_data()
```

### 2. Update `index.html`
Add a new section to display:
- Currently running login jobs
- Recent completed login jobs
- Most frequent login jobs
- Average duration per script
- Timeline visualization

## Comparison: Cluster vs Login Jobs

| Metric | Cluster Jobs | Login Jobs |
|--------|--------------|------------|
| **Tracked by** | `dashboard_cluster_usage.py` | `dashboard_login_jobs.py` |
| **Data source** | `myusage` command | `ps` command |
| **Frequency** | Hourly snapshot | Real-time (1s polling) |
| **Resource metric** | Core-hours | Duration (seconds) |
| **Runs on** | Compute nodes | Login node |
| **Examples** | WRF, metgrid, real | Dashboard updates, cleanup scripts |

## Next Steps

1. ✅ Start the tracker
2. ✅ Let it collect data for a few hours
3. ✅ Run the test script to verify
4. ✅ Integrate into web dashboard
5. 🔄 Monitor logs for any issues
6. 🔄 Adjust CHECK_INTERVAL or DATA_RETENTION_HOURS if needed
7. 🔄 Set up systemd service for automatic restart

## Configuration Options

Edit top of `dashboard_login_jobs.py`:

```python
CHECK_INTERVAL = 1        # Check every 1 second (default)
                          # Increase if CPU usage is a concern
                          # Decrease for more responsive tracking

DATA_RETENTION_HOURS = 48 # Keep 48 hours of data (default)
                          # Increase to keep more history
                          # Decrease to reduce JSON file size
```

## Questions?

See the full documentation: `LOGIN_JOBS_README.md`
