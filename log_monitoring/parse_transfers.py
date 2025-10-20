#!/usr/bin/env python3
"""
Parse transfer log files and generate JSON output for web dashboard.
Groups log entries by PID and extracts transfer details.
"""

import json
import re
import argparse
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional


# Regex patterns for parsing log entries
LOG_PATTERN = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\]: (\d+) (.+)')

# Patterns for extracting details from messages
CALLED_BY_PATTERN = re.compile(r'(\S+) called by: (\S+) with args: (.+)')
TRANSFER_PATTERN = re.compile(r'(\S+) (scp|cp|rsync) (.+)')
SFTP_PATTERN = re.compile(r"(\S+) echo 'put ([^\s]+) ([^']+)' \| sshpass -p \S+ sftp (\S+)")
AZ_STORAGE_PATTERN = re.compile(r'(\S+) az storage blob upload.*--name ([^\s]+).*--file ([^\s]+)')


def parse_message(message: str) -> Dict[str, str]:
    """Extract details from a log message."""
    details = {}
    
    # Check for "called by" pattern
    called_match = CALLED_BY_PATTERN.match(message)
    if called_match:
        details['script'] = called_match.group(1)
        details['caller'] = called_match.group(2)
        details['args'] = called_match.group(3)
        return details
    
    # Check for SFTP pattern
    sftp_match = SFTP_PATTERN.match(message)
    if sftp_match:
        details['script'] = sftp_match.group(1)
        details['method'] = 'sftp'
        details['file'] = sftp_match.group(2)
        details['destination'] = sftp_match.group(3) + ' (' + sftp_match.group(4) + ')'
        return details
    
    # Check for az storage pattern first
    az_match = AZ_STORAGE_PATTERN.match(message)
    if az_match:
        details['script'] = az_match.group(1)
        details['method'] = 'az storage'
        details['destination'] = az_match.group(2)  # --name parameter
        details['file'] = az_match.group(3)  # --file parameter
        return details
    
    # Check for transfer pattern
    transfer_match = TRANSFER_PATTERN.match(message)
    if transfer_match:
        details['script'] = transfer_match.group(1)
        details['method'] = transfer_match.group(2)
        transfer_args = transfer_match.group(3)
        
        # Parse transfer arguments
        if details['method'] == 'scp':
            # Format: filename destination
            parts = transfer_args.split(' ')
            if len(parts) >= 2:
                details['file'] = parts[0]
                details['destination'] = parts[1]
        elif details['method'] == 'cp':
            # Format: source dest
            parts = transfer_args.split(' ')
            if len(parts) >= 2:
                details['file'] = parts[0]
                details['destination'] = parts[1]
    
    return details


def parse_log_file(file_path: str) -> List[Dict]:
    """Parse the transfer log file and return grouped sessions."""
    sessions = defaultdict(list)
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                match = LOG_PATTERN.match(line)
                if not match:
                    continue
                
                timestamp, log_type, pid, message = match.groups()
                
                # Parse message details
                details = parse_message(message)
                
                # Create log entry
                entry = {
                    'timestamp': timestamp,
                    'log_type': log_type,
                    'message': message,
                    **details
                }
                
                sessions[pid].append(entry)
    
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        return []
    except Exception as e:
        print(f"Error reading file: {e}")
        return []
    
    # Convert to list of session objects
    result = []
    for pid, entries in sessions.items():
        # Sort entries by timestamp
        entries.sort(key=lambda x: x['timestamp'])
        
        session = {
            'pid': int(pid),
            'entries': entries,
            'entry_count': len(entries)
        }
        result.append(session)
    
    # Sort sessions by PID
    result.sort(key=lambda x: x['pid'])
    
    return result


def main():
    parser = argparse.ArgumentParser(description='Parse transfer log and generate JSON')
    parser.add_argument('-i', '--input', default='transfer.log', 
                       help='Input log file (default: transfer.log)')
    parser.add_argument('-o', '--output', default='transfers.json',
                       help='Output JSON file (default: transfers.json)')
    parser.add_argument('--summary', action='store_true',
                       help='Print summary statistics')
    
    args = parser.parse_args()
    
    # Parse the log file
    sessions = parse_log_file(args.input)
    
    if args.summary:
        total_entries = sum(session['entry_count'] for session in sessions)
        print(f"Parsed {total_entries} log entries into {len(sessions)} sessions")
        
        # Print session breakdown
        for session in sessions:
            print(f"  PID {session['pid']}: {session['entry_count']} entries")
    
    # Write JSON output
    try:
        with open(args.output, 'w') as f:
            json.dump(sessions, f, indent=2)
        print(f"JSON output written to {args.output}")
    except Exception as e:
        print(f"Error writing output file: {e}")


if __name__ == '__main__':
    main()