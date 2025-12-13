# Anomaly Detection & Alerting System

Machine learning-based anomaly detection system for HPC cluster monitoring. Learns normal usage patterns and alerts when anomalies are detected.

## Features

- **Pattern Learning**: Analyzes historical data to understand normal cluster behavior
- **Real-time Detection**: Monitors current metrics against learned patterns
- **Smart Alerting**: Configurable thresholds and notification channels
- **Multiple Metrics**: Tracks job submissions, core usage, execution times, user patterns

## Architecture

```
anomaly_detection/
├── detector.py           # Core anomaly detection engine
├── train_model.py        # Model training from historical data
├── alert_manager.py      # Alert generation and delivery
├── models/               # Trained model storage
├── alerts/               # Alert templates and history
└── config/               # Configuration files
```

## Data Sources

Integrates with existing monitoring infrastructure:
- Cluster job usage data (`dashboard_cluster_usage.json`)
- Login node job tracking (`dashboard_login_jobs.json`)
- Disk usage monitoring (`disk_usage_data.json`)

## Metrics Monitored

1. **Job Submission Rate**: Unusual spikes or drops in job submissions
2. **Core Utilization**: Abnormal cluster core usage patterns
3. **Execution Time**: Jobs taking significantly longer/shorter than normal
4. **User Activity**: Unusual user behavior patterns
5. **Resource Consumption**: Abnormal core-hours consumption

## Detection Methods

- **Statistical**: Z-score, IQR-based outlier detection
- **Time Series**: Seasonal decomposition, trend analysis
- **ML-based**: Isolation Forest, One-Class SVM for complex patterns

## Quick Start

1. **Train initial model** (requires historical data):
   ```bash
   python3 train_model.py --data-dir ../data --lookback-days 30
   ```

2. **Run detector** (continuous monitoring):
   ```bash
   python3 detector.py --config config/detection_config.yaml
   ```

3. **Test alerting**:
   ```bash
   python3 alert_manager.py --test
   ```

## Configuration

Edit `config/detection_config.yaml` to customize:
- Detection sensitivity
- Alert thresholds
- Notification channels (email, Slack, etc.)
- Monitoring intervals

## Alert Examples

- "Job submission rate 3.2σ above normal (45 jobs/hr vs avg 12)"
- "User 'jdoe' core-hours consumption anomaly detected"
- "Cluster utilization dropped to 15% (typical: 60-80%)"

## Development Status

🚧 **In Development** - Initial implementation phase
