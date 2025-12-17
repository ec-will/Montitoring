# Anomaly Detection Session Context

**Date**: December 17, 2025  
**Branch**: `anomaly-alerting`  
**Status**: Production deployment successful, improvements documented

---

## Session Summary

Fixed critical bug in anomaly detector and added duration anomaly detection, then documented the entire system comprehensively.

---

## What We Did

### 1. Fixed Profile Update Bug

**Problem**: Detector metrics weren't updating on jeffsc8 - jobs showed "last seen 67+ hours ago" even though data sources were fresh.

**Root Cause**: The `_update_existing_profiles()` method didn't exist. The detector only:
- Discovered **new** jobs
- Detected **missing** jobs
- But never **updated** existing job profiles with new runs from JSON data

**Solution**: 
- Added `_update_existing_profiles()` method that reads JSON data and updates profiles with runs newer than `last_seen`
- Integrated it into the continuous monitoring loop
- Processes both login jobs and cluster jobs

**Result**:
- Initial run processed 5,750 backlogged runs from 3-day gap
- Now processes ~10-15 new runs every 5 minutes
- `last_seen` timestamps now accurate (e.g., "3.4 hours ago" instead of "67 hours ago")

**Commits**:
- `142142d` - Fix: Update existing job profiles with new runs in continuous monitoring

---

### 2. Added Duration Anomaly Detection

**Problem**: Detector only watched for missing jobs, not jobs that ran too fast/slow.

**Implementation**:
- Check each new run for duration anomalies **before** adding to profile
- Uses 2.5σ threshold (configurable)
- Detects both too-fast (early exit/failure) and too-slow (performance issues)
- 30-minute cooldown to prevent alert spam
- Only checks **new** runs going forward (not historical backlog)

**Detection Method**:
```python
z_score = abs(duration - duration_mean) / duration_std
if z_score >= 2.5:
    alert("Duration Anomaly")
```

**Examples**:
- Job normally takes 1800s ± 95s
- Warning: <1562s or >2037s (2.5σ)
- Critical: <1515s or >2085s (3.0σ)

**Commits**:
- `d579818` - Add duration anomaly detection for new job runs

---

### 3. Comprehensive System Documentation

Created `SYSTEM_REPORT.md` documenting:
- Complete system architecture with ASCII diagrams
- Data collection dependencies (myusage, ps monitoring)
- Statistical learning algorithms with examples
- Configuration reference
- Deployment guide (file locations, cron, dependencies)
- CLI tool documentation
- Performance metrics and scalability
- 12 suggestions for future improvements

**Commits**:
- `ce3e2ee` - Add comprehensive system report for anomaly detection

---

## Current System State

### Deployment
- **Location**: jeffsc8 at `/e/08/erthch01/monitoring/anomaly_detection/`
- **Status**: Running in production
- **Process ID**: 2999701 (as of 22:10 UTC)
- **Monitoring**: 80 jobs (65 cluster, ~15 login node)

### Data Sources
- `dashboard_cluster_usage.json` - Updated hourly (150KB)
- `dashboard_login_jobs.json` - Updated real-time (2.1MB)

### Detector Behavior
- Check interval: 5 minutes (300 seconds)
- Profile save: Every 12 cycles (1 hour)
- Missing job alerts: No cooldown (alert every cycle)
- Duration anomaly alerts: 30-minute cooldown

### Current Alerts (as of 22:10 UTC)
- `run_accuwx_0833.v371.asia.A.csh` - Missing 3.6 hours (Critical)
- `run_accuwx_0833.v371.euro_plus.A.csh` - Missing 3.7 hours (Critical)
- `extract_test.pbs.csh` - Missing 3.2 hours (Warning)
- `extract_test.euro.csh` - Missing 3.4 hours (Warning)
- Several others - see `anomaly alerts` for full list

---

## Key Files Modified

### Core Detection Engine
- `anomaly_detection/job_detector.py`
  - Added `_update_existing_profiles()` method (lines 318-400)
  - Modified continuous loop to call update and check duration anomalies
  - Returns tuple: `(updated_count, duration_anomalies)`

### Configuration (jeffsc8)
- `/e/08/erthch01/monitoring/anomaly_detection/config/detection_config_production.yaml`
  - `check_interval: 300` (5 minutes)
  - `missing_job_multiplier: 2.5`
  - `duration_anomaly_sigma: 2.5`
  - `cooldown_period: 1800` (30 minutes, duration only)
  - `learning_mode: true` (not fully implemented)

### Job Profiles (auto-generated)
- `/e/08/erthch01/monitoring/anomaly_detection/job_profiles.json`
  - 80 jobs tracked
  - Last saved: 2025-12-17T21:03:29
  - Keeps last 100 intervals and durations per job

---

## Management Commands

### Quick Status
```bash
ssh jeffsc8 "/e/08/erthch01/will/anomaly status"
```

### Full Report
```bash
ssh jeffsc8 "/e/08/erthch01/will/anomaly report"
```

### View Logs
```bash
ssh jeffsc8 "tail -50 /e/08/erthch01/monitoring/anomaly_detection/anomaly_detector.log"
```

### View Alerts
```bash
ssh jeffsc8 "/e/08/erthch01/will/anomaly alerts 20"
```

### Acknowledge Deleted Job
```bash
ssh jeffsc8 "/e/08/erthch01/will/anomaly ack <job_name>"
```

### Restart Detector
```bash
ssh jeffsc8 "pkill -f 'python3 job_detector.py'"
# Cron will restart it within 5 minutes via keepalive_detector.sh
```

---

## Top Improvement Priorities

Based on the suggestions in SYSTEM_REPORT.md, here are the top 3 priorities:

### 1. Learning Mode Implementation (HIGH PRIORITY)
**Why**: Prevent alert spam during initial learning or after outages
```python
if learning_mode and profile.total_runs < min_data_points * 2:
    logger.info("Learning mode: suppressing alert for {}".format(job_name))
    return  # Log but don't send ntfy
```

### 2. Adaptive Thresholds (HIGH PRIORITY)
**Why**: Reduce false positives for inherently variable jobs
```python
# Jobs with high variability need higher thresholds
if interval_std / interval_mean > 0.3:  # >30% coefficient of variation
    effective_threshold = base_threshold * 1.5
```
**Example**: `mrms_to_chad.B.csh` runs every 7.0 min ± 2.5 min (36% variation) should use 3.75x threshold instead of 2.5x

### 3. Web Dashboard Integration (MEDIUM PRIORITY)
**Why**: At-a-glance status without checking phone or SSH
- Add "Active Anomalies" section to existing EarthCast dashboard
- Color-code by severity (red/yellow)
- Show job name, type, and time since alert
- Link to alert history

---

## Known Issues / Considerations

### Issue 1: Stale Data During Outage
When we deployed the fix, jobs had stale timestamps from 3 days ago. The detector correctly processed the backlog (5,750 runs) and updated all profiles. Future deployments should expect similar behavior if there's been a gap.

**Decision**: We chose NOT to zero out stale data because:
- Historical patterns are still valid (intervals, durations)
- The fix updated all `last_seen` timestamps automatically
- Jobs that are still running self-corrected within 30 minutes

### Issue 2: Learning Mode Not Implemented
Config has `learning_mode: true` but it doesn't suppress ntfy alerts. This is marked as improvement #1.

### Issue 3: High-Variability Jobs
Some jobs like `mrms_to_chad.B.csh` have high natural variability (36% coefficient of variation) and may generate false positives with fixed 2.5x threshold. Marked as improvement #2.

---

## Testing Notes

### Manual Testing Performed
1. Syntax validation: `python3 -m py_compile job_detector.py` ✓
2. Deployment: `rsync` to jeffsc8 ✓
3. Process restart: `pkill` + keepalive ✓
4. Log verification: Confirmed "Updated profiles with X new runs" messages ✓
5. Status check: `anomaly status` showed updated metrics ✓

### Integration Testing
- Detector successfully processed 5,750 backlogged runs
- Subsequent cycles processed 10-15 new runs every 5 minutes
- No duration anomalies detected yet (expected - most jobs run normally)
- Missing job alerts working correctly

---

## Next Session TODO

When returning to this work, consider:

1. **Implement Learning Mode** (high priority)
   - Suppress ntfy during initial learning period
   - Set threshold: 2x `min_data_points` before alerting
   - Keep log alerts for debugging

2. **Add Adaptive Thresholds** (high priority)
   - Calculate coefficient of variation per job
   - Adjust thresholds for high-variability jobs
   - Test with `mrms_to_chad.B.csh` and similar

3. **Web Dashboard Integration** (medium priority)
   - Add JSON endpoint for active anomalies
   - Create dashboard widget
   - Deploy to existing EarthCast dashboard

4. **Monitor for False Positives**
   - Review alerts over next 48 hours
   - Identify jobs that need threshold tuning
   - Adjust configuration as needed

5. **Consider Other Improvements**
   - Workflow-aware alerting (group related jobs)
   - Trend analysis (catch gradual degradation)
   - Resource anomaly detection (core-hours)

---

## References

### Documentation
- `anomaly_detection/SYSTEM_REPORT.md` - Complete system documentation
- `anomaly_detection/DEPLOYMENT_JEFFSC8.md` - Deployment guide for jeffsc8
- `anomaly_detection/README.md` - Quick start guide

### Key Code Sections
- `job_detector.py:318-400` - `_update_existing_profiles()` method
- `job_detector.py:473-499` - Continuous monitoring loop
- `job_detector.py:116-140` - Duration anomaly detection algorithm
- `job_detector.py:95-114` - Missing job detection algorithm

### Configuration
- Production config: `/e/08/erthch01/monitoring/anomaly_detection/config/detection_config_production.yaml`
- Thresholds: `missing_job_multiplier: 2.5`, `duration_anomaly_sigma: 2.5`
- Alerts: ntfy topic `ect-hpc`, 30-min cooldown for duration

### Data Sources
- Cluster usage: `/e/08/erthch01/monitoring/web_dashboard/dashboard_cluster_usage.json`
- Login jobs: `/e/08/erthch01/monitoring/web_dashboard/dashboard_login_jobs.json`
- Update frequency: Hourly (cluster), Real-time (login)

---

## Git Status

**Branch**: `anomaly-alerting`  
**Recent Commits**:
```
ce3e2ee - Add comprehensive system report for anomaly detection
d579818 - Add duration anomaly detection for new job runs
142142d - Fix: Update existing job profiles with new runs in continuous monitoring
```

**Changes to Deploy**: All changes already deployed to jeffsc8

**Merge Status**: Not yet merged to main - keep on feature branch for now until fully tested in production

---

## Questions for Next Session

1. Should we implement learning mode before merging to main?
2. What threshold should we use for coefficient of variation cutoff? (Currently suggested: 30%)
3. Should we add data quality monitoring before deploying improvements?
4. Do we want to track resource anomalies (core-hours) in addition to duration?
5. Should we add a dry-run mode for testing threshold changes?

---

## Performance Baseline

For comparison in future sessions:

- **Detector CPU**: <1% (mostly sleeping)
- **Detector Memory**: ~50MB
- **Profile Update**: 10-15 new runs per 5-minute cycle
- **Profile File Size**: <100KB (80 jobs)
- **Data Source Sizes**: 150KB cluster, 2.1MB login
- **Alert Volume**: ~10 alerts in first hour (mostly missing AccuWeather jobs)

---

## Contact / Escalation

If issues arise:
1. Check detector logs: `ssh jeffsc8 "tail -100 /e/08/erthch01/monitoring/anomaly_detection/anomaly_detector.log"`
2. Check data sources fresh: `ssh jeffsc8 "ls -lh /e/08/erthch01/monitoring/web_dashboard/dashboard_*.json"`
3. Restart detector: `ssh jeffsc8 "pkill -f 'python3 job_detector.py'"`
4. Review alert history: `ssh jeffsc8 "/e/08/erthch01/will/anomaly alerts 50"`
5. Check system report: `cat anomaly_detection/SYSTEM_REPORT.md`

---

**End of Session Context**
