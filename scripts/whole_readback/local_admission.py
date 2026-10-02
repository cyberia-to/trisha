"""Full local before/after closure through the frozen original audited predicates."""
import importlib.util
import sys
from pathlib import Path
import time

import gate


def original(directory):
    source=gate.load(gate.FROZEN/'sources.json')
    for name,value in source.items():gate.require(gate.identity(directory/name)==value,'unchanged original local helper '+name)
    # Only exact reviewed source is loaded; no fetched evidence code is executed.
    spec=importlib.util.spec_from_file_location('admission',directory/'admission.py')
    module=importlib.util.module_from_spec(spec);sys.modules['admission']=module;spec.loader.exec_module(module)
    spec=importlib.util.spec_from_file_location('original_local_contracts',directory/'contracts.py')
    contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
    return contract,source


def scan(directory):
    _,expected,_=gate.frozen();contract,source=original(directory)
    started=time.time_ns();prepared=contract.local_admission(expected,scan=True)
    for name,value in source.items():gate.require(gate.identity(directory/name)==value,'original checking source stable')
    return dict(schema='trident/local-certificate-byte-closure/v1',status='passed-complete-local-scan',started_ns=started,ended_ns=time.time_ns(),original_helper_sources=source,local_preparation=expected['local_preparation'],prepared=prepared,scope='Actual whole and22part hashes plus original four receipts/inputs/binaries; before or after observation, not continuous filesystem attestation.')


def compare(before,after):
    gate.require(before['schema']==after['schema']=='trident/local-certificate-byte-closure/v1' and before['status']==after['status']=='passed-complete-local-scan','both complete local observations passed')
    for field in ('original_helper_sources','local_preparation','prepared'):gate.require(before[field]==after[field],'exact local before/after closure: '+field)
    gate.require(before['ended_ns']<after['started_ns'],'ordered independent local observations')
