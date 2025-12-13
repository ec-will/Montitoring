# Anomaly Detection - Session Context

## Current State
- **Branch:** anomaly-alerting (10 commits)
- **Location:** ~/projects/monitoring/anomaly_detection/
- **Status:** Per-job detector working, ready for testing

## What Was Built

**job_detector.py** - Learns each job's pattern:
- Run frequency (e.g., every 5 min)
- Execution duration (e.g., 385 ± 146 sec)
- Detects missing jobs & duration anomalies
- Tracks 65 jobs (34 login + 31 cluster)

## Key Features
- Bootstraps from 48hr JSON data
- Python 3.6+ compatible
- UTC timestamps (works anywhere)
- Persists across restarts

## Usage
```bash
cd anomaly_detection
./fetch_data.sh                      # Get data from jeffsc8
./job_detector.py --report           # Show learned patterns
./job_detector.py                    # Run monitoring
```

## Next Steps
1. Test for 24 hours
2. Stop a cron job to test alerts
3. Deploy to production
4. Merge to main

## Important Files
- job_detector.py (main)
- fetch_data.sh (data fetch)
- config/detection_config_local.yaml
