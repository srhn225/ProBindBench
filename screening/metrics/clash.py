import sys
import os
import numpy as np
from Bio import PDB
from .base import BaseMetric

# Removed dependency on evaluation.clash to avoid import errors
# Inlined necessary logic from evaluation/clash.py

ca_dist = 3.6574 

def get_ca_coordinates(pdb_file, selected_chains):
    parser = PDB.PDBParser(QUIET=True)
    structure = parser.get_structure('protein', pdb_file)
    ca_coordinates = []
    selected_chains_set = set(selected_chains)
    for model in structure:
        for chain in model:
            if chain.id in selected_chains_set:
                for residue in chain:
                    if 'CA' in residue:
                        atom = residue['CA']
                        ca_coordinates.append(atom.coord)
    return np.array(ca_coordinates)

def inner_clash_ratio(ca_coords: np.array):
    if len(ca_coords) == 0: return 0.0
    num_residues = len(ca_coords)
    pair_mask = np.eye(num_residues, num_residues, dtype=bool)
    if num_residues > 1:
        pair_mask[np.arange(num_residues - 1), np.arange(1, num_residues)] = True
        pair_mask[np.arange(1, num_residues), np.arange(num_residues - 1)] = True

    dist = np.linalg.norm(ca_coords[:, None] - ca_coords[None, :], axis=-1) # [N, N]
    
    clash = (dist < ca_dist) & (~pair_mask)
    clash_indices = np.where(clash)
    clash_num_residues = len(np.unique(clash_indices[0]))

    return clash_num_residues / num_residues

def outer_clash_ratio(ca_coords1: np.array, ca_coords2: np.array):
    if len(ca_coords1) == 0 or len(ca_coords2) == 0: return 0.0, 0.0
    dist = np.linalg.norm(ca_coords1[:, None] - ca_coords2[None, :], axis=-1) # [N, M]

    clash = dist < ca_dist
    clash_indices = np.where(clash)
    clash_num_residues1 = len(np.unique(clash_indices[0]))
    clash_num_residues2 = len(np.unique(clash_indices[1]))

    clash_ratio1 = clash_num_residues1 / len(ca_coords1)
    clash_ratio2 = clash_num_residues2 / len(ca_coords2)

    return clash_ratio1, clash_ratio2

class ClashInner(BaseMetric):
    @property
    def name(self) -> str:
        return "Clash Score (Inner)"

    def calculate(self, pdb_path: str, rec_chains: list, lig_chains: list) -> float:
        try:
            ligand_ca = get_ca_coordinates(pdb_path, lig_chains)
            if len(ligand_ca) == 0: return None
            return inner_clash_ratio(ligand_ca)
        except Exception as e:
            print(f"Error in ClashInner: {e}")
            return None

class ClashOuter(BaseMetric):
    @property
    def name(self) -> str:
        return "Clash Score (Outer)"

    def calculate(self, pdb_path: str, rec_chains: list, lig_chains: list) -> float:
        try:
            rec_ca = get_ca_coordinates(pdb_path, rec_chains)
            lig_ca = get_ca_coordinates(pdb_path, lig_chains)
            if len(rec_ca) == 0 or len(lig_ca) == 0: return None
            # outer_clash_ratio returns (ratio1, ratio2)
            # assume we want ratio relative to ligand (ratio1)
            r1, _ = outer_clash_ratio(lig_ca, rec_ca)
            return r1
        except Exception as e:
            print(f"Error in ClashOuter: {e}")
            return None
