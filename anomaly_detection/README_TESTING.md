# Testing Anomaly Detection

## Current Issue

The detector reads **summary statistics** from the JSON files:
- `total_core_hours`: Total for all 48 hours
- `total_job_runs`: Total count for 48 hours
- `job_rate`: Counts recent jobs (last hour)

When we modify the JSON by removing jobs, the **summaries don't automatically recalculate**.

## Better Test Approach

### Option 1: Live Testing (Recommended)
Run the detector continuously and watch for real anomalies:

```bash
# Terminal 1: Run detector
./detector.py --config config/detection_config_local.yaml

# Terminal 2: Watch for anomalies
tail -f anomaly_detector.log
tail -f alerts/alert_history.log

# Terminal 3: Periodically fetch fresh data
watch -n 300 ./fetch_data.sh  # Every 5 minutes
```

The detector will:
- Learn normal patterns from the 50 hourly data points
- Compare each new 5-minute check against the baseline
- Detect when metrics deviate significantly

### Option 2: Simulate Time-Series Data
Create artificial hourly buckets with anomalies:

```python
# Add to historical_metrics.json:
# - 40 hours of "normal" activity
# - 2 hours with 50% reduction (anomaly)
# - 6 hours of normal activity
```

Then detector will spot the 2-hour anomaly.

### Option 3: Manual Threshold Test
Directly test z-score calculation:

```python
python3 << 'PYEOF'
import numpy as np

# Baseline: 50 hours of normal activity
normal_job_rate = [140, 145, 138, 142, 150, 148, 139] * 7  # ~140-150 jobs/hour

mean = np.mean(normal_job_rate)
std = np.std(normal_job_rate)

# Test values
test_values = [145, 100, 50, 200]

for val in test_values:
    z_score = abs((val - mean) / std)
    print(f"Value: {val}, Mean: {mean:.1f}, Std: {std:.1f}, Z-score: {z_score:.2f}")
    if z_score >= 3.0:
        print("  -> CRITICAL anomaly!")
    elif z_score >= 2.0:
        print("  -> WARNING anomaly!")
    else:
        print("  -> Normal")
PYEOF
```

## What We Learned

The detector is working correctly - it just needs:
1. **Real-time data** to compare against baseline, OR
2. **Proper simulation** of time-series with anomalies

The current test modifies totals, but doesn't simulate a "current reading" that differs from historical patterns.

## Recommended Next Steps

1. **Deploy to jeffsc8** with historical_metrics.json
2. **Run continuously** for a few hours
3. **Watch logs** for natural variations
4. **Inject a real test**: Stop a cron job temporarily and see if detected

This will validate detection in production conditions.
