import sys
import os
from .base import BaseMetric

# Add project root to sys.path to allow importing from evaluation
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from evaluation.foldx_energy import foldx_dg
except ImportError:
    # Fallback or stub if environment is not perfect, but usually this should work
    def foldx_dg(*args, **kwargs):
        raise ImportError("Could not import evaluation.foldx_energy")

class FoldXEnergy(BaseMetric):
    @property
    def name(self) -> str:
        return "FoldX Energy"

    def calculate(self, pdb_path: str, rec_chains: list, lig_chains: list) -> float:
        # foldx_dg(pdb_path, rec_chains, lig_chains, cyclic_chains=None)
        # Note: foldx_dg returns affinity
        try:
            return foldx_dg(pdb_path, rec_chains=rec_chains, lig_chains=lig_chains)
        except Exception as e:
            print(f"Error in FoldX calc: {e}")
            return None
