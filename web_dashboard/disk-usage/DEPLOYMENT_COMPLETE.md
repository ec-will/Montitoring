# Disk Usage Dashboard - Deployment Complete ✅

## Files Deployed to jeffsc8

Location: `/e/08/erthch01/monitoring/disk-usage/`

- ✅ `collect_disk_usage.py` - Data collection script
- ✅ `disk-usage.html` - Web dashboard interface
- ✅ `update_disk_usage_cron.sh` - Automated cron deployment script
- ✅ `disk_usage_data.json` - Current data (13TB, $1,195.41)
- ✅ `crontab-line.txt` - Crontab entry for daily updates
- ✅ `README.md` - Documentation
- ✅ `.gitignore` - Git ignore rules

## Setup Cron Job

Add to crontab on jeffsc8:
```bash
ssh jeffsc8
crontab -e
```

Add this line (or copy from `~/monitoring/disk-usage/crontab-line.txt`):
```
0 3 * * * /e/08/erthch01/monitoring/disk-usage/update_disk_usage_cron.sh
```

## Test the Cron Script

Run manually to test:
```bash
ssh jeffsc8 "/e/08/erthch01/monitoring/disk-usage/update_disk_usage_cron.sh"
```

Check logs:
```bash
ssh jeffsc8 "tail -f /e/08/erthch01/logs/disk-usage/update_disk_usage.log"
```

## Web Dashboard Access

After cron runs (or manual test), access at:
- http://rcity2.cottay.net/disk-usage/disk-usage.html
- http://ect-hpc.wx-farms.com/disk-usage/disk-usage.html

## Features

✅ Hierarchical directory tree (depth 3)
✅ Collapsible bar graph visualization  
✅ Click to expand/collapse subdirectories
✅ Human-readable sizes (TB, GB, MB)
✅ **Bold cost display at $0.09/GB**
✅ Total: 13.0TB = **$1,195.41**
✅ Automated daily updates at 3:00 AM
✅ Deploys to both web servers
✅ Lock file prevents overlapping runs
✅ Comprehensive logging

## Summary Info

Current data:
- 47 top-level directories
- 13.0TB total usage
- $1,195.41 total cost
- Largest: data (12.9TB = $1,188.48)
