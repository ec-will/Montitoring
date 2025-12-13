#!/usr/bin/env python3
"""
Alert Manager for Anomaly Detection System

Handles alert generation, formatting, and delivery through multiple channels.
"""

import json
import os
import smtplib
import requests
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List
import yaml


class AlertManager:
    """Manages alert delivery across multiple channels"""
    
    def __init__(self, config_path: str):
        """Initialize alert manager with configuration"""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.alert_config = self.config['alerts']
    
    def send_alert(self, anomaly: Dict):
        """Send alert through all enabled channels"""
        if not self.alert_config['enabled']:
            print("Alerting is disabled")
            return
        
        # Format alert message
        message = self._format_alert_message(anomaly)
        
        # Send through enabled channels
        if self.alert_config['channels']['email']['enabled']:
            self._send_email_alert(anomaly, message)
        
        if self.alert_config['channels']['slack']['enabled']:
            self._send_slack_alert(anomaly, message)
        
        if self.alert_config['channels']['log']['enabled']:
            self._log_alert(anomaly, message)
    
    def _format_alert_message(self, anomaly: Dict) -> str:
        """Format anomaly data into readable alert message"""
        severity_emoji = {
            'critical': '🚨',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        
        emoji = severity_emoji.get(anomaly['severity'], '❗')
        
        message = f"""{emoji} HPC Cluster Anomaly Detected

Severity: {anomaly['severity'].upper()}
Metric: {anomaly['metric']}
Current Value: {anomaly['current_value']:.2f}
Expected Range: {anomaly['expected_mean']:.2f} ± {anomaly['std_dev']:.2f}
Deviation: {anomaly['z_score']:.2f} standard deviations
Time: {anomaly['timestamp']}

This anomaly indicates unusual cluster behavior that may require investigation.
"""
        return message
    
    def _send_email_alert(self, anomaly: Dict, message: str):
        """Send alert via email"""
        email_config = self.alert_config['channels']['email']
        
        try:
            msg = MIMEMultipart()
            msg['From'] = email_config['from_address']
            msg['To'] = ', '.join(email_config['recipients'])
            msg['Subject'] = f"[{anomaly['severity'].upper()}] HPC Anomaly: {anomaly['metric']}"
            
            msg.attach(MIMEText(message, 'plain'))
            
            server = smtplib.SMTP(
                email_config['smtp_server'], 
                email_config['smtp_port']
            )
            server.send_message(msg)
            server.quit()
            
            print(f"Email alert sent to {email_config['recipients']}")
        except Exception as e:
            print(f"Failed to send email alert: {e}")
    
    def _send_slack_alert(self, anomaly: Dict, message: str):
        """Send alert via Slack webhook"""
        slack_config = self.alert_config['channels']['slack']
        
        try:
            # Color code based on severity
            color_map = {
                'critical': '#ff0000',
                'warning': '#ffaa00',
                'info': '#00aaff'
            }
            color = color_map.get(anomaly['severity'], '#cccccc')
            
            payload = {
                'attachments': [{
                    'color': color,
                    'title': f"{anomaly['severity'].upper()}: {anomaly['metric']}",
                    'text': message,
                    'footer': 'HPC Anomaly Detection System',
                    'ts': int(datetime.now().timestamp())
                }]
            }
            
            response = requests.post(
                slack_config['webhook_url'],
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                print("Slack alert sent successfully")
            else:
                print(f"Failed to send Slack alert: {response.status_code}")
        except Exception as e:
            print(f"Failed to send Slack alert: {e}")
    
    def _log_alert(self, anomaly: Dict, message: str):
        """Log alert to file"""
        log_config = self.alert_config['channels']['log']
        log_file = log_config['log_file']
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        with open(log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(message)
            f.write(f"\n{'='*60}\n")
        
        print(f"Alert logged to {log_file}")
    
    def test_alerts(self):
        """Test alert delivery with mock anomaly"""
        print("Testing alert delivery...\n")
        
        mock_anomaly = {
            'metric': 'test_metric',
            'severity': 'warning',
            'current_value': 100.5,
            'expected_mean': 50.0,
            'std_dev': 10.0,
            'z_score': 5.05,
            'timestamp': datetime.now().isoformat()
        }
        
        self.send_alert(mock_anomaly)
        print("\nTest alert sent through all enabled channels")


def main():
    parser = argparse.ArgumentParser(
        description='Alert Manager for HPC Anomaly Detection'
    )
    parser.add_argument(
        '--config',
        default='config/detection_config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test alert delivery'
    )
    parser.add_argument(
        '--anomaly-file',
        help='JSON file containing anomaly data to send'
    )
    
    args = parser.parse_args()
    
    manager = AlertManager(args.config)
    
    if args.test:
        manager.test_alerts()
    elif args.anomaly_file:
        with open(args.anomaly_file, 'r') as f:
            anomaly = json.load(f)
        manager.send_alert(anomaly)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
