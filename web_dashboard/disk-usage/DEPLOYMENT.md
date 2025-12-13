# Disk Usage Dashboard - Deployment Steps

## Status
✅ Collection script created and working
✅ Web interface created with collapsible bars
✅ Click/expand functionality fixed (using event delegation)
✅ Deployment script ready
⏳ Full data collection running in background on jeffsc8

## Current Data Collection
Running on jeffsc8: `python3 /tmp/collect_disk_usage.py ~ --max-depth 3`
Output: `/tmp/disk_usage_data.json`

Check progress:
```bash
ssh jeffsc8 "ps aux | grep collect_disk_usage | grep -v grep"
ssh jeffsc8 "wc -l /tmp/disk_usage_data.json"
```

## When Collection Finishes

1. **Verify the data:**
```bash
ssh jeffsc8 "python3 -m json.tool /tmp/disk_usage_data.json | head -20"
```

2. **Copy scripts to jeffsc8:**
```bash
scp -r ~/projects/monitoring/web_dashboard/disk-usage jeffsc8:~/monitoring/web_dashboard/
```

3. **Copy the generated data:**
```bash
ssh jeffsc8 "cp /tmp/disk_usage_data.json ~/monitoring/web_dashboard/disk-usage/"
```

4. **Deploy to web server:**
```bash
ssh jeffsc8 "cd ~/monitoring/web_dashboard/disk-usage && ./update_disk_usage.sh"
```

5. **Set up cron job:**
```bash
ssh jeffsc8 "crontab -e"
# Add this line:
0 2 * * * ~/monitoring/web_dashboard/disk-usage/update_disk_usage.sh
```

6. **Access the dashboard:**
http://rcity2.cottay.net/disk-usage/disk-usage.html

## Files Ready for Deployment
- `collect_disk_usage.py` - Data collection (Python 3.6+ compatible)
- `disk-usage.html` - Web interface with working expand/collapse
- `update_disk_usage.sh` - Automated deployment script
- `test_locally.sh` - Local testing helper
- `README.md` - Full documentation

## Key Features Working
- ✅ Hierarchical directory scanning
- ✅ Bar graph visualization
- ✅ Click to expand/collapse subdirectories
- ✅ Human-readable sizes (GB, MB, etc.)
- ✅ Relative bar sizing
- ✅ EarthCast HPC styling
