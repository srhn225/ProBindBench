from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseMetric(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def calculate(self, pdb_path: str, rec_chains: List[str], lig_chains: List[str]) -> float:
        """
        Calculate the metric for a given PDB file and chains.
        """
        pass
