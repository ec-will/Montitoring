#!/usr/bin/env python3
import json, time, os
import subprocess, sys, csv, datetime, shutil
from collections import defaultdict

def run_myusage(args):
    exe = shutil.which("myusage")
    if not exe:
        raise FileNotFoundError("myusage not found")
    p = subprocess.run([exe] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    if p.returncode != 0:
        raise RuntimeError("myusage failed: " + p.stderr)
    return p.stdout

def parse_csv_header(raw):
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        if "," in line and "sabalcore" not in line.lower() and "usage" not in line.lower():
            return lines[i:]
    return []

def parse_csv(raw):
    csv_lines = parse_csv_header(raw)
    if not csv_lines:
        return []
    reader = csv.DictReader(csv_lines)
    rows = []
    for row in reader:
        norm = {}
        for k, v in row.items():
            if k:
                norm[k.strip().lower().replace(" ", "_")] = (v or "").strip()
        rows.append(norm)
    return rows

def parse_date(s):
    if not s:
        return None
    formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

def parse_float(s):
    try:
        return float(s.replace(",", ""))
    except:
        return 0.0

def load_pricing():
    """Load pricing configuration from pricing.json"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pricing_file = os.path.join(script_dir, "pricing.json")
    
    try:
        with open(pricing_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: pricing.json not found, using default prices", file=sys.stderr)
        return {
            "compute": {"erthch": 0.0, "red": 0.12, "green": 0.12, "onyx": 0.12, "blue": 0.12},
            "storage": {"per_gb": 0.12},
            "currency": "USD"
        }
    except Exception as e:
        print("Warning: Failed to load pricing.json: %s" % str(e), file=sys.stderr)
        return {"compute": {}, "storage": {"per_gb": 0.12}, "currency": "USD"}

def parse_month_arg(month_str):
    """Parse month argument and return (year, month) tuple"""
    now = datetime.datetime.now()
    month_str = month_str.lower().strip()
    
    # Try numeric month (1-12)
    try:
        month = int(month_str)
        if 1 <= month <= 12:
            # If month is in the future, use previous year
            year = now.year if month <= now.month else now.year - 1
            return year, month
    except ValueError:
        pass
    
    # Try month names/abbreviations
    month_names = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12
    }
    
    if month_str in month_names:
        month = month_names[month_str]
        # If month is in the future, use previous year
        year = now.year if month <= now.month else now.year - 1
        return year, month
    
    raise ValueError("Invalid month: %s" % month_str)

def get_month_jobs(year, month):
    """Get all jobs for a specific month by fetching in 1-day chunks"""
    # Get first and last day of month
    first_day = datetime.datetime(year, month, 1)
    if month == 12:
        last_day = datetime.datetime(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.datetime(year, month + 1, 1) - datetime.timedelta(days=1)
    
    # Generate 1-day chunks (each chunk is start to start+1)
    chunks = []
    current = first_day
    while current <= last_day:
        chunk_end = current + datetime.timedelta(days=1)
        chunks.append((
            current.strftime("%Y-%m-%d"),
            chunk_end.strftime("%Y-%m-%d")
        ))
        current = chunk_end
    
    all_jobs = []
    job_ids = set()  # To avoid duplicates
    
    for start_date, end_date in chunks:
        try:
            raw = run_myusage(["--start", start_date, "--end", end_date, "--count", "2500", "--csv"])
            chunk_jobs = parse_csv(raw)
            
            # Add unique jobs only
            for job in chunk_jobs:
                job_id = job.get("id", "")
                if job_id and job_id not in job_ids:
                    job_ids.add(job_id)
                    all_jobs.append(job)
            
            if len(chunk_jobs) > 0:
                print("  %s to %s: Found %d jobs" % (start_date, end_date, len(chunk_jobs)), file=sys.stderr)
        except Exception as e:
            print("Warning: Failed to fetch %s to %s: %s" % (start_date, end_date, str(e)), file=sys.stderr)
    
    print("Total unique jobs collected: %d" % len(all_jobs), file=sys.stderr)
    return all_jobs

def filter_month(rows, year, month):
    """Filter jobs to specific month"""
    filtered = []
    for r in rows:
        start = r.get("start", "")
        dt = parse_date(start)
        if dt and dt.year == year and dt.month == month:
            filtered.append(r)
    return filtered

def main():
    if len(sys.argv) < 2:
        print("Usage: %s <month>" % sys.argv[0], file=sys.stderr)
        print("Example: %s oct" % sys.argv[0], file=sys.stderr)
        print("         %s 10" % sys.argv[0], file=sys.stderr)
        sys.exit(1)
    
    # Parse month argument
    try:
        year, month = parse_month_arg(sys.argv[1])
    except ValueError as e:
        print("Error: %s" % str(e), file=sys.stderr)
        sys.exit(1)
    
    month_date = datetime.datetime(year, month, 1)
    month_name = month_date.strftime("%B %Y")
    
    # Load pricing configuration
    pricing = load_pricing()
    
    # Prepare CSV output
    csv_writer = csv.writer(sys.stdout)
    
    # Write header
    csv_writer.writerow(["Cluster", "Job Count", "Core Hours", "Cost"])
    
    # Job Usage - get complete month data
    compute_prices = pricing.get("compute", {})
    total_compute_cost = 0.0
    
    try:
        print("Collecting complete %s job data..." % month_name, file=sys.stderr)
        all_jobs = get_month_jobs(year, month)
        current = filter_month(all_jobs, year, month)
        
        if current:
            agg = defaultdict(lambda: {"job_count": 0, "core_hours": 0.0})
            total_core_hours = 0.0
            
            for r in current:
                cluster = r.get("cluster", "UNKNOWN")
                core_hours = parse_float(r.get("core_hours", "0"))
                agg[cluster]["job_count"] += 1
                agg[cluster]["core_hours"] += core_hours
                total_core_hours += core_hours
            
            # Output cluster data
            for cluster, data in sorted(agg.items()):
                price_per_core_hour = compute_prices.get(cluster.lower(), 0.0)
                cost = data["core_hours"] * price_per_core_hour
                total_compute_cost += cost
                
                csv_writer.writerow([cluster, data["job_count"], "%.2f" % data["core_hours"], "%.2f" % cost])
            
            # Write summary
            csv_writer.writerow([])
            csv_writer.writerow(["Total", len(current), "%.2f" % total_core_hours, "%.2f" % total_compute_cost])
            
    except Exception as e:
        print("Error: Failed to retrieve job usage: %s" % str(e), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
