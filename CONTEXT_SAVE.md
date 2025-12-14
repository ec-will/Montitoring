# Anomaly Detection - Session Checkpoint

## Status: DEPLOYMENT PLANNING

**Branch:** anomaly-alerting (14 commits)  
**Location:** ~/projects/monitoring/anomaly_detection/  
**Date:** 2025-12-14 (afternoon session)

## Where We Are

### ✅ System Complete & Tested
- Per-job detector working (65 jobs tracked)
- Auto-discovery implemented
- ntfy.sh notifications tested (10 alerts sent successfully)
- Statistical detection (no ML/AI)
- Python 3.6+ compatible

### 🔍 Issue Discovered
The detector was built for JSON files that **aren't deployed to web servers yet**:
- `dashboard_cluster_usage.json` - exists on jeffsc8, NOT on web servers
- `dashboard_login_jobs.json` - exists on jeffsc8, NOT on web servers

**Current deployment only pushes:**
- `dashboard_data.json` (current status, not history)
- HTML files with embedded data

### 📄 Decision Pending
Created **DEPLOYMENT_OPTIONS.md** with three approaches:
- **Option A:** Separate monitoring instance (RECOMMENDED)
- **Option B:** Run on jeffsc8
- **Option C:** Hybrid approach

See `anomaly_detection/DEPLOYMENT_OPTIONS.md` for full analysis.

## Quick Summary of Options

### Option A: Separate Monitoring Instance ⭐
**Pros:** Detects jeffsc8 down, multi-cluster ready, independent  
**Cons:** Needs VM/container, requires deploying JSON files  
**Changes:** Deploy JSONs to web server, fetch via HTTP

### Option B: Run on jeffsc8
**Pros:** Simplest, $0 cost, fastest  
**Cons:** Can't detect jeffsc8 down, single cluster only

### Option C: Hybrid
**Pros:** Best resilience  
**Cons:** Most complex, duplicate alert risk

## Files to Review

1. **DEPLOYMENT_OPTIONS.md** - Full analysis of deployment choices
2. **CONTEXT_SAVE.md** - This file
3. **job_detector.py** - Working detector (no changes needed)
4. **fetch_data.sh** - May need update for HTTP (if Option A)

## Next Session Tasks

1. [ ] Decide on deployment option (A, B, or C)
2. [ ] If Option A: Update jeffsc8 deployment scripts
3. [ ] If Option A: Update fetch_data.sh for HTTP
4. [ ] Deploy and test
5. [ ] Monitor for 24 hours

## Commands

```bash
cd ~/projects/monitoring/anomaly_detection

# Read deployment options
cat DEPLOYMENT_OPTIONS.md

# Current files on jeffsc8
ssh jeffsc8 "ls -lh /e/08/erthch01/monitoring/web_dashboard/*.json"

# What's deployed to web server
ssh rcity2.cottay.net "ls -lh /srv/www/earthcast/*.json"
```

## No Code Changes Made Today
- Discovered deployment gap
- Documented options
- Waiting for decision before implementing

## Git Status
```
Branch: anomaly-alerting
Commits: 14
Status: Working code, deployment planning
```

Stay safe plowing! ❄️
