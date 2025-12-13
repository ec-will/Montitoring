#!/usr/bin/env python3
"""
Anomaly Detection Engine for HPC Cluster Monitoring

Monitors cluster metrics and detects anomalies using statistical methods
and machine learning models.

Features:
- Bootstraps from 48-hour historical data in JSON files
- Persists learned patterns across restarts
- Python 3.6+ compatible
"""

import json
import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
import yaml

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('anomaly_detector')


def parse_iso_datetime(timestamp_str):
    """Parse ISO format datetime string (Python 3.6 compatible)"""
    # Handle timezone info
    timestamp_str = timestamp_str.replace('Z', '+00:00')
    
    # Remove timezone for Python 3.6 compatibility
    if '+' in timestamp_str:
        timestamp_str = timestamp_str.split('+')[0]
    
    # Parse common ISO formats
    for fmt in ['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue
    
    raise ValueError("Cannot parse timestamp: {}".format(timestamp_str))


class AnomalyDetector:
    """Main anomaly detection engine"""
    
    def __init__(self, config_path):
        """Initialize detector with configuration"""
        self.config = self._load_config(config_path)
        self.historical_data = []
        self.last_check = None
        self.alert_cooldowns = {}
        self.history_file = 'historical_metrics.json'
        
        # Set up logging from config
        log_level = getattr(logging, self.config['logging']['level'])
        logger.setLevel(log_level)
        
        # Create file handler
        log_file = self.config['logging']['file']
        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(handler)
        
        logger.info("Anomaly detector initialized")
        
        # Load or bootstrap historical data
        self._initialize_historical_data()
    
    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _initialize_historical_data(self):
        """Initialize historical data from persistence or bootstrap from JSON"""
        # Try to load from persistent storage first
        if self._load_historical_data():
            logger.info("Loaded {} data points from persistent storage".format(
                len(self.historical_data)
            ))
            return
        
        # Bootstrap from 48-hour JSON data
        logger.info("No persistent data found, bootstrapping from JSON files...")
        self._bootstrap_from_json()
    
    def _load_historical_data(self):
        """Load historical data from persistent storage"""
        if not os.path.exists(self.history_file):
            return False
        
        try:
            with open(self.history_file, 'r') as f:
                data = json.load(f)
                self.historical_data = data.get('metrics', [])
                logger.info("Loaded historical data from {}".format(self.history_file))
                return True
        except Exception as e:
            logger.warning("Failed to load historical data: {}".format(e))
            return False
    
    def _save_historical_data(self):
        """Save historical data to persistent storage"""
        try:
            data = {
                'metrics': self.historical_data,
                'saved_at': datetime.now().isoformat(),
                'data_points': len(self.historical_data)
            }
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("Saved {} data points to {}".format(
                len(self.historical_data), self.history_file
            ))
        except Exception as e:
            logger.error("Failed to save historical data: {}".format(e))
    
    def _bootstrap_from_json(self):
        """Bootstrap historical metrics from 48-hour JSON data"""
        cluster_data = self._load_data_source(
            self.config['data_sources']['cluster_usage']
        )
        login_data = self._load_data_source(
            self.config['data_sources']['login_jobs']
        )
        
        if not cluster_data and not login_data:
            logger.warning("No data available for bootstrapping")
            return
        
        # Bucket data into hourly intervals
        hourly_buckets = defaultdict(lambda: {
            'job_count': 0,
            'core_hours': 0,
            'login_jobs': 0,
            'users': set()
        })
        
        # Process cluster usage data
        if cluster_data:
            job_usage = cluster_data.get('job_usage', {}).get('jobs', {})
            for job_name, job_data in job_usage.items():
                for run in job_data.get('runs_detail', []):
                    try:
                        start_time = parse_iso_datetime(run['start'])
                        hour_key = start_time.replace(minute=0, second=0, microsecond=0)
                        
                        hourly_buckets[hour_key]['job_count'] += 1
                        hourly_buckets[hour_key]['core_hours'] += run.get('core_hours', 0)
                    except:
                        continue
        
        # Process login jobs data
        if login_data:
            job_runs = login_data.get('job_runs', {}).get('jobs', {})
            for script_name, script_data in job_runs.items():
                for run in script_data.get('runs_detail', []):
                    try:
                        start_time = parse_iso_datetime(run['start'])
                        hour_key = start_time.replace(minute=0, second=0, microsecond=0)
                        
                        hourly_buckets[hour_key]['login_jobs'] += 1
                    except:
                        continue
        
        # Convert buckets to metrics
        for hour_time in sorted(hourly_buckets.keys()):
            bucket = hourly_buckets[hour_time]
            
            # Calculate core utilization (assume 1000 cores capacity)
            total_capacity = 1000
            core_utilization = min(
                (bucket['core_hours'] / 1.0) / total_capacity * 100,
                100
            )
            
            metrics = {
                'timestamp': hour_time.isoformat(),
                'job_rate': bucket['login_jobs'],
                'core_utilization': core_utilization,
                'total_core_hours': bucket['core_hours'],
                'active_jobs': bucket['job_count'],
                'user_count': len(bucket['users'])
            }
            self.historical_data.append(metrics)
        
        logger.info("Bootstrapped {} hourly data points from JSON".format(
            len(self.historical_data)
        ))
        
        # Save bootstrapped data
        self._save_historical_data()
    
    def _load_data_source(self, source_path):
        """Load data from JSON file"""
        if not os.path.exists(source_path):
            logger.warning("Data source not found: {}".format(source_path))
            return None
        
        try:
            with open(source_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse {}: {}".format(source_path, e))
            return None
    
    def collect_current_metrics(self):
        """Collect current metrics from all data sources"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'job_rate': 0,
            'core_utilization': 0,
            'total_core_hours': 0,
            'active_jobs': 0,
            'user_count': 0
        }
        
        # Load cluster usage data
        cluster_data = self._load_data_source(
            self.config['data_sources']['cluster_usage']
        )
        if cluster_data:
            job_usage = cluster_data.get('job_usage', {})
            summary = job_usage.get('summary', {})
            jobs = job_usage.get('jobs', {})
            
            metrics['active_jobs'] = summary.get('total_unique_scripts', len(jobs))
            metrics['total_core_hours'] = summary.get('total_core_hours', 0)
            metrics['user_count'] = len(jobs)
        
        # Load login jobs data
        login_data = self._load_data_source(
            self.config['data_sources']['login_jobs']
        )
        if login_data:
            job_runs = login_data.get('job_runs', {})
            jobs = job_runs.get('jobs', {})
            
            # Count recent jobs (last hour)
            recent_count = 0
            for script_name, script_data in jobs.items():
                for run in script_data.get('runs_detail', [])[:5]:  # Check recent runs
                    try:
                        if self._is_recent(run.get('start'), hours=1):
                            recent_count += 1
                    except:
                        continue
            
            metrics['job_rate'] = recent_count
        
        # Calculate core utilization
        total_capacity = 1000
        metrics['core_utilization'] = min(
            (metrics['total_core_hours'] / 48) / total_capacity * 100,
            100
        )
        
        return metrics
    
    def _is_recent(self, timestamp_str, hours=1):
        """Check if timestamp is within the last N hours"""
        try:
            ts = parse_iso_datetime(timestamp_str)
            return (datetime.now() - ts) < timedelta(hours=hours)
        except:
            return False
    
    def detect_anomalies(self, current_metrics):
        """Detect anomalies in current metrics"""
        anomalies = []
        
        if len(self.historical_data) < self.config['detection']['min_data_points']:
            logger.info(
                "Insufficient historical data: {} points (need {})".format(
                    len(self.historical_data),
                    self.config['detection']['min_data_points']
                )
            )
            return anomalies
        
        # Check each metric if enabled
        if self.config['metrics']['job_submission_rate']:
            job_anomaly = self._check_metric_anomaly(
                'job_rate',
                current_metrics['job_rate'],
                self.config['thresholds']['job_rate']
            )
            if job_anomaly:
                anomalies.append(job_anomaly)
        
        if self.config['metrics']['core_utilization']:
            core_anomaly = self._check_metric_anomaly(
                'core_utilization',
                current_metrics['core_utilization'],
                self.config['thresholds']['core_usage']
            )
            if core_anomaly:
                anomalies.append(core_anomaly)
        
        if self.config['metrics']['core_hours_consumption']:
            corehours_anomaly = self._check_metric_anomaly(
                'total_core_hours',
                current_metrics['total_core_hours'],
                self.config['thresholds']['core_hours']
            )
            if corehours_anomaly:
                anomalies.append(corehours_anomaly)
        
        return anomalies
    
    def _check_metric_anomaly(self, metric_name, current_value, thresholds):
        """Check if a metric value is anomalous using statistical methods"""
        
        # Extract historical values for this metric
        historical_values = [
            m.get(metric_name, 0) 
            for m in self.historical_data
        ]
        
        if len(historical_values) == 0:
            return None
        
        # Calculate statistics
        mean = np.mean(historical_values)
        std = np.std(historical_values)
        
        if std == 0:
            return None
        
        # Calculate z-score
        z_score = abs((current_value - mean) / std)
        
        # Determine severity
        severity = None
        if z_score >= thresholds['critical']:
            severity = 'critical'
        elif z_score >= thresholds['warning']:
            severity = 'warning'
        
        if severity:
            return {
                'metric': metric_name,
                'severity': severity,
                'current_value': current_value,
                'expected_mean': mean,
                'std_dev': std,
                'z_score': z_score,
                'timestamp': datetime.now().isoformat()
            }
        
        return None
    
    def run_continuous(self):
        """Run detector in continuous monitoring mode"""
        logger.info("Starting continuous monitoring...")
        logger.info("Historical data points: {}".format(len(self.historical_data)))
        
        save_counter = 0
        save_interval = 12  # Save every 12 checks (1 hour at 5-min intervals)
        
        try:
            while True:
                # Collect current metrics
                current_metrics = self.collect_current_metrics()
                logger.debug("Current metrics: {}".format(current_metrics))
                
                # Add to historical data
                self.historical_data.append(current_metrics)
                
                # Keep only data within lookback window
                lookback_hours = self.config['detection']['lookback_hours']
                cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
                self.historical_data = [
                    m for m in self.historical_data
                    if parse_iso_datetime(m['timestamp']) > cutoff_time
                ]
                
                # Detect anomalies
                anomalies = self.detect_anomalies(current_metrics)
                
                # Handle detected anomalies
                if anomalies:
                    self._handle_anomalies(anomalies)
                
                # Periodic save
                save_counter += 1
                if save_counter >= save_interval:
                    self._save_historical_data()
                    save_counter = 0
                
                # Wait for next check
                time.sleep(self.config['detection']['check_interval'])
                
        except KeyboardInterrupt:
            logger.info("Detector stopped by user")
            self._save_historical_data()
        except Exception as e:
            logger.error("Detector error: {}".format(e), exc_info=True)
            self._save_historical_data()
    
    def _handle_anomalies(self, anomalies):
        """Handle detected anomalies (log, alert, etc.)"""
        for anomaly in anomalies:
            # Check cooldown
            metric = anomaly['metric']
            now = datetime.now()
            
            if metric in self.alert_cooldowns:
                last_alert = self.alert_cooldowns[metric]
                cooldown = self.config['alerts']['cooldown_period']
                if (now - last_alert).total_seconds() < cooldown:
                    logger.debug("Skipping alert for {} (in cooldown)".format(metric))
                    continue
            
            # Log anomaly
            logger.warning(
                "ANOMALY DETECTED - {}: {:.2f} "
                "(expected: {:.2f} ± {:.2f}, "
                "z-score: {:.2f}, "
                "severity: {})".format(
                    anomaly['metric'],
                    anomaly['current_value'],
                    anomaly['expected_mean'],
                    anomaly['std_dev'],
                    anomaly['z_score'],
                    anomaly['severity']
                )
            )
            
            # Update cooldown
            self.alert_cooldowns[metric] = now
            
            # Send alerts if enabled
            if self.config['alerts']['enabled']:
                self._send_alert(anomaly)
    
    def _send_alert(self, anomaly):
        """Send alert through configured channels"""
        # For now, just log to alert file
        log_channel = self.config['alerts']['channels']['log']
        if log_channel['enabled']:
            alert_file = log_channel['log_file']
            os.makedirs(os.path.dirname(alert_file), exist_ok=True)
            
            with open(alert_file, 'a') as f:
                f.write("{} - {} - {}: {:.2f} (z-score: {:.2f})\n".format(
                    anomaly['timestamp'],
                    anomaly['severity'].upper(),
                    anomaly['metric'],
                    anomaly['current_value'],
                    anomaly['z_score']
                ))


def main():
    parser = argparse.ArgumentParser(
        description='HPC Cluster Anomaly Detection System'
    )
    parser.add_argument(
        '--config',
        default='config/detection_config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run in test mode (single check)'
    )
    
    args = parser.parse_args()
    
    # Initialize detector
    detector = AnomalyDetector(args.config)
    
    if args.test:
        # Test mode - single check
        metrics = detector.collect_current_metrics()
        print("Current metrics:")
        for key, value in metrics.items():
            print("  {}: {}".format(key, value))
        
        print("\nHistorical data points: {}".format(len(detector.historical_data)))
        if len(detector.historical_data) >= detector.config['detection']['min_data_points']:
            print("✓ Ready to detect anomalies")
        else:
            print("⚠ Need {} more data points before detection can start".format(
                detector.config['detection']['min_data_points'] - len(detector.historical_data)
            ))
    else:
        # Continuous monitoring
        detector.run_continuous()


if __name__ == '__main__':
    main()
