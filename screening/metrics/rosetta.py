import sys
import os
from .base import BaseMetric

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from evaluation.energy import pyrosetta_interface_energy
except ImportError:
    def pyrosetta_interface_energy(*args, **kwargs):
        raise ImportError("Could not import evaluation.energy")

class RosettaEnergy(BaseMetric):
    @property
    def name(self) -> str:
        return "Rosetta Interface Energy"

    def calculate(self, pdb_path: str, rec_chains: list, lig_chains: list) -> float:
        # pyrosetta_interface_energy(pdb_path, receptor_chains, ligand_chains, ...)
        try:
            return pyrosetta_interface_energy(pdb_path, receptor_chains=rec_chains, ligand_chains=lig_chains,relax=True)
        except Exception as e:
            print(f"Error in Rosetta calc: {e}")
            return None
