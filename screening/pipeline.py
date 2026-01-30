import os
import re
import json
import time
import shutil
import uuid
import zipfile
import concurrent.futures
from typing import List, Dict, Optional
from screening.metrics import get_metric, AVAILABLE_METRICS

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WORKSPACE_DIR, 'data')
UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads')
DB_FILE = os.path.join(DATA_DIR, 'db.json')

os.makedirs(UPLOADS_DIR, exist_ok=True)

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r') as f:
        try:
            return json.load(f)
        except:
            return []

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_job_from_db(job_id):
    db = load_db()
    for job in db:
        if job['id'] == job_id:
            return job
    return None

def update_job_in_db(updated_job):
    db = load_db()
    found = False
    for i, job in enumerate(db):
        if job['id'] == updated_job['id']:
            db[i] = updated_job
            found = True
            break
    if not found:
        db.append(updated_job)
    save_db(db)

def parse_chains(chain_str):
    if not chain_str: return []
    # If using separators, split by them
    if ',' in chain_str or ' ' in chain_str:
         return [c for c in re.split(r'[ ,]+', chain_str) if c]
    # Otherwise treat as list of chars (e.g. "AB" -> ["A", "B"])
    return list(chain_str)

class Pipeline:
    def __init__(self):

        self.metrics = AVAILABLE_METRICS.keys()

    def list_metrics(self):
        return list(self.metrics)

    def create_job(self, files: List, rec_chain: str, lig_chain: str):
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(UPLOADS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)

        for file_obj in files:
            filename = file_obj.filename
            dest = os.path.join(job_dir, filename)
            with open(dest, 'wb') as f:
                shutil.copyfileobj(file_obj.file, f)
            
            # Unzip if needed
            if filename.endswith('.zip'):
                try:
                    with zipfile.ZipFile(dest, 'r') as zip_ref:
                        zip_ref.extractall(job_dir)
                    os.remove(dest) # Remove zip after extraction
                except Exception as e:
                    print(f"Error unzipping {filename}: {e}")
            else:
                pass
        
        return self._finalize_job_creation(job_id, job_dir, rec_chain, lig_chain)

    def create_job_from_files(self, file_paths: List[str], rec_chain: str, lig_chain: str, name_prefix: str = ""):
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(UPLOADS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        for src in file_paths:
            if os.path.exists(src) and os.path.isfile(src):
                shutil.copy(src, job_dir)
        
        return self._finalize_job_creation(job_id, job_dir, rec_chain, lig_chain, name_prefix)

    def _finalize_job_creation(self, job_id, job_dir, rec_chain, lig_chain, name_prefix=""):
        # Scan dir for all PDBs
        all_files = []
        for root, dirs, files in os.walk(job_dir):
            for f in files:
                if f.endswith('.pdb'):
                    # relative path to job_dir
                    rel_path = os.path.relpath(os.path.join(root, f), job_dir)
                    all_files.append(rel_path)

        # Create Job Record
        files_dict = {}
        for f in all_files:
            files_dict[f] = {
                "status": "pending", # pending, active(done), filtered
                "scores": {} 
            }
        
        name = job_id[:8]
        if name_prefix:
            name = f"{name_prefix}_{name}"

        job_record = {
            "id": job_id,
            "name": name,
            "timestamp": time.time(),
            "rec_chain": rec_chain,
            "lig_chain": lig_chain,
            "files": files_dict,
            "history": [] # Log of actions
        }
        
        update_job_in_db(job_record)
        return job_record

    def rename_job(self, job_id: str, new_name: str):
        job = get_job_from_db(job_id)
        if not job:
            return False
        job['name'] = new_name
        update_job_in_db(job)
        return True

    def delete_job(self, job_id: str):
        db = load_db()
        new_db = [j for j in db if j['id'] != job_id]
        if len(new_db) == len(db):
            return False
        save_db(new_db)
        
        job_dir = os.path.join(UPLOADS_DIR, job_id)
        if os.path.exists(job_dir):
            try:
                shutil.rmtree(job_dir)
            except Exception as e:
                print(f"Error deleting job dir {job_dir}: {e}")
        return True

    def _calculate_single_file(self, job_dir, fname, rec_chains, lig_chains, active_metric_map):
        fpath = os.path.join(job_dir, fname)
        results = {}
        for m_key, metric in active_metric_map.items():
            try:
                # Logic: if score exists, overwrite or skip? 
                # User requested "Run", so we overwrite.
                score = metric.calculate(fpath, rec_chains, lig_chains)
                # Convert float32/64 to float for JSON serialization
                if hasattr(score, 'item'): score = score.item()
                results[m_key] = score
            except Exception as e:
                print(f"Error running {m_key} on {fname}: {e}")
                results[m_key] = None
        return fname, results

    def run_analysis(self, job_id: str, filenames: List[str], metrics: List[str], rec_chain: str = None, lig_chain: str = None, num_threads: int = 20):
        job = get_job_from_db(job_id)
        if not job:
            return None
        
        # Update chains if provided
        if rec_chain: job['rec_chain'] = rec_chain
        if lig_chain: job['lig_chain'] = lig_chain
        
        rec_chains_list = parse_chains(job.get('rec_chain', ''))
        lig_chains_list = parse_chains(job.get('lig_chain', ''))
        
        job_dir = os.path.join(UPLOADS_DIR, job_id)
        
        # Initialize metric calculators
        active_metric_map = {}
        for m_name in metrics:
            if m_name in AVAILABLE_METRICS:
                active_metric_map[m_name] = get_metric(m_name)

        # Run with ThreadPoolExecutor
        tasks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            for fname in filenames:
                if fname not in job['files']:
                    continue
                # Ensure scores dict exists (pre-allocation, though update handles it too)
                if 'scores' not in job['files'][fname]:
                    job['files'][fname]['scores'] = {}

                future = executor.submit(
                    self._calculate_single_file, 
                    job_dir, 
                    fname, 
                    rec_chains_list, 
                    lig_chains_list, 
                    active_metric_map
                )
                tasks.append(future)

            for future in concurrent.futures.as_completed(tasks):
                fname, results = future.result()
                
                job['files'][fname]['scores'].update(results)
                
                # If at least one metric run, set to active if it was pending
                if job['files'][fname]['status'] == 'pending':
                     job['files'][fname]['status'] = 'active'


        # Update History
        action_log = {
            "timestamp": time.time(),
            "action": "run_analysis",
            "files_count": len(filenames),
            "metrics": metrics
        }
        if "history" not in job: job["history"] = []
        job["history"].append(action_log)

        update_job_in_db(job)
        return job
    
    def update_job_files_status(self, job_id: str, updates: Dict[str, str]):
        # updates: {filename: new_status}
        job = get_job_from_db(job_id)
        if not job: return None
        
        for fname, status in updates.items():
            if fname in job['files']:
                job['files'][fname]['status'] = status
        
        update_job_in_db(job)
        return job

    def get_job(self, job_id):
        job = get_job_from_db(job_id)
        if job and 'files' not in job and 'results' in job:
            # On-the-fly migration for legacy jobs
            files_dict = {}
            for res in job['results']:
                fname = res.get('filename', 'unknown')
                files_dict[fname] = {
                    "status": "active",
                    "scores": res.get("scores", {})
                }
            job['files'] = files_dict
        return job

    def get_history(self):
        db = load_db()
        # Summary for history list
        summary = []
        for job in sorted(db, key=lambda x: x.get('timestamp', 0), reverse=True):
            file_count = 0
            if 'files' in job:
                file_count = len(job['files'])
            elif 'results' in job:
                file_count = len(job['results'])
            
            summary.append({
                "id": job['id'],
                "name": job.get('name', job['id'][:8]),
                "timestamp": job.get('timestamp', 0),
                "file_count": file_count,
                "rec_chain": job.get('rec_chain'),
                "lig_chain": job.get('lig_chain')
            })
        return summary
