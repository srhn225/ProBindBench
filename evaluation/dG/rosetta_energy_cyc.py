#!/usr/bin/python
# -*- coding:utf-8 -*-
import xml.etree.ElementTree as ET 

from pyrosetta import *
from pyrosetta.rosetta.protocols import rosetta_scripts
init(' '.join([
    '-beta_nov16',
    '-mute', 'all'
]))

FRXML = os.path.join(
    os.path.dirname(__file__), 'rosetta_scripts', 'cycpep_fast_relax.xml'
)
METXML = os.path.join(
    os.path.dirname(__file__), 'rosetta_scripts', 'energy.xml'
)


def _xml_set_pep_chain(path, chain_id):
    # create element tree object 
    tree = ET.parse(path) 
  
    # get root element 
    root = tree.getroot() 
  
    # Find all Chain selectors in RESIDUE_SELECTORS
    for chain_selector in root.findall("./RESIDUE_SELECTORS/Chain"):
        # Modify the 'chains' attribute
        chain_selector.set("chains", chain_id)
    
    # Convert the modified XML to a string
    modified_xml = ET.tostring(root, encoding="unicode")

    return modified_xml


def _energy_xml_set_chains(path, tgt_chain, pep_chain):
    # create element tree object 
    tree = ET.parse(path) 
  
    # get root element 
    root = tree.getroot() 
  
    # Find all Chain selectors in RESIDUE_SELECTORS
    for chain_selector in root.findall("./RESIDUE_SELECTORS/Chain"):
        # Modify the 'chains' attribute
        if chain_selector.attrib['name'] == 'chainA':
            chain_selector.set("chains", tgt_chain)
        elif chain_selector.attrib['name'] == 'chainB':
            chain_selector.set("chains", pep_chain)
    
    # Convert the modified XML to a string
    modified_xml = ET.tostring(root, encoding="unicode")

    return modified_xml

  

def pyrosetta_fastrelax(pdb_path, out_path, pep_chain):

    xml_str = _xml_set_pep_chain(FRXML, pep_chain)
    
    objs = rosetta_scripts.XmlObjects.create_from_string(xml_str)
    fr = objs.get_mover('full_relax_complex')
    pcm = objs.get_mover('pcm')
    pose = pose_from_pdb(pdb_path)
    pcm.apply(pose)
    fr.apply(pose)
    pcm.apply(pose)
    pose.dump_pdb(out_path)


def pyrosetta_metrics(pdb_path, tgt_chain, pep_chain):

    xml_str = _energy_xml_set_chains(METXML, tgt_chain, pep_chain)

    objs = rosetta_scripts.XmlObjects.create_from_string(xml_str)
    
    # movers
    min_if = objs.get_mover('minimize_interface')
    pcm = objs.get_mover('pcm')

    # metrics
    ddg = objs.get_filter('ddg')
    sap = objs.get_simple_metric('sap_score')
    cms = objs.get_filter('contact_molecular_surface')

    pose = pose_from_pdb(pdb_path)
    pcm.apply(pose)
    min_if.apply(pose)
    pcm.apply(pose)

    return {
        'pyrosetta_dG': ddg.score(pose),
        'SAP': sap.calculate(pose),
        'CMS': cms.score(pose)
    }



if __name__ == '__main__':
    import sys
    import json

    args = json.loads(sys.argv[1])

    if not os.path.exists(args['out_path']):
        # fast relax
        pyrosetta_fastrelax(args['pdb_path'], args['out_path'], args['pep_chain'])

    # get metrics
    metrics = pyrosetta_metrics(args['out_path'], args['tgt_chain'], args['pep_chain'])

    print(json.dumps(metrics))