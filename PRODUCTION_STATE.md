# Production Monitoring System - Current State

**Investigation Date:** 2025-12-14
**Location:** jeffsc8:/e/08/erthch01/monitoring/

## Production Crontab (Active)

```
# update usage for monitor site
0 * * * *        update_cluster_usage_cron.sh           # Hourly

# update login node jobs for monitor site  
*/10 * * * *     deploy_login_timeline.sh               # Every 10 min

# update transfer dashboard for monitor site
*/5 * * * *      update_transfer_dashboard_cron.sh      # Every 5 min

# update cluster usage for bill estimate
0 7 * * *        update_usage_report_cron.sh           # Daily 7am

# update the disk usage
0 3 * * *        update_disk_usage_cron.sh             # Daily 3am

# make sure the login node job tracker start/is running
@reboot          start_login_tracker.sh
*/10 * * * *     start_login_tracker.sh                # Every 10 min
```

## What Gets Deployed to Web Servers

**Target:** rcity2.cottay.net:/srv/www/earthcast/ (and ect-hpc.wx-farms.com)

### Files Deployed:
1. **login_jobs_timeline.html** (from deploy_login_timeline.sh)
   - Every 10 minutes
   - HTML with embedded job data
   
2. **cluster_usage_timeline.html** (from update_cluster_usage_cron.sh)
   - Every hour
   - HTML with embedded cluster data

3. **transfers.json** (from update_transfer_dashboard_cron.sh)
   - Every 5 minutes
   - JSON file

4. **dashboard_data.json** (from update_dashboard_cron.sh)
   - NOT in crontab (script exists but not running!)

## Key Finding: The Mismatch

**What anomaly detector expects:**
- dashboard_cluster_usage.json (48hr history)
- dashboard_login_jobs.json (48hr history)

**What production actually deploys:**
- login_jobs_timeline.html (embedded data)
- cluster_usage_timeline.html (embedded data)
- transfers.json
- dashboard_data.json (not currently deployed)

## JSON Files on jeffsc8 (Not Deployed)

These exist but are NOT pushed to web servers:
- dashboard_cluster_usage.json (146K, updated hourly)
- dashboard_login_jobs.json (2.0M, updated continuously)
- usage_report_data.json

## Git Branch Status

The anomaly detector was built on **anomaly-alerting branch** which is based on **monitoring branch**.

Need to verify:
- What branch is monitoring/?
- Is web_dashboard a different branch?
- What's the relationship?

## Questions to Answer

1. [ ] What git branch is /e/08/erthch01/monitoring/ on jeffsc8?
2. [ ] Is there a web_dashboard branch?
3. [ ] Where do dashboard_cluster_usage.json and dashboard_login_jobs.json come from?
4. [ ] Are they part of web_dashboard features not yet deployed?

## Next Steps

1. Check git status on jeffsc8
2. Understand branch structure
3. Determine if anomaly detector should:
   - Use HTML files (parse embedded data)
   - Deploy the JSON files (add to deployment)
   - Be part of web_dashboard branch integration
