#!/usr/bin/env python3
"""
Per-Job Anomaly Detection for HPC Cluster Monitoring

Learns patterns for each individual job:
- Expected run frequency
- Expected execution duration
- Last seen time

Detects:
- Missing jobs (should have run but didn't)
- Execution anomalies (too fast/slow)
- Frequency anomalies

Python 3.6+ compatible
"""

import json
import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
import yaml

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('job_detector')


def parse_iso_datetime(timestamp_str):
    """Parse ISO format datetime string (Python 3.6 compatible)"""
    timestamp_str = timestamp_str.replace('Z', '+00:00')
    if '+' in timestamp_str:
        timestamp_str = timestamp_str.split('+')[0]
    
    for fmt in ['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue
    
    raise ValueError("Cannot parse timestamp: {}".format(timestamp_str))


class JobProfile:
    """Statistical profile for a single job"""
    
    def __init__(self, job_name):
        self.job_name = job_name
        self.run_intervals = []  # Time between runs (seconds)
        self.durations = []  # Execution durations (seconds)
        self.last_seen = None
        self.total_runs = 0
    
    def add_run(self, start_time, duration):
        """Add a job run to the profile"""
        self.total_runs += 1
        
        if self.last_seen:
            interval = (start_time - self.last_seen).total_seconds()
            self.run_intervals.append(interval)
        
        self.durations.append(duration)
        self.last_seen = start_time
    
    def get_stats(self):
        """Get statistical summary of this job"""
        stats = {
            'job_name': self.job_name,
            'total_runs': self.total_runs,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }
        
        if len(self.run_intervals) > 0:
            stats['interval_mean'] = float(np.mean(self.run_intervals))
            stats['interval_std'] = float(np.std(self.run_intervals))
            stats['interval_min'] = float(np.min(self.run_intervals))
            stats['interval_max'] = float(np.max(self.run_intervals))
        
        if len(self.durations) > 0:
            stats['duration_mean'] = float(np.mean(self.durations))
            stats['duration_std'] = float(np.std(self.durations))
            stats['duration_min'] = float(np.min(self.durations))
            stats['duration_max'] = float(np.max(self.durations))
        
        return stats
    
    def check_missing(self, current_time, threshold_multiplier=2.5):
        """Check if job is missing (should have run but didn't)"""
        if not self.last_seen or len(self.run_intervals) < 3:
            return None
        
        expected_interval = np.mean(self.run_intervals)
        time_since_last = (current_time - self.last_seen).total_seconds()
        
        # Alert if we've exceeded expected interval by threshold
        if time_since_last > expected_interval * threshold_multiplier:
            return {
                'type': 'missing_job',
                'job_name': self.job_name,
                'last_seen': self.last_seen.isoformat(),
                'expected_interval': expected_interval,
                'actual_interval': time_since_last,
                'severity': 'critical' if time_since_last > expected_interval * 3 else 'warning'
            }
        
        return None
    
    def check_duration_anomaly(self, duration, threshold_sigma=2.5):
        """Check if execution duration is anomalous"""
        if len(self.durations) < 5:
            return None
        
        mean = np.mean(self.durations)
        std = np.std(self.durations)
        
        if std == 0:
            return None
        
        z_score = abs((duration - mean) / std)
        
        if z_score >= threshold_sigma:
            return {
                'type': 'duration_anomaly',
                'job_name': self.job_name,
                'duration': duration,
                'expected_mean': mean,
                'std_dev': std,
                'z_score': z_score,
                'severity': 'critical' if z_score >= 3.0 else 'warning'
            }
        
        return None


class JobAnomalyDetector:
    """Detector that learns and monitors individual job patterns"""
    
    def __init__(self, config_path):
        """Initialize detector"""
        self.config = self._load_config(config_path)
        self.job_profiles = {}  # job_name -> JobProfile
        self.profile_file = 'job_profiles.json'
        self.alert_cooldowns = {}
        
        # Set up logging
        log_level = getattr(logging, self.config['logging']['level'])
        logger.setLevel(log_level)
        
        log_file = self.config['logging']['file']
        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(handler)
        
        logger.info("Job anomaly detector initialized")
        
        # Load or build profiles
        self._initialize_profiles()
    
    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _initialize_profiles(self):
        """Load existing profiles or build from JSON data"""
        if self._load_profiles():
            logger.info("Loaded {} job profiles from {}".format(
                len(self.job_profiles), self.profile_file
            ))
        else:
            logger.info("Building job profiles from historical data...")
            self._build_profiles_from_json()
    
    def _load_profiles(self):
        """Load profiles from disk"""
        if not os.path.exists(self.profile_file):
            return False
        
        try:
            with open(self.profile_file, 'r') as f:
                data = json.load(f)
            
            for job_name, profile_data in data.get('profiles', {}).items():
                profile = JobProfile(job_name)
                profile.total_runs = profile_data['total_runs']
                profile.run_intervals = profile_data.get('run_intervals', [])
                profile.durations = profile_data.get('durations', [])
                
                if profile_data.get('last_seen'):
                    profile.last_seen = parse_iso_datetime(profile_data['last_seen'])
                
                self.job_profiles[job_name] = profile
            
            return True
        except Exception as e:
            logger.warning("Failed to load profiles: {}".format(e))
            return False
    
    def _save_profiles(self):
        """Save profiles to disk"""
        try:
            data = {
                'profiles': {},
                'saved_at': datetime.utcnow().isoformat(),
                'job_count': len(self.job_profiles)
            }
            
            for job_name, profile in self.job_profiles.items():
                data['profiles'][job_name] = {
                    'total_runs': profile.total_runs,
                    'run_intervals': profile.run_intervals[-100:],  # Keep last 100
                    'durations': profile.durations[-100:],  # Keep last 100
                    'last_seen': profile.last_seen.isoformat() if profile.last_seen else None
                }
            
            with open(self.profile_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug("Saved {} job profiles".format(len(self.job_profiles)))
        except Exception as e:
            logger.error("Failed to save profiles: {}".format(e))
    
    def _build_profiles_from_json(self):
        """Build job profiles from 48-hour historical JSON data"""
        # Load login jobs data
        login_data = self._load_data_source(
            self.config['data_sources']['login_jobs']
        )
        
        if not login_data:
            logger.warning("No login jobs data available")
            return
        
        jobs = login_data.get('job_runs', {}).get('jobs', {})
        
        for script_name, script_data in jobs.items():
            profile = JobProfile(script_name)
            
            # Sort runs by start time
            runs = sorted(
                script_data.get('runs_detail', []),
                key=lambda r: r.get('start', '')
            )
            
            for run in runs:
                try:
                    start_time = parse_iso_datetime(run['start'])
                    duration = run.get('duration_seconds', 0)
                    profile.add_run(start_time, duration)
                except:
                    continue
            
            if profile.total_runs > 0:
                self.job_profiles[script_name] = profile
        
        logger.info("Built profiles for {} jobs".format(len(self.job_profiles)))
        
        # Load cluster jobs data
        cluster_data = self._load_data_source(
            self.config['data_sources']['cluster_usage']
        )
        
        if cluster_data:
            jobs = cluster_data.get('job_usage', {}).get('jobs', {})
            
            for job_name, job_data in jobs.items():
                profile = JobProfile(job_name)
                
                runs = sorted(
                    job_data.get('runs_detail', []),
                    key=lambda r: r.get('start', '')
                )
                
                for run in runs:
                    try:
                        start_time = parse_iso_datetime(run['start'])
                        # Estimate duration from core_hours and cores
                        cores = run.get('cores', 1)
                        core_hours = run.get('core_hours', 0)
                        duration = (core_hours / cores) * 3600 if cores > 0 else 0
                        profile.add_run(start_time, duration)
                    except:
                        continue
                
                if profile.total_runs > 0:
                    self.job_profiles[job_name] = profile
            
            logger.info("Total profiles (including cluster): {}".format(
                len(self.job_profiles)
            ))
        
        # Save initial profiles
        self._save_profiles()
    
    def _load_data_source(self, source_path):
        """Load data from JSON file"""
        if not os.path.exists(source_path):
            logger.warning("Data source not found: {}".format(source_path))
            return None
        
        try:
            with open(source_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to parse {}: {}".format(source_path, e))
            return None
    
    def detect_anomalies(self):
        """Detect anomalies across all jobs"""
        anomalies = []
        current_time = datetime.utcnow()
        
        # Check for missing jobs
        for job_name, profile in self.job_profiles.items():
            missing_alert = profile.check_missing(current_time)
            if missing_alert:
                anomalies.append(missing_alert)
        
        return anomalies
    
    def check_new_run(self, job_name, start_time, duration):
        """Check a new job run for anomalies"""
        if job_name not in self.job_profiles:
            self.job_profiles[job_name] = JobProfile(job_name)
        
        profile = self.job_profiles[job_name]
        
        # Check for duration anomaly before adding
        duration_alert = profile.check_duration_anomaly(duration)
        
        # Add the run to profile
        profile.add_run(start_time, duration)
        
        return duration_alert
    
    def run_continuous(self):
        """Run detector in continuous monitoring mode"""
        logger.info("Starting continuous job monitoring...")
        logger.info("Tracking {} jobs".format(len(self.job_profiles)))
        
        save_counter = 0
        save_interval = 12  # Save every hour
        
        try:
            while True:
                # Detect missing jobs
                anomalies = self.detect_anomalies()
                
                if anomalies:
                    self._handle_anomalies(anomalies)
                
                # Periodic save
                save_counter += 1
                if save_counter >= save_interval:
                    self._save_profiles()
                    save_counter = 0
                
                # Wait for next check
                time.sleep(self.config['detection']['check_interval'])
                
        except KeyboardInterrupt:
            logger.info("Detector stopped by user")
            self._save_profiles()
        except Exception as e:
            logger.error("Detector error: {}".format(e), exc_info=True)
            self._save_profiles()
    
    def _handle_anomalies(self, anomalies):
        """Handle detected anomalies"""
        for anomaly in anomalies:
            # Check cooldown
            alert_key = "{}:{}".format(anomaly['job_name'], anomaly['type'])
            now = datetime.utcnow()
            
            if alert_key in self.alert_cooldowns:
                last_alert = self.alert_cooldowns[alert_key]
                cooldown = self.config['alerts']['cooldown_period']
                if (now - last_alert).total_seconds() < cooldown:
                    continue
            
            # Log anomaly
            if anomaly['type'] == 'missing_job':
                logger.warning(
                    "MISSING JOB - {}: Last seen {:.1f} hours ago (expected every {:.1f} hours)".format(
                        anomaly['job_name'],
                        anomaly['actual_interval'] / 3600,
                        anomaly['expected_interval'] / 3600
                    )
                )
            elif anomaly['type'] == 'duration_anomaly':
                logger.warning(
                    "DURATION ANOMALY - {}: {:.1f}s (expected {:.1f}s ± {:.1f}s, z={:.2f})".format(
                        anomaly['job_name'],
                        anomaly['duration'],
                        anomaly['expected_mean'],
                        anomaly['std_dev'],
                        anomaly['z_score']
                    )
                )
            
            # Update cooldown
            self.alert_cooldowns[alert_key] = now
            
            # Send alert
            if self.config['alerts']['enabled']:
                self._send_alert(anomaly)
    
    def _send_alert(self, anomaly):
        """Send alert through configured channels"""
        log_channel = self.config['alerts']['channels']['log']
        if log_channel['enabled']:
            alert_file = log_channel['log_file']
            os.makedirs(os.path.dirname(alert_file), exist_ok=True)
            
            with open(alert_file, 'a') as f:
                f.write("{} - {} - {} - {}\n".format(
                    datetime.utcnow().isoformat(),
                    anomaly['severity'].upper(),
                    anomaly['type'],
                    anomaly['job_name']
                ))
    
    def print_report(self):
        """Print summary report of all jobs"""
        print("\n=== Job Profile Report ===")
        print("Total jobs tracked: {}".format(len(self.job_profiles)))
        print()
        
        # Sort by frequency (shortest interval first)
        sorted_jobs = sorted(
            self.job_profiles.items(),
            key=lambda x: np.mean(x[1].run_intervals) if len(x[1].run_intervals) > 0 else float('inf')
        )
        
        for job_name, profile in sorted_jobs:  # Top 20
            stats = profile.get_stats()
            
            print("Job: {}".format(job_name))
            print("  Total runs: {}".format(stats['total_runs']))
            
            if 'interval_mean' in stats:
                print("  Run frequency: Every {:.1f} minutes (± {:.1f} min)".format(
                    stats['interval_mean'] / 60,
                    stats['interval_std'] / 60
                ))
            
            if 'duration_mean' in stats:
                print("  Duration: {:.1f} seconds (± {:.1f} sec)".format(
                    stats['duration_mean'],
                    stats['duration_std']
                ))
            
            if stats.get('last_seen'):
                last_seen = parse_iso_datetime(stats['last_seen'])
                hours_ago = (datetime.utcnow() - last_seen).total_seconds() / 3600
                print("  Last seen: {:.1f} hours ago".format(hours_ago))
            
            print()


def main():
    parser = argparse.ArgumentParser(
        description='Per-Job HPC Anomaly Detection'
    )
    parser.add_argument(
        '--config',
        default='config/detection_config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Print job profile report'
    )
    
    args = parser.parse_args()
    
    detector = JobAnomalyDetector(args.config)
    
    if args.report:
        detector.print_report()
    else:
        detector.run_continuous()


if __name__ == '__main__':
    main()
