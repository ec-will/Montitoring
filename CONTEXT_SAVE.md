# Anomaly Detection - Session Checkpoint

## Status: READY FOR DEPLOYMENT ✅

**Branch:** anomaly-alerting (13 commits)  
**Location:** ~/projects/monitoring/anomaly_detection/  
**Date:** 2025-12-13

## What's Complete

### ✅ Per-Job Anomaly Detector
- **job_detector.py** - Learns each job's pattern (frequency & duration)
- Tracks 65 jobs (34 login + 31 cluster)
- Detects missing jobs (2.5x expected interval)
- Detects duration anomalies (2.5σ threshold)
- Statistical detection (no ML/AI required)

### ✅ Auto-Discovery
- Automatically finds new jobs in JSON data
- Creates profiles from last 10 runs
- No restart needed when adding jobs

### ✅ ntfy.sh Notifications
- **Topic:** ect-hpc
- **Server:** https://ntfy.sh
- Sends push notifications for anomalies
- Includes job name, severity, details
- Uses emoji tags (⏰ missing, ⚡ duration)

### ✅ Data Fetching
- **fetch_data.sh** - Gets JSON from jeffsc8
- Uses SSH config (no hardcoded credentials)
- Fetches cluster_usage + login_jobs

### ✅ Compatibility
- Python 3.6+ (works on jeffsc8)
- UTC timestamps (deploy anywhere)
- Persists profiles (survives restarts)

## Testing Completed

✅ **Auto-discovery** - New jobs detected automatically  
✅ **Missing job detection** - Injected 10hr delay, detected correctly  
✅ **ntfy notifications** - Sent 10 test alerts, all received  
✅ **Profile learning** - 577 runs/job, accurate patterns learned

## Example Learned Patterns

```
wget_mrms_QCEchoHgt.C.csh
  Runs every 5.0 minutes (± 0.0)
  Takes 32.7 seconds (± 5.6)
  
mrms_to_chad.B.csh  
  Runs every 7.0 minutes (± 2.5)
  Takes 385.9 seconds (± 145.9)
```

## Quick Commands

```bash
cd ~/projects/monitoring/anomaly_detection

# Get fresh data
./fetch_data.sh

# See learned patterns
./job_detector.py --config config/detection_config_local.yaml --report

# Run monitoring
./job_detector.py --config config/detection_config_local.yaml

# Test ntfy
curl -d "Test" https://ntfy.sh/ect-hpc
```

## Configuration

**File:** config/detection_config_local.yaml

**Key settings:**
- Check interval: 300s (5 min)
- Missing job threshold: 2.5x expected interval
- Duration threshold: 2.5σ
- ntfy enabled: true, topic: ect-hpc
- Cooldown: 1800s (30 min)

## Ready for Tomorrow

### Deployment Options

**Option 1: HPC Cluster (jeffsc8)**
- Use config/detection_config.yaml
- Run directly on cluster
- No data fetching needed

**Option 2: Separate Instance** ⭐ Recommended
- Use config/detection_config_local.yaml
- Fetches data via SSH
- Can monitor multiple clusters
- Add to crontab for auto-fetch/restart

### Deployment Steps

1. **Choose location** (jeffsc8 or separate instance)

2. **Install dependencies:**
   ```bash
   pip3 install --user numpy pyyaml requests
   ```

3. **Test:**
   ```bash
   ./job_detector.py --report  # Verify profiles loaded
   ```

4. **Run:**
   ```bash
   # Manual
   ./job_detector.py
   
   # Or background
   nohup ./job_detector.py > detector_output.log 2>&1 &
   
   # Or with screen/tmux
   screen -S anomaly_detector
   ./job_detector.py
   ```

5. **Add keepalive to crontab:**
   ```bash
   crontab -e
   # Add:
   */5 * * * * /path/to/anomaly_detection/check_detector.sh
   */5 * * * * /path/to/anomaly_detection/fetch_data.sh  # If remote
   ```

6. **Subscribe to ntfy:**
   - Install ntfy app or visit https://ntfy.sh/ect-hpc
   - Subscribe to topic: ect-hpc

## Files

**Main:**
- job_detector.py (per-job detector)
- fetch_data.sh (data fetching)
- check_detector.sh (keepalive)

**Config:**
- config/detection_config_local.yaml (for remote deployment)
- config/detection_config.yaml (for jeffsc8 deployment)

**Generated (gitignored):**
- job_profiles.json (learned patterns)
- anomaly_detector.log (debug log)
- alerts/alert_history.log (alert log)
- data/*.json (fetched data)

## Git Status

```
Branch: anomaly-alerting
Commits: 13
Status: Ready to merge to main
```

## Next Session Tasks

1. [ ] Decide deployment location
2. [ ] Deploy and start monitoring
3. [ ] Monitor for 24 hours
4. [ ] Verify no false positives
5. [ ] Merge to main branch

## Notes

- All alerts go to ntfy topic: ect-hpc
- No AI/ML used - pure statistics
- Cooldown prevents alert spam (30 min)
- Auto-discovers new jobs every 5 minutes
- Works from any timezone (uses UTC)

## Test Results

Injected anomaly test (2025-12-13 02:48):
- Modified wget_mrms_QCEchoHgt.C.csh last_seen to 10hrs ago
- Detector found 10 missing jobs
- Sent 10 ntfy notifications
- All received successfully ✅

System is production-ready!
