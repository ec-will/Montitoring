# Installation Instructions - Login Job Tracker

## Quick Setup

### 1. Copy Files to Server
```bash
# From your local machine
scp dashboard_login_jobs.py start_login_tracker.sh jeffsc8:monitoring/web_dashboard/
```

### 2. Make Scripts Executable
```bash
ssh jeffsc8
cd monitoring/web_dashboard
chmod +x dashboard_login_jobs.py start_login_tracker.sh
```

### 3. Add to Crontab
```bash
crontab -e
```

Add these two lines:
```cron
# Start login job tracker on reboot
@reboot $HOME/monitoring/web_dashboard/start_login_tracker.sh

# Check every 10 minutes and restart if needed
*/10 * * * * $HOME/monitoring/web_dashboard/start_login_tracker.sh
```

### 4. Start It Manually (First Time)
```bash
cd monitoring/web_dashboard
./start_login_tracker.sh
```

### 5. Verify It's Running
```bash
# Check the process
ps aux | grep dashboard_login_jobs

# Check the lock file
cat /tmp/dashboard_login_jobs.lock

# View logs
tail -f $HOME/logs/dashboard/login_jobs.log

# Check JSON output
ls -lh dashboard_login_jobs.json
```

## How It Works

### Wrapper Script (`start_login_tracker.sh`)
- Checks if tracker is already running (via lock file)
- If running: exits quietly (no duplicate)
- If not running: starts it
- Logs all start/stop events
- Can be run repeatedly safely

### Cron Jobs
1. **`@reboot`**: Starts tracker when server boots
2. **`*/10 * * * *`**: Health check every 10 minutes
   - If tracker died, automatically restarts it
   - If tracker is running, does nothing

### Lock File
- Location: `/tmp/dashboard_login_jobs.lock`
- Contains PID of running tracker
- Automatically cleaned up on shutdown
- Stale locks are detected and removed

## Management Commands

### Check Status
```bash
# Is it running?
ps aux | grep dashboard_login_jobs.py | grep -v grep

# What's the PID?
cat /tmp/dashboard_login_jobs.lock

# View recent logs
tail -50 $HOME/logs/dashboard/login_jobs.log

# View recent tracked jobs
tail -20 dashboard_login_jobs.json
```

### Stop the Tracker
```bash
# Graceful stop (saves state)
kill -TERM $(cat /tmp/dashboard_login_jobs.lock)

# Or just kill the process
kill $(cat /tmp/dashboard_login_jobs.lock)
```

### Restart the Tracker
```bash
# Stop it
kill $(cat /tmp/dashboard_login_jobs.lock)

# Wait a moment
sleep 2

# Start it
./start_login_tracker.sh
```

### View Live Output
```bash
# Watch the log file
tail -f $HOME/logs/dashboard/login_jobs.log

# Watch tracked jobs
watch -n 5 'tail -20 dashboard_login_jobs.json'
```

## Troubleshooting

### Tracker Won't Start
```bash
# Check for errors in log
tail -50 $HOME/logs/dashboard/login_jobs.log

# Try running manually to see errors
cd monitoring/web_dashboard
./dashboard_login_jobs.py

# Check if Python 3 is available
which python3
python3 --version
```

### Duplicate Instances Running
```bash
# This should never happen, but if it does:
ps aux | grep dashboard_login_jobs.py | grep -v grep

# Kill all instances
pkill -f dashboard_login_jobs.py

# Remove lock file
rm -f /tmp/dashboard_login_jobs.lock

# Restart
./start_login_tracker.sh
```

### Lock File Issues
```bash
# Lock exists but process is dead
cat /tmp/dashboard_login_jobs.lock  # Shows PID
ps -p <PID>  # Process not found

# Solution: just run the wrapper (it will clean it up)
./start_login_tracker.sh
```

### Cron Not Starting It
```bash
# Check cron is running
ps aux | grep crond

# Verify your crontab
crontab -l | grep start_login_tracker

# Check cron logs (location varies)
tail -f /var/log/cron
# or
grep CRON /var/log/messages | tail -20

# Test the wrapper manually
./start_login_tracker.sh
echo $?  # Should be 0 on success
```

### Log File Getting Too Large
```bash
# Check size
ls -lh $HOME/logs/dashboard/login_jobs.log

# Truncate it
> $HOME/logs/dashboard/login_jobs.log

# Or set up log rotation
# Add to crontab:
0 0 * * 0 mv $HOME/logs/dashboard/login_jobs.log $HOME/logs/dashboard/login_jobs.log.$(date +\%Y\%m\%d) && gzip $HOME/logs/dashboard/login_jobs.log.*
```

## What Gets Tracked

The tracker monitors these types of scripts:
✅ Dashboard update scripts (`update_*.sh`)
✅ Data push/transfer scripts (`push_*.csh`, `*_to_chad.csh`)
✅ Data download scripts (`wget_*.csh`, `*_download.sh`)
✅ Status check scripts (`status_*.csh`, `check_*.csh`)
✅ Log cleanup and maintenance scripts

It skips these types:
❌ Scripts with `qsub` (submit PBS jobs)
❌ Scripts with `sbatch` (submit Slurm jobs)
❌ Scripts with `msub`, `bsub`, `llsubmit` (other schedulers)

## Files and Locations

```
$HOME/monitoring/web_dashboard/
├── dashboard_login_jobs.py       # Main tracker script
├── start_login_tracker.sh        # Wrapper/monitor script
├── dashboard_login_jobs.json     # Output (tracked jobs)
└── dashboard_login_jobs.json.tmp # Temp file during writes

$HOME/logs/dashboard/
└── login_jobs.log                # Tracker output/errors

/tmp/
└── dashboard_login_jobs.lock     # PID file
```

## Monitoring the Tracker Itself

Add this to your main dashboard to show tracker health:

```bash
# Check if tracker is running
if [ -f /tmp/dashboard_login_jobs.lock ]; then
    PID=$(cat /tmp/dashboard_login_jobs.lock)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✓ Login job tracker: Running (PID $PID)"
    else
        echo "✗ Login job tracker: Dead (stale lock)"
    fi
else
    echo "✗ Login job tracker: Not running"
fi

# Show latest tracked jobs
if [ -f dashboard_login_jobs.json ]; then
    JOBS=$(jq -r '.job_runs.summary.total_job_runs // 0' dashboard_login_jobs.json)
    SCRIPTS=$(jq -r '.job_runs.summary.total_unique_scripts // 0' dashboard_login_jobs.json)
    echo "  Jobs tracked: $JOBS ($SCRIPTS unique scripts)"
fi
```

## Next Steps

1. ✅ Install and start the tracker
2. ✅ Add to crontab for auto-restart
3. ✅ Let it run for a few hours to collect data
4. 🔄 Integrate into web dashboard (`update_dashboard.py`)
5. 🔄 Create visualizations in `index.html`

## Questions?

Check the full docs: `LOGIN_JOBS_README.md` and `QUICKSTART_LOGIN_JOBS.md`
