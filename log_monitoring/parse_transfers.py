#!/usr/bin/env python3
"""
Parse transfer log files and generate JSON output for web dashboard.
Groups log entries by PID and extracts transfer details.
"""

import json
import re
import argparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Optional


# Regex patterns for parsing log entries
LOG_PATTERN = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\]: (\d+) (.+)')

# Patterns for extracting details from messages
CALLED_BY_PATTERN = re.compile(r'(\S+) called by: (\S+) with args: (.+)')
TRANSFER_PATTERN = re.compile(r'(\S+) (scp|cp|rsync) (.+)')
SFTP_PATTERN = re.compile(r"(\S+) echo 'put ([^\s]+) ([^']+)' \| sshpass -p \S+ sftp (\S+)")
AZ_STORAGE_PATTERN = re.compile(r'(\S+) az storage blob upload.*--name ([^\s]+).*--file ([^\s]+)')
RSYNC_PATTERN = re.compile(r'(\S+) rsync .*?([^\s/]+\.\w+) (\S+::\S+)/?$')
LFTP_PATTERN = re.compile(r'(\S+) lftp -u (\S+) sftp://(\S+) mput (\S+) (\S+)')


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
        # Extract destination without filename (remove anything after last /)
        sftp_dest = sftp_match.group(3)
        if '/' in sftp_dest:
            sftp_dest = sftp_dest.rsplit('/', 1)[0] + '/'
        details['destination'] = sftp_dest + ' (' + sftp_match.group(4) + ')'
        return details
    
    # Check for specific rsync pattern (before generic transfer pattern)
    rsync_match = RSYNC_PATTERN.match(message)
    if rsync_match:
        details['script'] = rsync_match.group(1)
        details['method'] = 'rsync'
        details['file'] = rsync_match.group(2)
        details['destination'] = rsync_match.group(3)
        return details
    
    # Check for lftp pattern
    lftp_match = LFTP_PATTERN.match(message)
    if lftp_match:
        details['script'] = lftp_match.group(1)
        details['method'] = 'lftp'
        details['file'] = lftp_match.group(4).rsplit('/', 1)[-1]
        details['destination'] = lftp_match.group(2).split(',')[0] + '@' + lftp_match.group(3) + ':' + lftp_match.group(5)
        return details

    # Check for az storage pattern first
    az_match = AZ_STORAGE_PATTERN.match(message)
    if az_match:
        details['script'] = az_match.group(1)
        details['method'] = 'az storage'
        # Extract container name from the message
        # Look for --container-name parameter
        container_match = re.search(r'--container-name\s+(\S+)', message)
        if container_match:
            details['destination'] = 'Azure: ' + container_match.group(1)
        else:
            details['destination'] = 'Azure Storage'
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
                # Extract destination without filename (remove anything after last /)
                dest = parts[1]
                # For scp, destination is user@host:path, keep everything
                details['destination'] = dest
        elif details['method'] == 'cp':
            # Format: source dest
            parts = transfer_args.split(' ')
            if len(parts) >= 2:
                details['file'] = parts[0]
                details['destination'] = parts[1]
        elif details['method'] == 'rsync':
            # Generic rsync parsing for other formats
            parts = transfer_args.split(' ')
            if len(parts) >= 2:
                # Take last two arguments as source and destination
                details['file'] = parts[-2]
                dest = parts[-1]
                # For rsync, destination is module::path - keep up to last /
                if '::' in dest:
                    # Remove filename after the last /
                    dest = dest.rsplit('/', 1)[0] + '/'
                details['destination'] = dest
    
    return details


def parse_log_file(file_path: str, hours: int = 0) -> List[Dict]:
    """Parse the transfer log file and return grouped sessions.
    
    If hours > 0, only sessions with at least one entry in the last N hours
    are included in the output.
    """
    sessions = defaultdict(list)
    cutoff = None
    if hours > 0:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    
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

        # Apply time window filter: skip sessions with no entries in the window
        if cutoff is not None:
            newest = entries[-1]['timestamp']  # already sorted ascending
            try:
                newest_dt = datetime.strptime(newest, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                newest_dt = cutoff  # keep if unparseable
            if newest_dt < cutoff:
                continue

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
    parser.add_argument('--hours', type=int, default=0,
                       help='Only include sessions with entries in the last N hours (0 = no limit)')
    
    args = parser.parse_args()
    
    # Parse the log file
    sessions = parse_log_file(args.input, hours=args.hours)
    
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