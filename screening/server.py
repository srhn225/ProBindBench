import zipfile
import tempfile
import yaml
import subprocess
import threading
import glob
from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from typing import List, Dict, Optional
from pydantic import BaseModel
import uvicorn
import os
import json
import sys

# Allow running directly from file or as module
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "screening"

from screening.pipeline import Pipeline, UPLOADS_DIR

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIMOMO_DIR = os.path.join(WORKSPACE_ROOT, 'unimomo')

app = FastAPI()
pipeline = Pipeline()

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def read_index():
    with open(os.path.join(static_dir, "index.html")) as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/api/metrics")
def get_metrics():
    return {"metrics": pipeline.list_metrics()}

@app.get("/api/history")
def get_history():
    return pipeline.get_history()

@app.post("/api/jobs")
def create_job(
    rec_chain: str = Form(...),
    lig_chain: str = Form(...),
    files: List[UploadFile] = File(...)
):
    return pipeline.create_job(files, rec_chain, lig_chain)

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = pipeline.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/jobs/{job_id}/files/{filename:path}")
def get_job_file(job_id: str, filename: str):
    # Security check: ensure filename doesn't contain ..
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = os.path.join(UPLOADS_DIR, job_id, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path, filename=os.path.basename(filename))

class RunRequest(BaseModel):
    files: List[str]
    metrics: List[str]
    rec_chain: Optional[str] = None
    lig_chain: Optional[str] = None
    num_threads: int = 4

@app.post("/api/jobs/{job_id}/run")
def run_job(job_id: str, req: RunRequest):
    job = pipeline.run_analysis(
        job_id, 
        req.files, 
        req.metrics, 
        req.rec_chain, 
        req.lig_chain,
        num_threads=req.num_threads
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

class UpdateStatusRequest(BaseModel):
    updates: Dict[str, str] # {filename: status}

@app.post("/api/jobs/{job_id}/status")
def update_status(job_id: str, req: UpdateStatusRequest):
    job = pipeline.update_job_files_status(job_id, req.updates)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

class RenameRequest(BaseModel):
    name: str

@app.post("/api/jobs/{job_id}/rename")
def rename_job(job_id: str, req: RenameRequest):
    success = pipeline.rename_job(job_id, req.name)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "success", "id": job_id, "name": req.name}

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    success = pipeline.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "success", "id": job_id}

class DownloadRequest(BaseModel):
    files: List[str]

class OptimizeRequest(BaseModel):
    optimize_step: int = 16
    batch_size: int = 50
    n_samples: int = 100

def run_optimization_task(job_id: str, filename: str, req: OptimizeRequest):
    # 1. Setup paths
    job_dir = os.path.join(UPLOADS_DIR, job_id)
    input_pdb = os.path.join(job_dir, filename)
    if not os.path.exists(input_pdb):
        print(f"Error: Input PDB {input_pdb} not found")
        return

    job = pipeline.get_job(job_id)
    if not job:
        print(f"Error: Job {job_id} not found")
        return

    run_id = f"opt_{os.urandom(4).hex()}"
    output_dir = os.path.join(WORKSPACE_ROOT, "results", run_id)
    os.makedirs(output_dir, exist_ok=True)
    
    config_path = os.path.join(output_dir, "config.yaml")
    
    # 2. Generate Config
    config_data = {
        "dataset": {
            "pdb_paths": [os.path.abspath(input_pdb)],
            "tgt_chains": [job.get('rec_chain', 'A').replace(',', '').replace(' ', '')], 
            "lig_chains": [job.get('lig_chain', 'B').replace(',', '').replace(' ', '')]
        },
        "templates": [{"class": "OptimizePeptide"}],
        "sample_opt": {
            "optimize_step": req.optimize_step
        },
        "batch_size": req.batch_size,
        "n_samples": req.n_samples
    }
    
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f)
        
    # 3. Prepare Command
    ckpt_path = os.path.join(UNIMOMO_DIR, "ckpts", "unimomo.ckpt")
    
    cmd = [
        sys.executable, "-m", "api.optimize",
        "--config", config_path,
        "--confidence_ckpt", ckpt_path,
        "--save_dir", output_dir,
        "--gpu", "0"
    ]
    
    print(f"Starting optimization: {' '.join(cmd)}")
    print(f"CWD: {UNIMOMO_DIR}")

    # 4. Run
    try:
        process = subprocess.Popen(
            cmd, 
            cwd=UNIMOMO_DIR, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream output to server stdout (visible in terminal)
        for line in process.stdout:
            print(f"[OPT-{run_id}] {line}", end='')
            
        process.wait()
        
        if process.returncode == 0:
            print(f"Optimization finished successfully. Collecting results...")
            
            # 5. Collect Results
            created_files = []
            for root, dirs, files in os.walk(output_dir):
                for f in files:
                    if f.endswith('.pdb'):
                         created_files.append(os.path.join(root, f))
            
            if created_files:
                new_job = pipeline.create_job_from_files(
                    created_files, 
                    job.get('rec_chain'), 
                    job.get('lig_chain'), 
                    name_prefix=f"OPT_{filename}"
                )
                print(f"Created new job: {new_job['id']}")
            else:
                print("No PDB files generated.")
        else:
            print(f"Optimization failed with return code {process.returncode}")

    except Exception as e:
        print(f"Exception during optimization: {e}")

@app.post("/api/jobs/{job_id}/optimize/{filename:path}")
def start_optimize(job_id: str, filename: str, req: OptimizeRequest, background_tasks: BackgroundTasks):
    # Security check on filename
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    job = pipeline.get_job(job_id)
    if not job:
          raise HTTPException(status_code=404, detail="Job not found")
    
    background_tasks.add_task(run_optimization_task, job_id, filename, req)
    return {"status": "started", "message": "Optimization started in background check terminal for progress"}

@app.post("/api/jobs/{job_id}/download_batch")
def download_batch_files(job_id: str, req: DownloadRequest):
    job = pipeline.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_dir = os.path.join(UPLOADS_DIR, job_id)
    
    # Create a temporary file for the zip
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    zip_path = tmp.name
    tmp.close()
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fname in req.files:
                # Security check
                if ".." in fname or fname.startswith("/"):
                    continue
                
                # Check if file belongs to this job
                # (Optional: pipeline.py stores valid files, checking job['files'] ensures validity)
                if fname not in job['files']:
                    continue

                full_path = os.path.join(job_dir, fname)
                if os.path.exists(full_path):
                    zf.write(full_path, arcname=fname)
        
        def cleanup():
            if os.path.exists(zip_path):
                os.remove(zip_path)

        return FileResponse(zip_path, filename="batch_download.zip", background=BackgroundTasks(tasks=[cleanup]))
        
    except Exception as e:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise HTTPException(status_code=500, detail=str(e))

def start_server():

    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    start_server()
