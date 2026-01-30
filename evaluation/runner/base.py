#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import re
import json
from typing import Optional, Tuple, List
from dataclasses import dataclass

from easydict import EasyDict


@dataclass
class Task:
    id: str
    number: int
    in_path: str
    current_path: str
    ref_path: str # meta data path
    rec_chains: List[str]
    lig_chains: List[str]
    ref_seq: List[str]
    gen_seq: List[str]
    gen_block_idx: List[List[Tuple[str, int]]]
    metric: Optional[dict] = None

    def set_metric(self, name, value):
        if self.metric is None:
            self.metric = {}
        self.metric[name] = value

    def get_in_path_with_tag(self, tag):
        name, ext = os.path.splitext(self.in_path)
        new_path = f'{name}_{tag}{ext}'
        return new_path

    def set_current_path_tag(self, tag):
        new_path = self.get_in_path_with_tag(tag)
        self.current_path = new_path
        return new_path

    def check_current_path_exists(self):
        ok = os.path.exists(self.current_path)
        if not ok:
            self.mark_failure()
        if os.path.getsize(self.current_path) == 0:
            ok = False
            self.mark_failure()
            os.unlink(self.current_path)
        return ok

    def update_if_finished(self, tag):
        out_path = self.get_in_path_with_tag(tag)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            # print('Already finished', out_path)
            self.set_current_path_tag(tag)
            self.mark_success()
            return True
        return False

    def can_proceed(self):
        self.check_current_path_exists()
        return self.status != 'failed'

    def mark_success(self):
        self.status = 'success'

    def mark_failure(self):
        self.status = 'failed'


class TaskScanner:

    def __init__(self, result_dir, include_ref=False):
        super().__init__()
        self.result_dir = result_dir
        self.result_index = os.path.join(result_dir, 'results.jsonl')
        self.include_ref = include_ref

    def scan(self) -> List[Task]: 
        tasks = []
        with open(self.result_index, 'r') as fin:
            lines = fin.readlines()
        for line in lines:
            item = json.loads(line)
            tasks.append(Task(
                id = item['id'],
                number = item['n'],
                in_path = item['gen_pdb'],
                current_path = item['gen_pdb'],
                ref_path = item['ref_pdb'],
                rec_chains = item['rec_chains'],
                lig_chains = item['lig_chains'],
                ref_seq = item['ref_seq'],
                gen_seq = item['gen_seq'],
                gen_block_idx = item['gen_block_idx'],
            ))

        return tasks