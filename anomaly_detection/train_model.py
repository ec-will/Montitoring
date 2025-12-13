#!/usr/bin/env python3
"""
Model Training for Anomaly Detection

Trains models on historical data for improved anomaly detection.
Supports statistical baselines and ML-based models.
"""

import json
import os
import argparse
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import numpy as np
import yaml

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.svm import OneClassSVM
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not available. Only statistical models supported.")


class ModelTrainer:
    """Trains anomaly detection models on historical data"""
    
    def __init__(self, config_path: str):
        """Initialize trainer with configuration"""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.model_dir = self.config['model']['model_dir']
        os.makedirs(self.model_dir, exist_ok=True)
    
    def load_historical_data(self, data_dir: str, lookback_days: int) -> List[Dict]:
        """Load historical monitoring data"""
        # This is a placeholder - actual implementation would load
        # historical JSON snapshots from data directory
        print(f"Loading historical data from {data_dir} ({lookback_days} days)")
        
        # For now, return empty list
        # Real implementation would scan directory for dated JSON files
        return []
    
    def extract_features(self, data: List[Dict]) -> np.ndarray:
        """Extract feature vectors from historical data"""
        features = []
        
        for record in data:
            feature_vector = [
                record.get('job_rate', 0),
                record.get('core_utilization', 0),
                record.get('total_core_hours', 0),
                record.get('active_jobs', 0),
                record.get('user_count', 0)
            ]
            features.append(feature_vector)
        
        return np.array(features)
    
    def train_statistical_model(self, data: List[Dict]) -> Dict:
        """Train statistical baseline model (mean, std dev)"""
        print("Training statistical model...")
        
        if len(data) == 0:
            print("Warning: No historical data available")
            return {}
        
        features = self.extract_features(data)
        
        # Calculate statistics for each metric
        model = {
            'type': 'statistical',
            'metrics': {
                'job_rate': {
                    'mean': float(np.mean(features[:, 0])),
                    'std': float(np.std(features[:, 0])),
                    'min': float(np.min(features[:, 0])),
                    'max': float(np.max(features[:, 0]))
                },
                'core_utilization': {
                    'mean': float(np.mean(features[:, 1])),
                    'std': float(np.std(features[:, 1])),
                    'min': float(np.min(features[:, 1])),
                    'max': float(np.max(features[:, 1]))
                },
                'total_core_hours': {
                    'mean': float(np.mean(features[:, 2])),
                    'std': float(np.std(features[:, 2])),
                    'min': float(np.min(features[:, 2])),
                    'max': float(np.max(features[:, 2]))
                },
                'active_jobs': {
                    'mean': float(np.mean(features[:, 3])),
                    'std': float(np.std(features[:, 3])),
                    'min': float(np.min(features[:, 3])),
                    'max': float(np.max(features[:, 3]))
                },
                'user_count': {
                    'mean': float(np.mean(features[:, 4])),
                    'std': float(np.std(features[:, 4])),
                    'min': float(np.min(features[:, 4])),
                    'max': float(np.max(features[:, 4]))
                }
            },
            'trained_at': datetime.now().isoformat(),
            'training_samples': len(data)
        }
        
        return model
    
    def train_isolation_forest(self, data: List[Dict]) -> Dict:
        """Train Isolation Forest model"""
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn required for Isolation Forest")
        
        print("Training Isolation Forest model...")
        
        features = self.extract_features(data)
        
        # Normalize features
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)
        
        # Train model
        model = IsolationForest(
            contamination=0.1,  # Expect 10% anomalies
            random_state=42
        )
        model.fit(features_scaled)
        
        return {
            'type': 'isolation_forest',
            'model': model,
            'scaler': scaler,
            'trained_at': datetime.now().isoformat(),
            'training_samples': len(data)
        }
    
    def save_model(self, model: Dict, model_name: str = 'anomaly_model'):
        """Save trained model to disk"""
        model_path = os.path.join(self.model_dir, f'{model_name}.pkl')
        
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        print(f"Model saved to {model_path}")
        
        # Also save metadata as JSON
        metadata = {
            'type': model['type'],
            'trained_at': model['trained_at'],
            'training_samples': model['training_samples']
        }
        
        if model['type'] == 'statistical':
            metadata['metrics'] = model['metrics']
        
        metadata_path = os.path.join(self.model_dir, f'{model_name}_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Model metadata saved to {metadata_path}")
    
    def train(self, data_dir: str, lookback_days: int):
        """Train model on historical data"""
        # Load historical data
        data = self.load_historical_data(data_dir, lookback_days)
        
        if len(data) == 0:
            print("No historical data available. Creating baseline model.")
            # Create baseline with default values
            model = {
                'type': 'statistical',
                'metrics': {},
                'trained_at': datetime.now().isoformat(),
                'training_samples': 0
            }
        else:
            # Train model based on configured type
            model_type = self.config['model']['type']
            
            if model_type == 'statistical':
                model = self.train_statistical_model(data)
            elif model_type == 'isolation_forest':
                model = self.train_isolation_forest(data)
            elif model_type == 'one_class_svm':
                # Placeholder for OneClassSVM
                model = self.train_statistical_model(data)
            else:
                raise ValueError(f"Unknown model type: {model_type}")
        
        # Save model
        self.save_model(model)
        
        print(f"\nTraining complete!")
        print(f"Model type: {model['type']}")
        print(f"Training samples: {model['training_samples']}")
        print(f"Trained at: {model['trained_at']}")


def main():
    parser = argparse.ArgumentParser(
        description='Train anomaly detection models'
    )
    parser.add_argument(
        '--config',
        default='config/detection_config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--data-dir',
        default='../data',
        help='Directory containing historical data'
    )
    parser.add_argument(
        '--lookback-days',
        type=int,
        default=30,
        help='Number of days of historical data to use'
    )
    
    args = parser.parse_args()
    
    trainer = ModelTrainer(args.config)
    trainer.train(args.data_dir, args.lookback_days)


if __name__ == '__main__':
    main()
