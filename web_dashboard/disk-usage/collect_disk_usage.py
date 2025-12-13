#!/usr/bin/env python3
"""
Disk usage data collection script for jeffsc8.
Scans directory tree and generates hierarchical JSON for web visualization.
"""

import os
import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path


def get_human_readable_size(bytes_size):
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f}EB"


def calculate_cost(bytes_size, cost_per_gb=0.09):
    """Calculate storage cost at $0.09 per GB."""
    gigabytes = bytes_size / (1024 ** 3)
    return gigabytes * cost_per_gb


def get_directory_size_du(path):
    """
    Get directory size using du command (faster for large directories).
    Returns size in bytes.
    """
    try:
        # Use du with block size of 1 byte for accuracy
        result = subprocess.run(
            ['du', '-sb', path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=300  # 5 minute timeout
        )
        if result.returncode == 0:
            # du -sb output format: "bytes\tpath"
            size_str = result.stdout.split('\t')[0]
            return int(size_str)
        else:
            print(f"Warning: du failed for {path}: {result.stderr}", file=sys.stderr)
            return 0
    except subprocess.TimeoutExpired:
        print(f"Warning: du timed out for {path}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Warning: Error getting size for {path}: {e}", file=sys.stderr)
        return 0


def scan_directory(root_path, max_depth=3, current_depth=0):
    """
    Recursively scan directory and build hierarchical structure.
    
    Args:
        root_path: Path to scan
        max_depth: Maximum depth to recurse (0 = only immediate children)
        current_depth: Current recursion depth (internal)
    
    Returns:
        Dictionary with directory info and children
    """
    try:
        path_obj = Path(root_path)
        
        # Get total size of this directory
        total_size = get_directory_size_du(root_path)
        
        result = {
            'name': path_obj.name or str(root_path),
            'path': str(root_path),
            'size_bytes': total_size,
            'size_human': get_human_readable_size(total_size),
            'cost': calculate_cost(total_size),
            'children': []
        }
        
        # If we haven't reached max depth, scan subdirectories
        if current_depth < max_depth:
            try:
                # List immediate subdirectories only
                subdirs = []
                for item in os.scandir(root_path):
                    if item.is_dir(follow_symlinks=False):
                        subdirs.append(item.path)
                
                # Sort by size (largest first) - do a quick scan first
                subdir_sizes = []
                for subdir in subdirs:
                    size = get_directory_size_du(subdir)
                    subdir_sizes.append((subdir, size))
                
                # Sort by size descending
                subdir_sizes.sort(key=lambda x: x[1], reverse=True)
                
                # Recursively scan subdirectories
                for subdir, size in subdir_sizes:
                    child = scan_directory(subdir, max_depth, current_depth + 1)
                    result['children'].append(child)
                    
            except PermissionError:
                print(f"Warning: Permission denied accessing {root_path}", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Error scanning subdirectories of {root_path}: {e}", file=sys.stderr)
        
        return result
        
    except Exception as e:
        print(f"Error scanning {root_path}: {e}", file=sys.stderr)
        return {
            'name': str(root_path),
            'path': str(root_path),
            'size_bytes': 0,
            'size_human': '0B',
            'cost': 0.0,
            'children': [],
            'error': str(e)
        }


def scan_top_level_directories(root_path, max_depth=3):
    """
    Scan all subdirectories of the given root path.
    
    Args:
        root_path: Root directory to scan
        max_depth: Maximum depth to recurse for each subdirectory
    
    Returns:
        List of directory info dictionaries
    """
    directories = []
    root_path = Path(root_path).resolve()
    
    try:
        print(f"Scanning {root_path}...", file=sys.stderr)
        
        # Get immediate subdirectories
        subdirs = []
        for item in os.scandir(root_path):
            if item.is_dir(follow_symlinks=False):
                subdirs.append(item.path)
        
        # Scan each subdirectory
        for subdir in subdirs:
            dir_name = Path(subdir).name
            print(f"  Scanning {dir_name}...", file=sys.stderr)
            dir_info = scan_directory(subdir, max_depth=max_depth)
            directories.append(dir_info)
                
    except PermissionError:
        print(f"Error: Permission denied accessing {root_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error scanning {root_path}: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Sort by size descending
    directories.sort(key=lambda x: x['size_bytes'], reverse=True)
    
    return directories


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Collect disk usage data and output as JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'root_dir',
        nargs='?',
        default='~',
        help='Root directory to scan (default: ~)'
    )
    parser.add_argument(
        '--max-depth',
        type=int,
        default=3,
        help='Maximum depth to recurse (default: 3)'
    )
    
    args = parser.parse_args()
    
    # Expand ~ to home directory
    root_dir = os.path.expanduser(args.root_dir)
    root_dir = os.path.abspath(root_dir)
    
    if not os.path.exists(root_dir):
        print(f"Error: Directory does not exist: {root_dir}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.isdir(root_dir):
        print(f"Error: Not a directory: {root_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Starting disk usage collection from {root_dir}...", file=sys.stderr)
    print(f"Max depth: {args.max_depth}", file=sys.stderr)
    
    # Scan directories
    directories = scan_top_level_directories(root_dir, max_depth=args.max_depth)
    
    # Calculate total
    total_bytes = sum(d['size_bytes'] for d in directories)
    total_cost = sum(d['cost'] for d in directories)
    
    # Build output structure
    output = {
        'generated_at': datetime.now().isoformat(),
        'hostname': os.uname().nodename,
        'root_path': root_dir,
        'max_depth': args.max_depth,
        'total_size_bytes': total_bytes,
        'total_size_human': get_human_readable_size(total_bytes),
        'total_cost': total_cost,
        'cost_per_gb': 0.09,
        'directories': directories
    }
    
    # Output JSON to stdout
    json.dump(output, sys.stdout, indent=2)
    
    print(f"\nCollection complete. Total size: {get_human_readable_size(total_bytes)}", file=sys.stderr)
    print(f"Directories scanned: {len(directories)}", file=sys.stderr)


if __name__ == '__main__':
    main()
