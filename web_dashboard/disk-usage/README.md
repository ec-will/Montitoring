# Disk Usage Dashboard

Collapsible web-based disk usage visualization with hierarchical directory bar graphs.

## Overview

This system collects disk usage data from jeffsc8 and displays it in an interactive web dashboard with:
- Collapsible directory tree with bar graph visualization
- Relative sizing (bars scale based on parent directory or top-level max)
- Human-readable size labels (embedded in bars for large directories, at end for smaller ones)
- Click to expand/collapse subdirectories
- Up to 3 levels of depth by default

## Files

- **collect_disk_usage.py** - Python script that scans directories and generates JSON
- **disk-usage.html** - Web interface with collapsible bar graphs
- **update_disk_usage.sh** - Deployment script for jeffsc8 (collects data and deploys to web server)
- **README.md** - This file

## Usage

### Local Testing

To test the dashboard locally, you need to run a web server (browsers block loading JSON from file:// URLs):

```bash
# Quick test
./test_locally.sh

# Or manually
python3 -m http.server 8888
# Then open http://localhost:8888/disk-usage.html
```

### Manual Collection

Run the collection script directly (defaults to home directory):
```bash
python3 collect_disk_usage.py > disk_usage_data.json
```

Or specify a different root directory:
```bash
python3 collect_disk_usage.py /path/to/directory > disk_usage_data.json
```

Options:
```bash
python3 collect_disk_usage.py --help
python3 collect_disk_usage.py ~ --max-depth 3
```

### Automated Deployment (jeffsc8)

The `update_disk_usage.sh` script handles collection and deployment:

```bash
# Run manually (defaults to ~)
./update_disk_usage.sh

# Specify different root directory
./update_disk_usage.sh /e/08/erthch01

# View logs
tail -f ~/logs/disk-usage/update.log
```

### Cron Setup (jeffsc8)

Add to crontab for daily updates at 2 AM:
```bash
crontab -e
```

Add line:
```
0 2 * * * /path/to/monitoring/web_dashboard/disk-usage/update_disk_usage.sh
```

Or for a specific directory:
```
0 2 * * * /path/to/monitoring/web_dashboard/disk-usage/update_disk_usage.sh /e/08/erthch01
```

## Web Interface

After deployment, access the dashboard at:
- http://rcity2.cottay.net/disk-usage/

Features:
- Click any directory to expand/collapse subdirectories
- Hover over directory names to see full path
- Bar width shows relative usage compared to largest sibling directory
- Size labels appear inside bars (for large dirs) or at the end (for smaller dirs)
- Matches EarthCast HPC dashboard styling

## Configuration

Edit `update_disk_usage.sh` to customize:
- `ROOT_DIR` - Default root directory to scan (default: ~)
- `MAX_DEPTH` - How many levels deep to scan (default: 3)
- `WEB_SERVER` - Target web server (default: rcity2.cottay.net)
- `WEB_PATH` - Remote path on web server (default: /srv/www/earthcast/disk-usage)

Edit `collect_disk_usage.py` to customize:
- Timeout for du commands (default: 300 seconds / 5 minutes per directory)
- Size calculation method (currently uses `du -sb`)

## How It Works

1. **Collection** (`collect_disk_usage.py`):
   - Scans immediate subdirectories of specified root
   - Uses `du -sb` for accurate size calculation (includes all files and subdirs)
   - Recursively scans up to MAX_DEPTH levels
   - Sorts directories by size (largest first)
   - Outputs hierarchical JSON with sizes in bytes and human-readable format

2. **Deployment** (`update_disk_usage.sh`):
   - Creates lock file to prevent concurrent runs
   - Runs collection script
   - Validates JSON output
   - Deploys JSON and HTML to web server via scp
   - Logs all operations to ~/logs/disk-usage/update.log

3. **Visualization** (`index.html`):
   - Loads JSON via fetch API
   - Renders collapsible directory tree
   - Scales bars relative to largest directory at each level
   - Shows/hides size labels based on bar width
   - Updates timestamp but data only refreshes when regenerated

## Troubleshooting

### Collection is slow
- Reduce MAX_DEPTH in the script (default: 3)
- Increase timeout in collect_disk_usage.py if directories are very large
- Consider scanning a more specific directory instead of ~

### Permission errors
- Ensure the script has permission to read directories being scanned
- Script skips directories it can't access and continues

### Deployment fails
- Check SSH access to web server: `ssh rcity2.cottay.net`
- Verify remote directory exists or is writable
- Check logs: `tail -f ~/logs/disk-usage/update.log`

### Web page shows "Loading..."
- Verify disk_usage_data.json exists in the web directory
- Check JSON is valid: `python3 -m json.tool disk_usage_data.json`
- Check browser console for errors

## Notes

- Collection time depends on directory size and depth
- The script uses `du -sb` which is I/O intensive
- Lock file prevents concurrent runs (stale after 2 hours)
- Symlinks are not followed to prevent loops
- Bar widths are relative to siblings (not absolute across entire tree)
