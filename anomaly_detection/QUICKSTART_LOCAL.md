# Quick Start - Local Development

Run anomaly detection on your local machine by fetching data from jeffsc8.

## Setup (One-time)

1. **Install dependencies:**
   ```bash
   pip3 install numpy pyyaml requests
   
   # Optional: for ML models
   pip3 install scikit-learn
   ```

2. **Verify SSH access:**
   ```bash
   ssh jeffsc8 "echo 'Connection OK'"
   ```

## Running Locally

### 1. Fetch Data
```bash
cd anomaly_detection
./fetch_data.sh
```

This downloads the latest JSON files from jeffsc8 to the `data/` directory.

### 2. Test the Detector
```bash
./detector.py --config config/detection_config_local.yaml --test
```

You should see current metrics displayed.

### 3. Run Continuous Monitoring
```bash
./detector.py --config config/detection_config_local.yaml
```

The detector will:
- Check metrics every 5 minutes
- Use the local JSON files
- Log alerts to `alerts/alert_history.log`

### 4. Automate Data Fetching

Add to crontab to fetch data every 5 minutes:
```bash
crontab -e

# Add:
*/5 * * * * /path/to/anomaly_detection/fetch_data.sh
```

Or manually fetch before each run:
```bash
./fetch_data.sh && ./detector.py --config config/detection_config_local.yaml --test
```

## Monitoring

**View logs:**
```bash
tail -f anomaly_detector.log
```

**View alerts:**
```bash
tail -f alerts/alert_history.log
```

**View fetch log:**
```bash
tail -f fetch_data.log
```

**Check data freshness:**
```bash
ls -lh data/*.json
```

## Configuration Files

- `config/detection_config.yaml` - For HPC cluster deployment (relative paths)
- `config/detection_config_local.yaml` - For local development (points to `data/`)

## Workflow

```
jeffsc8 (HPC Cluster)           Your Local Machine
---------------------           ------------------
Cron generates JSON   →         fetch_data.sh downloads
                                     ↓
                                data/*.json files
                                     ↓
                                detector.py reads
                                     ↓
                                Anomalies detected
                                     ↓
                                alerts/alert_history.log
```

## Tips

- Run `fetch_data.sh` in a separate terminal/screen if running detector continuously
- The detector doesn't auto-fetch - you control when to update data
- Can fetch on-demand for testing specific time periods
