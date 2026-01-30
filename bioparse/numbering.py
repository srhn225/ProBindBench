#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
from typing import List, Tuple, Dict


class Chothia:
    # heavy chain
    HFR1 = (1, 25)
    HFR2 = (33, 51)
    HFR3 = (57, 94)
    HFR4 = (103, 113)

    H1 = (26, 32)
    H2 = (52, 56)
    H3 = (95, 102)

    # light chain
    LFR1 = (1, 23)
    LFR2 = (35, 49)
    LFR3 = (57, 88)
    LFR4 = (98, 107)

    L1 = (24, 34)
    L2 = (50, 56)
    L3 = (89, 97)

    INSERTION = {
        'H1': [31],
        'H2': [52],
        'HFR3': [82],
        'H3': [100],
        'L1': [30],
        'L3': [95],
        'LFR4': [106]
    }

    @classmethod
    def mark_heavy_seq(cls, pos: List[int]):
        mark = ''
        for p in pos:
            if p < cls.HFR1[0] or p > cls.HFR4[1]: mark += 'X'
            elif cls.H1[0] <= p and p <= cls.H1[1]: mark += '1'
            elif cls.H2[0] <= p and p <= cls.H2[1]: mark += '2'
            elif cls.H3[0] <= p and p <= cls.H3[1]: mark += '3'
            else: mark += '0'
        return mark
    
    @classmethod
    def mark_light_seq(cls, pos: List[int]):
        mark = ''
        for p in pos:
            if p < cls.LFR1[0] or p > cls.LFR4[1]: mark += 'X'
            elif cls.L1[0] <= p and p <= cls.L1[1]: mark += '1'
            elif cls.L2[0] <= p and p <= cls.L2[1]: mark += '2'
            elif cls.L3[0] <= p and p <= cls.L3[1]: mark += '3'
            else: mark += '0'
        return mark


from typing import List, Dict, Tuple

class IMGT:
    """
    IMGT numbering (V-domain) region definitions.

    Keeps the SAME interface/style as your Chothia class:
      - HFR1..HFR4, H1..H3
      - LFR1..LFR4, L1..L3
      - INSERTION dict
      - mark_heavy_seq / mark_light_seq

    Marking convention:
      - 'X': outside V-domain range (before FR1 or after FR4)
      - '0': framework (FR)
      - '1': CDR1
      - '2': CDR2
      - '3': CDR3
    """

    # -------------------------
    # heavy chain (IMGT V-domain coordinates)
    # -------------------------
    HFR1 = (1, 26)
    HFR2 = (39, 55)
    HFR3 = (66, 104)
    HFR4 = (118, 129)

    H1 = (27, 38)     # CDR1
    H2 = (56, 65)     # CDR2
    H3 = (105, 117)   # CDR3

    # -------------------------
    # light chain (same IMGT coordinates)
    # -------------------------
    LFR1 = (1, 26)
    LFR2 = (39, 55)
    LFR3 = (66, 104)
    LFR4 = (118, 129)

    L1 = (27, 38)     # CDR1
    L2 = (56, 65)     # CDR2
    L3 = (105, 117)   # CDR3

    # IMGT typically avoids "Chothia-style" insertion positions (e.g., 30A/30B).
    # ANARCI may still carry insertion codes in edge cases, but if your `pos` is List[int],
    # there is no place to represent those; keep empty by default.
    INSERTION: Dict[str, List[int]] = {
        'H1': [33], 'H2': [60], 'H3': [111],
        'L1': [33], 'L2': [60], 'L3': [111],
        'HFR2': [47], 'LFR2': [47],
        'HFR3': [85], 'LFR3': [85]
    }

    @classmethod
    def _in_range(cls, p: int, seg: Tuple[int, int]) -> bool:
        return seg[0] <= p <= seg[1]

    @classmethod
    def mark_heavy_seq(cls, pos: List[int]) -> str:
        mark = ''
        for p in pos:
            if p < cls.HFR1[0] or p > cls.HFR4[1]:
                mark += 'X'
            elif cls.H1[0] <= p <= cls.H1[1]:
                mark += '1'
            elif cls.H2[0] <= p <= cls.H2[1]:
                mark += '2'
            elif cls.H3[0] <= p <= cls.H3[1]:
                mark += '3'
            else:
                mark += '0'
        return mark

    @classmethod
    def mark_light_seq(cls, pos: List[int]) -> str:
        mark = ''
        for p in pos:
            if p < cls.LFR1[0] or p > cls.LFR4[1]:
                mark += 'X'
            elif cls.L1[0] <= p <= cls.L1[1]:
                mark += '1'
            elif cls.L2[0] <= p <= cls.L2[1]:
                mark += '2'
            elif cls.L3[0] <= p <= cls.L3[1]:
                mark += '3'
            else:
                mark += '0'
        return mark



_NSYS_NAMESPACE = {
    Chothia.__name__: Chothia,
    IMGT.__name__: IMGT

}


def set_nsys(cls):
    os.environ['NUMBERING_SYSTEM'] = cls.__name__


def get_nsys():
    key = 'NUMBERING_SYSTEM'
    name = os.environ.get(key, 'IMGT')
    return _NSYS_NAMESPACE[name]


def register_nsys(cls):
    _NSYS_NAMESPACE[cls.__name__] = cls
    return cls.__name__



def _extract_next_fr_cdr(regions, cdr_mark):
    if cdr_mark in regions:
        fr = regions[:regions.index(cdr_mark)]
        cdr = regions[regions.index(cdr_mark):regions.rindex(cdr_mark) + 1]
        regions = regions[regions.rindex(cdr_mark) + 1:]
    else:
        fr, cdr = '', ''
    return fr, cdr, regions


def _fr1_pos_ids(number_system, length, chain_type):
    all_ids = number_system.HFR1 if chain_type == 'H' else number_system.LFR1
    start = all_ids[1]
    pos_ids = []
    while length > 0:
        pos_ids.append((start, ''))
        length -= 1
        start -= 1
    return pos_ids[::-1]

def _inter_pos_ids(number_system, length, name, side_to_middle=False):
    start, end = getattr(number_system, name)
    insert_pos = number_system.INSERTION.get(name, [])
    all_ids = [(i, '') for i in range(start, end + 1)]
    if len(all_ids) < length:
        num_insert = length - len(all_ids)
        if len(insert_pos) == 0: raise ValueError(f'Region {name} longer than definition but no insertion allowed')
        for i in range(num_insert):
            all_ids.append((insert_pos[0], chr(ord('A') + i)))
    elif side_to_middle:   # all ids more or equal to length
        if length % 2 == 0: l_len, r_len = length // 2, length // 2
        else: l_len, r_len = length // 2 + 1, length // 2
        all_ids = all_ids[:l_len] + all_ids[-r_len:]    # two side to middle
    else:
        all_ids = all_ids[:length]
    return sorted(all_ids)


def _fr4_pos_ids(number_system, length, chain_type):
    all_ids = number_system.HFR4 if chain_type == 'H' else number_system.LFR4
    start = all_ids[0]
    pos_ids = []
    while length > 0:
        pos_ids.append((start, ''))
        length -= 1
        start += 1
    return pos_ids


def assign_pos_ids(regions: str, chain_type: str):
    '''
    Args:
        regions: string of region definition, e.g. 00000111100022200003333000, where 1/2/3 denotes CDR 1/2/3
        chain_type: H or L
    '''
    Nsys = get_nsys()
    fr1, cdr1, regions = _extract_next_fr_cdr(regions, '1')
    fr2, cdr2, regions = _extract_next_fr_cdr(regions, '2')
    fr3, cdr3, fr4 = _extract_next_fr_cdr(regions, '3')

    pos_ids = _fr1_pos_ids(Nsys, len(fr1), chain_type) + \
              _inter_pos_ids(Nsys, len(cdr1), chain_type + '1') + \
              _inter_pos_ids(Nsys, len(fr2), chain_type + 'FR2', side_to_middle=True) + \
              _inter_pos_ids(Nsys, len(cdr2), chain_type + '2') + \
              _inter_pos_ids(Nsys, len(fr3), chain_type + 'FR3', side_to_middle=True) + \
              _inter_pos_ids(Nsys, len(cdr3), chain_type + '3') + \
              _fr4_pos_ids(Nsys, len(fr4), chain_type)
    return pos_ids
    