#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import json
import argparse
import statistics
from easydict import EasyDict

import ray
import numpy as np
from Bio import PDB

from data.converter.pdb_to_list_blocks import pdb_to_list_blocks
from utils.logger import print_log
from evaluation.rmsd import compute_rmsd
from evaluation.aar import compute_aar

from .base import TaskScanner, Task



@ray.remote(num_cpus=1)
def cal_metrics(task: Task):
    
    generated = pdb_to_list_blocks(task.current_path, dict_form=True, allow_het=True)
    reference = pdb_to_list_blocks(task.ref_path, dict_form=True, allow_het=True)

    gen_segs, ref_segs = [], []
    for segs in task.gen_block_idx:
        gen_segs.append([])
        ref_segs.append([])
        for chain, idx in segs:
            gen_segs[-1].append(generated[chain][idx])
            ref_segs[-1].append(reference[chain][idx])

    # AAR
    aars = []
    for gen_seq, ref_seq in zip(task.gen_seq, task.ref_seq):
        aars.append(compute_aar(gen_seq, ref_seq))
    task.set_metric('AAR', aars)

    # CA RMSD
    rmsds = []
    for gen_blocks, ref_blocks in zip(gen_segs, ref_segs):
        gen_ca_x, ref_ca_x = [], []
        for gblk, rblk in zip(gen_blocks, ref_blocks):
            if not rblk.is_residue(): continue
            gen_ca_x.append(gblk.get_unit_by_name('CA').get_coord())
            ref_ca_x.append(rblk.get_unit_by_name('CA').get_coord())
        rmsds.append(compute_rmsd(np.array(gen_ca_x), np.array(ref_ca_x)))
    task.set_metric('RMSD_CA', rmsds)

    # full-atom RMSD
    atom_rmsds = []
    for gen_blocks, ref_blocks in zip(gen_segs, ref_segs):
        gen_x, ref_x = [], []
        for gblk, rblk in zip(gen_blocks, ref_blocks):
            if not gblk.abrv == rblk.abrv: continue
            if not rblk.is_residue(): continue
            for atom in rblk:
                if atom.name == 'OXT': continue
                if not gblk.has_unit(atom.name):
                    print_log(f'Generated block missing {atom.name}: {gblk}', level='ERROR')
                    continue
                gen_x.append(gblk.get_unit_by_name(atom.name).get_coord())
                ref_x.append(atom.get_coord())
        if len(gen_x) == 0: atom_rmsds.append(None) # No hit residues
        else: atom_rmsds.append(compute_rmsd(np.array(gen_x), np.array(ref_x)))
    task.set_metric('RMSD_atom', atom_rmsds)

    # # parse pdb
    # parser = PDB.PDBParser(QUIET=True)
    # try:
    #     model = parser.get_structure(task.id, task.current_path)[0]
    #     ref = parser.get_structure(task.id, task.ref_path)[0]
    # except Exception:
    #     task.mark_failure()
    #     return task

    # # get target CDR
    # residue_first, residue_last = task.metadata.residue_first, task.metadata.residue_last
    # model_cdr_data = get_cdr(model, residue_first, residue_last)
    # ref_cdr_data = get_cdr(ref, residue_first, residue_last)

    # # RMSD
    # rmsd = compute_rmsd(model_cdr_data.pos_heavyatom[:, 1].numpy(), ref_cdr_data.pos_heavyatom[:, 1].numpy())
    # task.set_metric('RMSD', rmsd)

    # # bbRMSD
    # bb_rmsd = compute_rmsd(model_cdr_data.pos_heavyatom[:, :4].reshape(-1, 3).numpy(), ref_cdr_data.pos_heavyatom[:, :4].reshape(-1, 3).numpy())
    # task.set_metric('bbRMSD', bb_rmsd)

    task.mark_success()
    return task


def print_results(path):
    with open(path, 'r') as fin:
        items = [EasyDict(json.loads(line)) for line in fin.readlines()]
    
    methods = {
        'max': max,
        'min': min,
        'mean': lambda l: sum(l) / len(l)
    }

    for metric_name in items[0].metric:
        print(metric_name)

        agg_by_id = {}

        for item in items:
            name = item.id
            if name not in agg_by_id: agg_by_id[name] = []
            agg_by_id[name].append(item.metric[metric_name])
        
        for name in agg_by_id:
            vals = []
            for v in agg_by_id[name]:
                assert len(v) == 1
                if v[0] is None: continue # metric on this sample is not available (e.g. full-atom RMSD for codesigned yet not hit blocks)
                vals.append(v[0])
            if len(vals) == 0: agg_by_id[name] = { m: None for m in methods}
            else: agg_by_id[name] = { m: methods[m](vals) for m in methods }
        
        for m in methods:
            vals = [agg_by_id[name][m] for name in agg_by_id if agg_by_id[name][m] is not None]
            print(f'\t{m}: {sum(vals) / len(vals)}')


def parse():
    parser = argparse.ArgumentParser(description='calculating metrics')
    parser.add_argument('--result_dir', type=str, required=True, help='Directory of results')
    parser.add_argument('--out_path', type=str, default=None, help='Output path, default dG_report.jsonl under the same directory as results')
    return parser.parse_args()


def main(args):
    # output summary
    if args.out_path is None:
        args.out_path = os.path.join(args.result_dir, 'metrics.jsonl')
    
    # if os.path.exists(args.out_path):
    #     print_log(f'Existing metric file: {args.out_path}')
    #     print_results(args.out_path)
    #     return

    # parallel
    scanner = TaskScanner(args.result_dir)
    tasks = scanner.scan()
    ray.init(num_cpus=16)
    futures = [cal_metrics.remote(t) for t in tasks]
    if len(futures) > 0:
        print_log(f'Submitted {len(futures)} tasks.')

    fout = open(args.out_path, 'w')
    while len(futures) > 0:
        done_ids, futures = ray.wait(futures, num_returns=1)
        for done_id in done_ids:
            done_task = ray.get(done_id)
            # print_log(f'Remaining {len(futures)}. Finished {done_task.current_path}, dG {done_task.metric}')
            if done_task.status == 'failed':
                continue
            res  = {
                'id': done_task.id,
                'number': done_task.number,
                'metric': done_task.metric
            }
            fout.write(json.dumps(res) + '\n')
            fout.flush()
    fout.close()
    
    print_results(args.out_path)


if __name__ == '__main__':
    import random
    random.seed(12)
    main(parse())
