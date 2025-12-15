# Anomaly Detector Deployment on jeffsc8

## Deployment Status ✅

The anomaly detector has been deployed to jeffsc8 and is ready to run.

## Deployment Details

### Location
- **Installation Directory**: `/e/08/erthch01/monitoring/anomaly_detection/`
- **Configuration**: `config/detection_config_production.yaml`
- **Wrapper Script**: `run_anomaly_detector.sh`
- **Log File**: `anomaly_detector.log`
- **Profiles**: `job_profiles.json` (auto-generated)

### Data Sources
- **Cluster Usage**: `/e/08/erthch01/monitoring/web_dashboard/dashboard_cluster_usage.json` (updated hourly)
- **Login Jobs**: `/e/08/erthch01/monitoring/web_dashboard/dashboard_login_jobs.json` (updated continuously)

### Current Status
- ✅ Code deployed to jeffsc8
- ✅ Python dependencies installed (numpy, pyyaml, requests)
- ✅ Configuration created for production paths
- ✅ Initial profiles built (65 jobs tracked)
- ✅ Wrapper script created with lock file protection
- ✅ Tested successfully with `--report` mode
- ✅ **Crontab entry added** (running every 15 minutes)
- ✅ **Anomaly command tool deployed** at `~/will/anomaly`

## Testing Results

Ran initial test on 2024-12-15:
```
Total jobs tracked: 65

High-frequency jobs (5-minute interval):
- update_transfer_dashboard_cron.sh: 577 runs, 4.7s ±1.0s
- wget_mrms_mrgRQCComp_VIL_delta.C.csh: 577 runs, 6.2s ±1.6s
- update_dashboard_cron.sh: 577 runs, 6.8s ±1.9s
- mrms_to_chad.B.csh: runs every 7.0 min (±2.5), 384.3s ±145.3s

Medium-frequency jobs (hourly):
- extract_hrrr_hrly.B.csh: 48 runs, 1807.4s ±95.1s
- extract_test.pbs.csh: 48 runs, 2323.7s ±85.8s
- update_cluster_usage_cron.sh: 48 runs, 4.7s ±0.8s

Long-running jobs (12+ hours):
- global_extract_interp2.csh: 720.8 min interval, 4588.8s ±63.0s
- global_extract_interp2.18Z.csh: 716.6 min interval, 6077.2s ±103.0s
```

## Crontab Entry

### Recommended Schedule: Every 15 minutes

Add this line to your crontab on jeffsc8 (as user `will` or `erthch01`):

```bash
# Anomaly detector - monitors HPC job patterns and alerts on anomalies
*/15 * * * * /e/08/erthch01/monitoring/anomaly_detection/run_anomaly_detector.sh
```

### Alternative Schedules

**Every 10 minutes** (more responsive):
```bash
*/10 * * * * /e/08/erthch01/monitoring/anomaly_detection/run_anomaly_detector.sh
```

**Every 30 minutes** (lighter load):
```bash
*/30 * * * * /e/08/erthch01/monitoring/anomaly_detection/run_anomaly_detector.sh
```

## To Add Crontab Entry

On jeffsc8:
```bash
crontab -e
```

Then add the line above and save.

## Notifications

Alerts will be sent via ntfy.sh to topic `ect-hpc`:
- **Subscribe on phone**: Install ntfy app, subscribe to `ect-hpc`
- **Subscribe on desktop**: https://ntfy.sh/ect-hpc
- **Test notification**: 
  ```bash
  curl -d "Test from jeffsc8" https://ntfy.sh/ect-hpc
  ```

## Alert Types

The detector will send notifications when:

1. **Missing Job Alert** (Critical)
   - Job hasn't run when expected (> 2.5x normal interval)
   - Example: A 5-minute job that hasn't run in 13+ minutes

2. **Duration Anomaly** (Warning/Critical)
   - Job runs unusually short or long (> 2.5σ from mean)
   - Example: A job that normally takes 5 minutes runs in 30 seconds or 30 minutes

## Monitoring the Detector

### Quick Status Command (Recommended)

A unified `anomaly` command is available at `~/will/anomaly` on jeffsc8:

```bash
# Show quick status overview (default)
~/will/anomaly
~/will/anomaly status

# Full detailed report of all jobs
~/will/anomaly report

# View detector logs
~/will/anomaly log           # Last 50 lines
~/will/anomaly log 100       # Last 100 lines

# View alert history
~/will/anomaly alerts        # Last 50 alerts
~/will/anomaly alerts 20     # Last 20 alerts

# Look up specific job details
~/will/anomaly job mrms_to_chad.B.csh
~/will/anomaly job update_dashboard_cron.sh

# Show help
~/will/anomaly help
```

**Example output:**
```
═══════════════════════════════════════════════════════
    HPC Job Anomaly Detector Status
═══════════════════════════════════════════════════════

✓ Last run: 2025-12-15 01:14:42 UTC
✓ Jobs tracked: 65
✓ Profiles last saved: 2025-12-15T01:14:42.723

✓ No alerts in last 24 hours

━━━ Top 10 Most Frequent Jobs ━━━
  wget_mrms_QCEchoHgt.C.csh                           577 runs  ~    5m  ~   30s
  update_dashboard_cron.sh                            576 runs  ~    5m  ~    7s
  ...
```

### Manual Commands

If you prefer direct access:

```bash
# Check if detector is running
ps aux | grep job_detector.py

# View recent logs
tail -50 /e/08/erthch01/monitoring/anomaly_detection/anomaly_detector.log

# View alert history
tail -50 /e/08/erthch01/monitoring/anomaly_detection/alerts/alert_history.log

# Generate full status report
cd /e/08/erthch01/monitoring/anomaly_detection
python3 job_detector.py --config config/detection_config_production.yaml --report

# Check learned profiles (JSON)
cat /e/08/erthch01/monitoring/anomaly_detection/job_profiles.json | python3 -m json.tool | less
```

## Stopping/Disabling

### Temporary stop
Remove from crontab and kill any running process:
```bash
crontab -e  # Remove the line
pkill -f job_detector.py
```

### Permanent removal
```bash
rm -rf /e/08/erthch01/monitoring/anomaly_detection
```

## Troubleshooting

### No notifications received
1. Check ntfy is enabled in config: `grep -A3 ntfy config/detection_config_production.yaml`
2. Test ntfy manually: `curl -d "Test" https://ntfy.sh/ect-hpc`
3. Check for errors in log: `grep ERROR anomaly_detector.log`

### Too many false positives
Adjust sensitivity in `config/detection_config_production.yaml`:
- Increase `missing_job_multiplier` from 2.5 to 3.0 or 3.5
- Increase `duration_anomaly_sigma` from 2.5 to 3.0 or 3.5

### Not detecting real anomalies
- Decrease sensitivity thresholds
- Check if job is in profiles: `grep "job_name" job_profiles.json`
- Ensure JSON files are being updated: `ls -lh /e/08/erthch01/monitoring/web_dashboard/dashboard_*.json`

## Git Integration

The anomaly detector code is on the `anomaly-alerting` branch:
```bash
cd ~/projects/monitoring
git push origin anomaly-alerting
```

To update production deployment:
```bash
cd ~/projects/monitoring
rsync -avz anomaly_detection/ jeffsc8:/e/08/erthch01/monitoring/anomaly_detection/ --exclude 'data/' --exclude '*.pyc' --exclude 'job_profiles.json'
```

## Configuration Reference

Key settings in `config/detection_config_production.yaml`:

- `detection.check_interval`: 300 seconds (how often to run checks)
- `detection.lookback_hours`: 48 hours (historical data window)
- `detection.min_data_points`: 10 (minimum runs before alerting)
- `thresholds.missing_job_multiplier`: 2.5 (alert when > 2.5x expected interval)
- `thresholds.duration_anomaly_sigma`: 2.5 (alert when > 2.5 standard deviations)
- `alerts.cooldown_period`: 1800 seconds (don't re-alert for 30 minutes)

## Next Steps

1. ✅ Review this deployment documentation
2. ✅ Add crontab entry (running every 15 minutes)
3. ✅ Anomaly command deployed at `~/will/anomaly`
4. ⏳ Subscribe to ntfy.sh topic `ect-hpc`
5. ⏳ Monitor for first 24-48 hours for false positives
6. ⏳ Adjust sensitivity if needed
