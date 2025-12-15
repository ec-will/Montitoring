# Anomaly Detector Integration Summary

## Current State ✅

### Production System (jeffsc8:/e/08/erthch01/monitoring/)
- **Branch**: web-dashboard  
- **Status**: Active production system
- **Data Pipeline**: 
  - ✓ `dashboard_cluster_usage.json` generated hourly
  - ✓ `dashboard_login_jobs.json` updated continuously by daemon
  - ✓ Both files contain all data needed for anomaly detection

### Anomaly Detector (Local: anomaly-alerting branch)
- **Status**: Complete and tested
- **Features**:
  - ✓ Per-job anomaly detection
  - ✓ ntfy.sh push notifications  
  - ✓ Missing job alerts (>2.5x expected interval)
  - ✓ Duration anomaly alerts (>2.5σ from mean)
  - ✓ Auto-discovery of new jobs
  - ✓ 48-hour bootstrap learning
  - ✓ Python 3.6.8 compatible
- **Testing**: 10 test alerts successfully delivered

## Problem Statement ❌

**Branch Mismatch**: 
- Anomaly detector built on old version of web-dashboard (commit be522dc)
- Production is 9 commits ahead (commit 172c6cd)
- Need to integrate detector with current production code

## Solution Path ✅

### Option 1: Merge Strategy (Recommended)
**Steps**:
1. Add jeffsc8 as git remote
2. Fetch latest production web-dashboard
3. Merge production → local anomaly-alerting
4. Resolve conflicts (low risk - detector in separate directory)
5. Test with production data
6. Deploy to jeffsc8

**Pros**:
- Clean git history
- All production features preserved
- Easy to push back to production
- Trackable in version control

**Cons**:
- May have merge conflicts to resolve
- Requires git knowledge

### Option 2: Cherry-Pick Strategy (Alternative)
**Steps**:
1. Create new branch from production web-dashboard
2. Cherry-pick 15 anomaly detection commits in order
3. Test and deploy

**Pros**:
- Clean base from production
- Avoids merge conflicts
- Fresh start

**Cons**:
- More manual work (15 commits)
- Potential cherry-pick conflicts
- Loses original branch history

### Option 3: Standalone Deployment (Quick & Dirty)
**Steps**:
1. Copy anomaly_detection/ directory to jeffsc8
2. Point config to production JSON files
3. Add to crontab

**Pros**:
- Fastest deployment
- No git operations needed
- Isolated from web-dashboard

**Cons**:
- Not tracked in version control on production
- Code divergence over time
- Harder to maintain/update

## Recommended Action Plan

### Immediate Next Steps
1. **Fetch production state**:
   ```bash
   git remote add jeffsc8 jeffsc8:/e/08/erthch01/monitoring/.git
   git fetch jeffsc8
   ```

2. **Examine divergence**:
   ```bash
   git log --oneline --graph web-dashboard...jeffsc8/web-dashboard
   ```

3. **Make decision** based on divergence complexity:
   - Simple divergence → Use merge strategy
   - Complex divergence → Use cherry-pick strategy
   - Need quick test → Use standalone deployment

4. **After integration, deploy**:
   - Location: `/tmp/will/anomaly_detection/` (write permissions)
   - Or: `/e/08/erthch01/monitoring/anomaly_detection/` (read-only, needs admin)

5. **Add to crontab** (as user will):
   ```bash
   */15 * * * * /usr/bin/python3 /tmp/will/anomaly_detection/job_detector.py
   ```

6. **Monitor notifications** on ntfy.sh topic `ect-hpc`

## Files to Review

- `ARCHITECTURE_ANALYSIS.md` - Production system architecture
- `BRANCH_STATUS.md` - Detailed git branch comparison
- `PRODUCTION_STATE.md` - Production crontab and deployment
- `DEPLOYMENT_OPTIONS.md` - Original deployment analysis

## Expected Timeline

- **Merge + Test**: 30-60 minutes
- **Deployment to jeffsc8**: 15 minutes  
- **First anomaly alerts**: Within 24 hours (depending on job patterns)

## Success Metrics

✅ Anomaly detector running on jeffsc8  
✅ Reading production JSON files  
✅ Learning job patterns  
✅ Sending ntfy.sh notifications  
✅ No false positives in first 48 hours  
✅ Catches real anomalies (missing/slow jobs)

## Risk Mitigation

**Low Risk**:
- Detector doesn't modify production code
- Reads JSON files (read-only)
- Notifications go to separate channel
- Can be stopped without affecting production

**If Problems Occur**:
1. Stop detector: `kill <pid>` or remove from crontab
2. Check logs: `/tmp/anomaly_detection.log`
3. Verify JSON files exist and are readable
4. Test notifications manually with curl

## Questions for User

Before proceeding, clarify:
1. **Deployment approach preference**: Merge, cherry-pick, or standalone?
2. **Deployment location**: /tmp/will/ or /e/08/erthch01/monitoring/?
3. **Notification testing**: Should we test ntfy first before enabling all alerts?
4. **Update frequency**: Run every 15 min, hourly, or something else?

---

**Status**: ✅ Architecture documented and analyzed  
**Next**: Awaiting user decision on integration approach
