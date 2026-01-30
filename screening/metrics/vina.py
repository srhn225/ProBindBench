import sys
import os
import tempfile
import subprocess
import logging
from typing import List, Optional
from .base import BaseMetric

# Helper functions adapted from the user-provided script
def extract_chains_to_pdb(input_pdb: str, output_pdb: str, chain_ids: List[str]):
    chain_set = set(chain_ids)
    with open(input_pdb, 'r') as f_in, open(output_pdb, 'w') as f_out:
        for line in f_in:
            if line.startswith('ATOM') or line.startswith('HETATM'):
                # PDB format: Chain ID is at column 21 (0-indexed)
                if len(line) > 21 and line[21] in chain_set:
                    f_out.write(line)
            elif line.startswith('TER'):
                if len(line) > 21 and line[21] in chain_set:
                    f_out.write(line)
            elif line.startswith('END'):
                f_out.write(line)

def prepare_receptor_pdbqt(pdb_file: str, output_pdbqt: str):
    # Use obabel to convert PDB to PDBQT (rigid)
    # -xr: Output as a rigid molecule
    cmd = ["obabel", "-ipdb", pdb_file, "-opdbqt", "-O", output_pdbqt, "-xr"]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def prepare_ligand_pdbqt(sdf_file: str, output_pdbqt: str):
    # Use obabel to convert SDF to PDBQT
    # -xr: Output as rigid to avoid "BRANCH" parsing errors in Vina with complex topologies
    cmd = ["obabel", "-isdf", sdf_file, "-opdbqt", "-O", output_pdbqt]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def run_vina_local(rec_pdbqt: str, lig_pdbqt: str) -> Optional[float]:
    # vina --receptor rec.pdbqt --ligand lig.pdbqt --autobox --local_only
    cmd = ["vina", "--receptor", rec_pdbqt, "--ligand", lig_pdbqt, "--autobox", "--local_only"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Vina failed: {result.stderr}")
            return None
        
        # Parse score
        # Look for "Affinity: -XXX (kcal/mol)" or "Estimated Free Energy of Binding"
        score = None
        for line in result.stdout.splitlines():
            if line.strip().startswith("Affinity:"):
                # Example: Affinity: -6.43567 (kcal/mol)
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        score = float(parts[1])
                        break
                    except ValueError: pass
            elif line.strip().startswith("Estimated Free Energy of Binding"):
                parts = line.split(":")
                if len(parts) >= 2:
                    val_str = parts[1].strip().split()[0]
                    try:
                        score = float(val_str)
                        break
                    except ValueError: pass
        return score
    except Exception as e:
        print(f"Vina execution error: {e}")
        return None

class VinaScore(BaseMetric):
    @property
    def name(self) -> str:
        return "Vina Score (Local)"

    def calculate(self, pdb_path: str, rec_chains: list, lig_chains: list) -> float:
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                rec_pdb = os.path.join(tmpdir, 'receptor.pdb')
                lig_pdb = os.path.join(tmpdir, 'ligand.pdb')
                lig_sdf = os.path.join(tmpdir, 'ligand.sdf')
                rec_pdbqt = os.path.join(tmpdir, 'receptor.pdbqt')
                lig_pdbqt = os.path.join(tmpdir, 'ligand.pdbqt')

                # 1. Extract Chains
                extract_chains_to_pdb(pdb_path, rec_pdb, rec_chains)
                extract_chains_to_pdb(pdb_path, lig_pdb, lig_chains)
                
                # Check if extracted files are not empty
                if os.path.getsize(rec_pdb) == 0:
                    print(f"Error: No atoms found for receptor chains {rec_chains}")
                    return None
                if os.path.getsize(lig_pdb) == 0:
                    print(f"Error: No atoms found for ligand chains {lig_chains}")
                    return None

                # 2. Prepare Receptor (PDB -> PDBQT)
                prepare_receptor_pdbqt(rec_pdb, rec_pdbqt)

                # 3. Prepare Ligand (PDB -> SDF -> PDBQT)
                # Convert PDB to SDF using obabel first (to match flow utilizing SDF)
                # Using subprocess for this too to be consistent
                cmd_sdf = ["obabel", "-ipdb", lig_pdb, "-osdf", "-O", lig_sdf]
                subprocess.run(cmd_sdf, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                prepare_ligand_pdbqt(lig_sdf, lig_pdbqt)

                # 4. Run Vina
                return run_vina_local(rec_pdbqt, lig_pdbqt)

            except subprocess.CalledProcessError as e:
                print(f"Subprocess failed: {e}")
                return None
            except Exception as e:
                print(f"Error in VinaScore: {e}")
                return None

if __name__ == "__main__":
    import argparse
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description="Debug VinaScore calculation")
    parser.add_argument("pdb_path", type=str, help="Path to the complex PDB file")
    parser.add_argument("--rec_chains", nargs='+', required=True, help="List of receptor chain IDs (e.g. A B)")
    parser.add_argument("--lig_chains", nargs='+', required=True, help="List of ligand chain IDs (e.g. C)")

    args = parser.parse_args()

    if not os.path.exists(args.pdb_path):
        print(f"Error: File {args.pdb_path} not found.")
        sys.exit(1)

    print(f"Running VinaScore on {args.pdb_path}")
    print(f"Receptor Chains: {args.rec_chains}")
    print(f"Ligand Chains: {args.lig_chains}")

    metric = VinaScore()
    try:
        score = metric.calculate(args.pdb_path, args.rec_chains, args.lig_chains)
        print("-" * 30)
        print(f"Vina Score: {score}")
        print("-" * 30)
    except Exception as e:
        print(f"An error occurred during execution: {e}")

