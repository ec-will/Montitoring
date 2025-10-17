# Transfer Log Monitoring System

A complete transfer log monitoring solution with automated parsing on HPC systems and web dashboard visualization.

## Architecture Overview

This system operates in a distributed environment:

1. **HPC Environment (Production)**:
   - `transfer.log` - Active transfer log file
   - `parse_transfers.py` - Automated by cron to generate JSON data
   - Log rotation scripts - Manage log file growth
   - Generated `transfers.json` - Transferred to web server

2. **Web Server Environment**:
   - `transfer_dashboard.html` - Interactive web dashboard
   - `transfers.json` - Data consumed by dashboard
   - Web server - Serves dashboard to users

## Production Workflow

```
[HPC System] transfer.log → parse_transfers.py (cron) → transfers.json → [Web Server] → Dashboard
                ↓
        [Log Rotation] (cron)
```

## Log Format

The parser expects log entries in this format:
```
YYYY-MM-DD HH:MM:SS [LOG_TYPE]: PID message
```

Where:
- `LOG_TYPE` can be INFO, SUCCESS, ERROR, etc.
- `PID` is used to group related log entries into transfer sessions
- `message` contains details about the transfer operation

## Usage

### Basic Usage
```bash
python3 parse_transfers.py
```
This reads `transfer.log` and outputs `transfers.json`.

### With Options
```bash
python3 parse_transfers.py -i input.log -o output.json --summary
```

### Options
- `-i, --input`: Input log file (default: transfer.log)
- `-o, --output`: Output JSON file (default: transfers.json)
- `--summary`: Print parsing statistics

### Validation
```bash
python3 parse_transfers.py -i transfer.log -o transfers.json && python3 -m json.tool transfers.json | head
```

## JSON Schema

The output JSON is an array of session objects, each representing a group of log entries with the same PID:

```json
[
  {
    "pid": 1553807,
    "entry_count": 2,
    "entries": [
      {
        "timestamp": "2025-10-15 17:30:08",
        "log_type": "INFO",
        "message": "file_to_bftp.csh called by: wget_short_term_fcst.csh with args: WRS,file.nc",
        "script": "file_to_bftp.csh",
        "caller": "wget_short_term_fcst.csh",
        "args": "WRS,file.nc"
      },
      {
        "timestamp": "2025-10-15 17:30:10",
        "log_type": "SUCCESS",
        "message": "file_to_bftp.csh scp file.nc upload@server.com:WRS",
        "script": "file_to_bftp.csh",
        "method": "scp",
        "file": "file.nc",
        "destination": "upload@server.com:WRS"
      }
    ]
  }
]
```

### Entry Fields

Each log entry contains:
- **timestamp**: When the log entry was created
- **log_type**: Type of log message (INFO, SUCCESS, ERROR, etc.)
- **message**: Original log message
- **script**: Script that generated the log entry (when detectable)
- **caller**: Parent script that invoked the current script (for INFO entries)
- **args**: Arguments passed to the script (for INFO entries)
- **method**: Transfer method used (scp, cp, rsync) (for SUCCESS entries)
- **file**: File being transferred (for SUCCESS entries)
- **destination**: Transfer destination (for SUCCESS entries)

## Production Deployment

### HPC Environment Setup

1. **Deploy Parser Script**:
   ```bash
   # Copy parser to HPC system
   scp parse_transfers.py user@hpc-system:/path/to/monitoring/
   ```

2. **Configure Cron Job**:
   ```bash
   # Add to crontab for automated parsing
   */5 * * * * /usr/bin/python3 /path/to/monitoring/parse_transfers.py -i /path/to/transfer.log -o /path/to/transfers.json
   ```

3. **Setup Log Rotation**:
   ```bash
   # Add to crontab for log management
   0 0 * * * /path/to/monitoring/rotate_transfer_logs.sh
   ```

4. **Data Transfer to Web Server**:
   ```bash
   # Copy JSON to web server (add to cron after parsing)
   */5 * * * * scp /path/to/transfers.json webserver:/var/www/dashboard/
   ```

### Web Server Setup

1. **Deploy Dashboard**:
   ```bash
   # Copy dashboard files to web server
   scp transfer_dashboard.html webserver:/var/www/dashboard/
   ```

2. **Configure Web Server**: Ensure web server serves static files from dashboard directory

### Recommended Cron Schedule

```bash
# HPC System crontab
*/5 * * * * /usr/bin/python3 /path/to/parse_transfers.py && scp transfers.json webserver:/var/www/dashboard/
0 0 * * * /path/to/rotate_transfer_logs.sh
```

## Testing

Run the basic test suite:
```bash
python3 test_parser.py
```

## Web Dashboard Integration

The JSON output is designed for web dashboard consumption. The structure allows for:

- **Sorting**: By timestamp, PID, log type, file name, etc.
- **Filtering**: By transfer method, destination, time range, etc.
- **Grouping**: Sessions are already grouped by PID for related operations
- **Status Tracking**: INFO entries show initiation, SUCCESS/ERROR entries show completion

### Suggested Web Features

1. **Session View**: Display each PID as a collapsible session showing all related transfers
2. **Timeline**: Chronological view of all transfer activities
3. **File Tracking**: Search and filter by filename patterns
4. **Status Dashboard**: Summary of successful vs failed transfers
5. **Destination Analysis**: Group transfers by destination host/path

## Web Dashboard

The project includes a standalone web dashboard for visualizing transfer logs with interactive features.

### Quick Start

```bash
# Start the dashboard server (parses logs and serves web interface)
./serve_dashboard.sh
```

This will:
1. Parse `transfer.log` to generate `transfers.json`
2. Start a local web server
3. Open the dashboard in your browser

### Manual Dashboard Setup

```bash
# Parse logs
python3 parse_transfers.py

# Start web server
python3 -m http.server 8080

# Open http://127.0.0.1:8080/transfer_dashboard.html
```

### Dashboard Features

- **Session View**: Transfer sessions grouped by PID with collapsible details
- **Statistics**: Real-time counts of sessions, entries, and transfer methods
- **Filtering**: Filter by log type (INFO, SUCCESS, ERROR) and transfer method (scp, cp, rsync)
- **Search**: Full-text search across files, destinations, and messages with highlighting
- **Responsive**: Works on desktop and mobile devices
- **Auto-refresh**: Updates every 5 minutes

## File Structure

```
log_monitoring/
├── transfer.log              # Input log file
├── parse_transfers.py        # Main parser script
├── test_parser.py           # Test suite
├── transfers.json           # Generated JSON output
├── transfer_dashboard.html  # Web dashboard
├── serve_dashboard.sh       # Dashboard server script
└── README.md               # This documentation
```

## Development Notes

- PIDs are used purely for grouping - no PID-level statistics are calculated
- The parser handles multiple transfer methods (scp, cp, rsync)
- Regex patterns are designed to be easily extensible for new log formats
- All sessions are sorted by PID, entries within sessions by timestamp