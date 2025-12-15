# Git Branch Status Analysis

## Production vs Local Comparison

### jeffsc8 (Production) - web-dashboard branch
**Latest commit**: 172c6cd "Fix timeline to show last 4 hours and extend to 48-hour window"
**Key features**:
- Timeline visualizations (added commit dde0119)
- Cluster usage monitoring (added commit 397c273)
- Dynamic scheduled jobs (added commits 35cdaaf, 6e58fed)
- Frequent jobs section (added commits a701428, 5fd2e7f)

### Local - web-dashboard branch  
**Latest commit**: be522dc "Add login jobs tracking, usage reports, and disk monitoring"
**Status**: Behind production by ~9 commits
**Missing from production**:
- Timeline visualization updates (last 4 hours, 48-hour window)
- Cluster usage monitoring enhancements
- Dynamic scheduling features
- Recent bug fixes

### Local - anomaly-alerting branch
**Base commit**: be522dc (same as local web-dashboard)
**Commits ahead**: 15 commits
**Features**:
- Per-job anomaly detection system
- ntfy.sh push notifications
- Missing job detection (>2.5x expected interval)
- Duration anomaly detection (>2.5σ from mean)
- Auto-discovery of new jobs
- Profile persistence
- Bootstrap learning from 48h history

### GitHub origin/web-dashboard
**Latest commit**: 8193535 "Use mqstat to accurately determine if PBS jobs are running"
**Status**: Behind both local web-dashboard (be522dc) and jeffsc8 (172c6cd)
**Note**: GitHub may not be the source of truth

## Branch Divergence Issue

The git history shows **divergence** between:
1. **jeffsc8 web-dashboard** (production) - Most up-to-date
2. **Local web-dashboard** - 1 commit ahead of GitHub, behind jeffsc8
3. **GitHub origin/web-dashboard** - Behind both
4. **Local anomaly-alerting** - Based on old web-dashboard, doesn't have jeffsc8 updates

## Recommended Merge Strategy

### Step 1: Fetch Production State
```bash
# Add jeffsc8 as remote
git remote add jeffsc8 jeffsc8:/e/08/erthch01/monitoring/.git
git fetch jeffsc8
```

### Step 2: Check Divergence
```bash
# Compare local web-dashboard with production
git log --oneline --graph web-dashboard...jeffsc8/web-dashboard
```

### Step 3: Update Local web-dashboard (Choose One)

**Option A: Fast-forward if possible**
```bash
git checkout web-dashboard
git merge jeffsc8/web-dashboard
```

**Option B: Reset to match production exactly**
```bash
git checkout web-dashboard
git reset --hard jeffsc8/web-dashboard
```

**Option C: Rebase local changes**
```bash
git checkout web-dashboard
git rebase jeffsc8/web-dashboard
```

### Step 4: Merge into anomaly-alerting
```bash
git checkout anomaly-alerting
git merge web-dashboard  # This will bring in all jeffsc8 updates
```

### Step 5: Resolve Conflicts
Expect conflicts in:
- Any files modified by both jeffsc8 updates and anomaly detector
- Config files if paths changed
- Potentially DEPLOYMENT_OPTIONS.md or README files

### Step 6: Test Locally
```bash
# Fetch latest JSON from production
./anomaly_detection/fetch_data.sh

# Test anomaly detector
python3 anomaly_detection/job_detector.py
```

### Step 7: Push Back to Production
```bash
# Push updated branch to GitHub
git push origin anomaly-alerting

# Push to jeffsc8 (if remote configured for push)
git push jeffsc8 anomaly-alerting

# Or manually copy to jeffsc8
```

## Risk Assessment

**Low Risk**:
- Anomaly detector code is in separate directory (`anomaly_detection/`)
- Unlikely to conflict with web-dashboard visualization code
- Uses same JSON files that already exist

**Medium Risk**:
- Config file paths may have changed between versions
- Python dependencies may have changed
- Crontab modifications needed for deployment

**High Risk Items to Check**:
- Python version compatibility (jeffsc8 has Python 3.6.8)
- File permissions on jeffsc8 (can't write to /e/08/erthch01)
- JSON file locations haven't moved
- No breaking changes in JSON schema

## Alternative: Cherry-Pick Approach

If merge is too complex, cherry-pick just the anomaly detection commits:

```bash
# Start from production web-dashboard
git checkout -b anomaly-alerting-v2 jeffsc8/web-dashboard

# Cherry-pick anomaly detection commits (in order)
git cherry-pick 97ef07d  # Add anomaly detection system
git cherry-pick 4969d59  # Add deployment guide
git cherry-pick 9d5f664  # Add local development setup
git cherry-pick 7131b19  # Python 3.6.8 compatibility
git cherry-pick e6a29d5  # Add bootstrapping
git cherry-pick cceebd9  # Per-job detection
git cherry-pick 791279c  # Fix timezone
git cherry-pick 7e735c8  # Remove report limit
git cherry-pick b85f514  # Save session context
git cherry-pick f42f160  # Auto-discovery
git cherry-pick 78f780a  # ntfy notifications
git cherry-pick 618e71a  # Testing checkpoint
git cherry-pick ea70cb2  # Deployment options
```

This creates a clean anomaly-alerting branch on top of current production.
