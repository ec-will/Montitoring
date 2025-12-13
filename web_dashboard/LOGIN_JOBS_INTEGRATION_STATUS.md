# Login Node Job Tracking - Integration Status

**Date:** 2025-11-15  
**Status:** ✅ Ready for Dashboard Integration

---

## What's Been Completed

### 1. Core Tracking System ✅
- **File:** `dashboard_login_jobs.py`
- **Function:** Continuously monitors login node cron jobs
- **Method:** 
  - Reads `crontab -l` on startup
  - Analyzes script content to detect job submission commands (`qsub`, `sbatch`, etc.)
  - Tracks scripts that DON'T submit to cluster (run locally on login node)
  - Uses `ps -u erthch01 -o args=` to detect running scripts
  - Records start/end times and durations
- **Output:** `dashboard_login_jobs.json` (updated after each job completion)
- **Data Retention:** 48 hours rolling window

### 2. Auto-Start Wrapper ✅
- **File:** `start_login_tracker.sh`
- **Function:** Monitors and auto-restarts the tracker
- **Deployment:** 
  - Installed on jeffsc8 at `~/monitoring/web_dashboard/`
  - Added to crontab:
    - `@reboot` - starts on server boot
    - `*/10 * * * *` - health check every 10 minutes
- **Status:** Currently running and tracking jobs

### 3. Timeline Visualization ✅
- **File:** `web_server_login_timeline_plot.py`
- **Function:** Generates interactive HTML timeline from JSON data
- **Output:** `login_jobs_timeline.html`
- **Features:**
  - Plotly-based interactive timeline
  - Shows when scripts executed (horizontal bars)
  - Sorted by total runtime (most time-consuming at top)
  - Color-coded by script type
  - Hover shows start/end/duration details
  - Matches cluster timeline styling
- **Tested:** ✅ Working locally with production data

---

## Current Production Status

### Tracking Performance (as of 2025-11-15 03:12 UTC)
- **Unique Scripts Tracked:** 24
- **Total Job Runs:** 64
- **Total Runtime:** 4806 seconds (1.3 hours)
- **Data Age:** ~15 minutes

### Scripts Being Tracked (Examples)
✅ `mrms_to_chad.B.csh` - MRMS data processing  
✅ `wrs_to_chad.csh` - Weather data transfers  
✅ `update_dashboard_cron.sh` - Dashboard updates  
✅ `wget_mrms_*.csh` - Data download scripts  
✅ `push_data_to_chad.csh` - Data push operations  
✅ `gen_send_gtgn.wrf.B.csh` - GTG data generation  
✅ `master_clean_seq.csh` - Cleanup operations  

### Scripts Being Filtered Out (Not Tracked)
❌ `run_master.wrfv3911_*.csh` - Submits WRF to cluster  
❌ `accuwx_*_seq.*.csh` - Submits AccuWeather jobs  
❌ `master_hiresw_seq.*.csh` - Submits HiResW jobs  
❌ `get_gfs_0p25_nomads_aria2c.sh` - Contains qsub

---

## Files Created

### Core Components
```
web_dashboard/
├── dashboard_login_jobs.py          # Main tracker (continuous)
├── start_login_tracker.sh            # Auto-restart wrapper
├── web_server_login_timeline_plot.py # Timeline generator
├── dashboard_login_jobs.json         # Output data (gitignored)
└── login_jobs_timeline.html          # Generated timeline (gitignored)
```

### Documentation
```
web_dashboard/
├── LOGIN_JOBS_README.md              # Full documentation
├── QUICKSTART_LOGIN_JOBS.md          # Quick reference guide
├── INSTALL_LOGIN_TRACKER.md          # Installation instructions
├── LOGIN_JOBS_INTEGRATION_STATUS.md  # This file
└── test_login_jobs.sh                # Test script
```

---

## Integration TODO

### 1. Generate HTML on HPC System
Generate the timeline HTML locally before pushing:

```bash
# In update_dashboard_cron.sh or similar (on jeffsc8)
cd $HOME/monitoring/web_dashboard
python3 web_server_login_timeline_plot.py dashboard_login_jobs.json login_jobs_timeline.html
```

### 2. Push HTML to Web Server
Transfer the ready-to-display HTML file:

```bash
# Push HTML directly (simpler - no cron needed on web server)
scp login_jobs_timeline.html rcity2.cottay.net:/srv/www/earthcast/

# Optional: also push JSON if you want it available for other uses
scp dashboard_login_jobs.json rcity2.cottay.net:/srv/www/earthcast/
```

### 3. Add to Deployment Script
Update your deployment script (e.g., `update_dashboard_cron.sh`) to generate and push:

```bash
# Generate login jobs timeline
cd $HOME/monitoring/web_dashboard
python3 web_server_login_timeline_plot.py dashboard_login_jobs.json login_jobs_timeline.html

# Push to web server
scp login_jobs_timeline.html rcity2.cottay.net:/srv/www/earthcast/
```

### 4. Add to Web Dashboard HTML
In `index.html`, add a link or iframe to the timeline:

```html
<!-- Option 1: Direct link in nav bar -->
<a href="login_jobs_timeline.html" class="nav-link" target="_blank">Login Jobs Timeline</a>

<!-- Option 2: Embedded iframe in a section -->
<div class="section">
    <h2>Login Node Activity</h2>
    <iframe src="login_jobs_timeline.html" width="100%" height="800px" frameborder="0"></iframe>
</div>
```

### 5. Optional Enhancements
- Load JSON via JavaScript to display summary stats in index.html
- Create a combined cluster + login jobs view
- Add date range selector
- Export data to CSV

---

## JSON Data Format

### dashboard_login_jobs.json Structure
```json
{
  "metadata": {
    "generator": "dashboard_login_jobs.py",
    "version": "1.0",
    "generated_at": 1763175123,
    "generated_time": "2025-11-15 03:12:03 UTC",
    "description": "48-hour login node cron job tracking",
    "data_retention_hours": 48
  },
  "job_runs": {
    "summary": {
      "total_unique_scripts": 24,
      "total_job_runs": 64,
      "total_duration_seconds": 4806.23
    },
    "jobs": {
      "script_name.csh": {
        "total_runs": 5,
        "total_duration_seconds": 234.56,
        "avg_duration_seconds": 46.91,
        "runs_detail": [
          {
            "script_name": "script_name.csh",
            "start": "2025-11-15T02:56:02.148695",
            "end": "2025-11-15T02:57:03.519102",
            "duration_seconds": 61.37
          }
        ]
      }
    }
  }
}
```

---

## Deployment Checklist

When integrating tomorrow:

- [ ] Add HTML generation to HPC deployment script
- [ ] Add HTML transfer (scp) to deployment script  
- [ ] Test generation locally: `python3 web_server_login_timeline_plot.py`
- [ ] Test push to web server: `scp login_jobs_timeline.html rcity2...`
- [ ] Add link/iframe to `index.html`
- [ ] Test end-to-end: generate → push → view
- [ ] Update deployment documentation
- [ ] Add monitoring for tracker health (check if running)

---

## Key Differences from Cluster Jobs

| Aspect | Cluster Jobs | Login Jobs |
|--------|--------------|------------|
| **Data Source** | `myusage` (historical) | `ps` (real-time) |
| **Tracking Method** | One-time snapshot | Continuous monitoring |
| **Metrics** | Cores, core-hours | Duration (seconds) |
| **Frequency** | Hourly | Every second |
| **Sorting** | By core count | By total runtime |
| **Colors** | Red/orange palette | Blue/green palette |

---

## Troubleshooting

### If Tracker Stops
```bash
ssh jeffsc8
cd monitoring/web_dashboard
./start_login_tracker.sh
```

### If JSON Not Updating
```bash
# Check tracker status
ps aux | grep dashboard_login_jobs
cat /tmp/dashboard_login_jobs.lock

# Check logs
tail -50 ~/logs/dashboard/login_jobs.log

# Restart
kill $(cat /tmp/dashboard_login_jobs.lock)
./start_login_tracker.sh
```

### If Timeline Empty
- Check if JSON has data: `head -50 dashboard_login_jobs.json`
- Check tracker has been running: Look at generated_time in metadata
- Let tracker run for at least 5-10 minutes to collect data

---

## Notes

- Tracker is **deterministic** - uses script content analysis, not name matching
- **No root required** - runs as user, uses crontab for auto-restart
- **Self-healing** - auto-restarts if crashes (via cron)
- **Persistent** - maintains state across restarts
- **Safe** - lock file prevents duplicate instances

---

## Success Criteria

✅ Tracker running continuously on jeffsc8  
✅ JSON being generated and updated  
✅ Timeline visualization working  
✅ Scripts properly filtered (cluster jobs excluded)  
✅ Documentation complete  
✅ Auto-restart mechanism in place  

**Status: Ready for Dashboard Integration** 🎉
