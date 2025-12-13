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

def get_all_current_month_jobs():
    """Get all jobs for the current month by fetching in 1-day chunks"""
    now = datetime.datetime.now()
    year = now.year
    month = now.month
    
    # Get first and last day of current month
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

def filter_current_month(rows):
    now = datetime.datetime.now()
    filtered = []
    for r in rows:
        start = r.get("start", "")
        dt = parse_date(start)
        if dt and dt.year == now.year and dt.month == now.month:
            filtered.append(r)
    return filtered

def main():
    now = datetime.datetime.now()
    month_name = now.strftime("%B %Y")
    
    # Load pricing configuration
    pricing = load_pricing()
    
    output = {
        "metadata": {
            "generator": "usage_report_json.py", 
            "version": "1.2",
            "generated_at": int(time.time()),
            "generated_time": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "description": "Complete disk and job usage report with cost calculations",
            "currency": pricing.get("currency", "USD")
        },
        "disk_usage": [],
        "job_usage": {
            "clusters": {},
            "summary": {}
        }
    }
    
    # Disk Usage
    storage_price_per_gb = pricing.get("storage", {}).get("per_gb", 0.12)
    total_storage_cost = 0.0
    
    try:
        sraw = run_myusage(["--storage", "--csv"])
        srows = parse_csv(sraw)
        for r in srows:
            path = r.get("path", "unknown")
            bytes_used = parse_float(r.get("bytes", "0"))
            files = int(parse_float(r.get("files", "0")))
            gigabytes = bytes_used / (1024**3)
            cost = gigabytes * storage_price_per_gb
            total_storage_cost += cost
            
            output["disk_usage"].append({
                "path": path,
                "bytes": int(bytes_used),
                "gigabytes": round(gigabytes, 2),
                "files": files,
                "cost": round(cost, 2)
            })
    except Exception as e:
        print("Warning: Failed to retrieve disk usage: %s" % str(e), file=sys.stderr)
    
    # Job Usage - get complete current month data
    compute_prices = pricing.get("compute", {})
    total_compute_cost = 0.0
    
    try:
        print("Collecting complete %s job data..." % month_name, file=sys.stderr)
        all_jobs = get_all_current_month_jobs()
        current = filter_current_month(all_jobs)
        
        if current:
            agg = defaultdict(lambda: {"job_count": 0, "core_hours": 0.0})
            total_core_hours = 0.0
            
            for r in current:
                cluster = r.get("cluster", "UNKNOWN")
                core_hours = parse_float(r.get("core_hours", "0"))
                agg[cluster]["job_count"] += 1
                agg[cluster]["core_hours"] += core_hours
                total_core_hours += core_hours
            
            # Convert to regular dict and calculate costs
            for cluster, data in agg.items():
                # Get price for this cluster (default to 0 if not found)
                price_per_core_hour = compute_prices.get(cluster.lower(), 0.0)
                cost = data["core_hours"] * price_per_core_hour
                total_compute_cost += cost
                
                output["job_usage"]["clusters"][cluster] = {
                    "job_count": data["job_count"],
                    "core_hours": round(data["core_hours"], 2),
                    "cost": round(cost, 2)
                }
            
            output["job_usage"]["summary"] = {
                "total_jobs": len(current),
                "total_core_hours": round(total_core_hours, 2),
                "total_cost": round(total_compute_cost, 2),
                "unique_clusters": len(agg),
                "collection_period": month_name
            }
            
    except Exception as e:
        print("Error: Failed to retrieve job usage: %s" % str(e), file=sys.stderr)
        sys.exit(1)
    
    # Add overall cost summary
    output["metadata"]["total_cost"] = round(total_compute_cost + total_storage_cost, 2)
    output["metadata"]["compute_cost"] = round(total_compute_cost, 2)
    output["metadata"]["storage_cost"] = round(total_storage_cost, 2)
    
    # Output JSON
    print(json.dumps(output, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()