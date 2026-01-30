from .base import BaseMetric
from .foldx import FoldXEnergy
from .rosetta import RosettaEnergy
from .clash import ClashInner, ClashOuter
from .vina import VinaScore

AVAILABLE_METRICS = {
    'foldx': FoldXEnergy,
    'rosetta': RosettaEnergy,
    'vina': VinaScore,
    'clash_inner': ClashInner,
    'clash_outer': ClashOuter
}

def get_metric(name: str) -> BaseMetric:
    return AVAILABLE_METRICS[name]()
