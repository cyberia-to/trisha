#!/usr/bin/env python3
"""Run the complete real baseline proof gate against one verified source candidate.

This records the exact executable and complete input/source inventories before
and after proving. It does not retrofit provenance onto older benchmark logs.
"""
import argparse
import hashlib
import importlib.util
import json
import ntpath
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import tomllib

sys.dont_write_bytecode = True
if os.name == 'nt':
    from windows_process import Job


def binary(prefix, name):
    return prefix/'bin'/(name + ('.exe' if os.name == 'nt' else ''))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def fixture_key(path, windows=os.name == 'nt'):
    # Rust canonicalize emits extended-length Windows paths; Python resolve
    # usually emits drive paths. They identify the same inventoried fixture.
    if windows:
        if path.startswith('\\\\?\\UNC\\'):
            path = '\\\\' + path[8:]
        elif path.startswith('\\\\?\\'):
            path = path[4:]
        return ntpath.normcase(ntpath.normpath(path))
    return path


def checked_log(log, fixtures, baseline_count):
    """Require exact fixture rows and verified proof pairs, never infer proofs from PASS."""
    expected = {fixture_key(f['absolute_path']): f for f in fixtures}
    if len(expected) != len(fixtures):
        raise ValueError('duplicate fixture identity')
    completed, proofs = set(), {}
    summary = f'{len(fixtures)} / {len(fixtures)} fixtures passed; {baseline_count} / {baseline_count} baselines verified'
    summaries = 0
    for line in log.splitlines():
        if line == summary:
            summaries += 1
        if line.startswith('TRISHA_PROOF_VERIFIED\t'):
            event = json.loads(line.split('\t', 1)[1])
            event_path = event.get('fixture')
            if not isinstance(event_path, str):
                raise ValueError('proof event is missing its fixture path')
            event_path = fixture_key(event_path)
            fixture = expected.get(event_path)
            implementation = event.get('implementation')
            key = (event_path, implementation)
            if (fixture is None or fixture['negative'] or implementation not in ('classic', 'hand')
                    or key in proofs or key[0] in completed):
                raise ValueError('unexpected, duplicate or late proof event')
            inputs = fixture['input'] if implementation == 'classic' else fixture['hand_input']
            digest = event.get('program_hash')
            if (type(event.get('schema_version')) is not int or event['schema_version'] != 1 or event.get('generated_and_verified') is not True
                    or event.get('format') != 'stark-triton-v7'
                    or event.get('public_input') != inputs or event.get('public_output') != fixture['output']
                    or any(type(v) is not int or not 0 <= v < 18446744069414584321
                           for key in ('public_input', 'public_output') for v in event[key])
                    or not isinstance(digest, list) or len(digest) != 5
                    or any(type(v) is not int or not 0 <= v < 18446744069414584321 for v in digest)
                    or type(event.get('proof_bytes')) is not int or event['proof_bytes'] <= 0
                    or not re.fullmatch('[0-9a-f]{64}', event.get('proof_hemera', ''))):
                raise ValueError('invalid proof event or mismatched public claim')
            proofs[key] = event
        columns = line.split('\t')
        if columns[-1] not in ('PASS', 'PASS (both executions rejected)'):
            continue
        row_path = fixture_key(columns[0])
        fixture = expected.get(row_path)
        if len(columns) != 5 or fixture is None or row_path in completed:
            raise ValueError('unexpected or duplicate fixture result')
        if fixture['negative']:
            if columns[1:] != ['-', '-', '-', 'PASS (both executions rejected)']:
                raise ValueError('negative fixture did not reject')
        elif (columns[-1] != 'PASS' or not columns[1].isdigit() or not columns[2].isdigit()
              or columns[3] != f'{columns[2]}/{columns[1]}'
              or any((row_path, impl) not in proofs for impl in ('classic', 'hand'))):
            raise ValueError('positive fixture lacks its verified proof pair')
        completed.add(row_path)
    if completed != set(expected) or summaries != 1:
        raise ValueError('incomplete fixture coverage or missing exact summary')
    positive = sum(not f['negative'] for f in fixtures)
    if len(proofs) != 2 * positive:
        raise ValueError('incomplete fresh proof coverage')
    return list(proofs.values())


def stop_group(process):
    if os.name == 'nt':
        process.release_job.close()
        process.wait(timeout=30)
        return
    # The process group belongs to this invocation, including children surviving
    # their direct parent. Kill the group even when the parent has already exited.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('work', type=Path)
    parser.add_argument('--rss-limit-gib', type=int, default=40)
    args = parser.parse_args()
    prefix = args.candidate.resolve(strict=True)
    work = args.work.absolute()
    if work.exists() or work.is_symlink():
        parser.error('work directory must not already exist')
    if args.rss_limit_gib <= 0:
        parser.error('RSS limit must be positive')
    candidate = json.loads((prefix/'candidate.json').read_text())
    source = Path(candidate['source']).resolve(strict=True)
    own_script = Path(__file__).resolve(strict=True)
    archived_script = source/'trisha/scripts/check-baselines.py'
    if sha(own_script) != sha(archived_script):
        parser.error('run the exact checker included in the source candidate')
    for parent in [source, prefix]:
        if work == parent or parent in work.resolve().parents:
            parser.error('work must be outside source and installed candidate')
    # Importing the archived verifier must not mutate its exact source inventory.
    # This is a property of the default command, independent of Python flags/env.
    sys.dont_write_bytecode = True
    verifier_spec = importlib.util.spec_from_file_location('source_verifier', source/'trisha/scripts/verify-source.py')
    verifier = importlib.util.module_from_spec(verifier_spec)
    verifier_spec.loader.exec_module(verifier)
    verification_bytes = (prefix/'source-verification.json').read_bytes()
    verification = json.loads(verification_bytes)
    if (not candidate.get('source_verified') or
            hashlib.sha256(verification_bytes).hexdigest() != candidate['source_verification_sha256'] or
            sha(source/'sources.json') != candidate['provenance_sha256']):
        parser.error('candidate source receipt mismatch')
    initial = verifier.verify(source)
    if initial != verification:
        parser.error('source/vendor inventory mismatch')
    binaries = {item['name']: item['sha256'] for item in candidate['binaries']}
    for name in ['trident','trident-lsp','trisha','joy']:
        if sha(binary(prefix, name)) != binaries[name]:
            parser.error(f'candidate binary mismatch: {name}')
    baseline_root = source/'trisha/baselines/triton'
    fixtures = []
    for path in sorted(baseline_root.rglob('*.bench.toml')):
        data = tomllib.loads(path.read_text())
        referenced = [data['source'], data['hand'], *data.get('witness_files', []), *data.get('hand_libraries', [])]
        for value in referenced:
            resolved = (path.parent/value).resolve(strict=True)
            resolved.relative_to(source)
            if not resolved.is_file():
                parser.error('fixture dependency must be an inventoried source file')
        if type(data.get('expect_failure', False)) is not bool:
            parser.error('fixture expect_failure must be boolean')
        fields = lambda values: [int(value) for value in values]
        fixtures.append(dict(path=str(path.relative_to(source)), absolute_path=str(path.resolve()), sha256=sha(path),
                             input=fields(data['input']), hand_input=fields(data.get('hand_input', data['input'])),
                             output=fields(data['output']),
                             negative=data.get('expect_failure', False),
                             hand=str((path.parent/data['hand']).resolve().relative_to(source))))
    positive = sum(not f['negative'] for f in fixtures)
    negative = sum(f['negative'] for f in fixtures)
    baselines = {str(p.resolve().relative_to(source)) for p in baseline_root.rglob('*.tasm')}
    if (len(baselines), positive, negative) != (43,99,34):
        parser.error(f'inventory changed: {len(baselines)} baselines, {positive} positive, {negative} negative; review the gate contract')
    if {f['hand'] for f in fixtures if not f['negative']} != baselines:
        parser.error('positive fixtures do not cover the exact baseline set')
    work.mkdir()
    command = [str(binary(prefix, 'trisha')), 'bench', str(baseline_root), '--full']
    start = dict(format='trisha-complete-baseline-gate-v1', candidate=candidate,
                 source_verification_sha256=candidate['source_verification_sha256'],
                 script_sha256=sha(own_script), fixtures=fixtures,
                 baselines=sorted(baselines), command=command,
                 rayon_threads=4, lde_trace='no_cache', rss_limit_bytes=args.rss_limit_gib*1024**3)
    write(work/'started.json',start)
    env={k:v for k,v in os.environ.items() if not k.startswith('TRIDENT_')}
    env.update(PATH=str(prefix/'bin'),RAYON_NUM_THREADS='4',TVM_LDE_TRACE='no_cache')
    started=time.monotonic(); peak=0; guard_stop=None
    with (work/'bench.log').open('x') as log, (work/'memory.jsonl').open('x') as memory:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,cwd=work,start_new_session=os.name!='nt')
        if os.name == 'nt':
            process.release_job = Job(process)
        try:
            while process.poll() is None:
                free_percent=None;available=None
                if os.name == 'nt':
                    rss, available = process.release_job.sample()
                else:
                    rows=subprocess.check_output(['/bin/ps','-axo','pid,pgid,rss'],text=True).splitlines()[1:]
                    data=[tuple(map(int,row.split())) for row in rows if len(row.split())==3]
                    rss=sum(rss for pid,group,rss in data if group==process.pid)*1024
                peak=max(peak,rss)
                if sys.platform=='darwin':
                    pressure=subprocess.check_output(['/usr/bin/memory_pressure','-Q'],text=True)
                    match=re.search(r'memory free percentage:\s*(\d+)%',pressure)
                    if not match: raise RuntimeError('cannot read host memory pressure')
                    free_percent=int(match.group(1))
                elif os.name != 'nt':
                    match=re.search(r'^MemAvailable:\s*(\d+) kB',Path('/proc/meminfo').read_text(),re.M)
                    if not match:raise RuntimeError('cannot read available memory')
                    available=int(match.group(1))*1024
                row=dict(elapsed_seconds=time.monotonic()-started,rss_bytes=rss,peak_rss_bytes=peak,
                         memory_free_percent=free_percent,memory_available_bytes=available)
                memory.write(json.dumps(row)+'\n');memory.flush()
                print(json.dumps(row),flush=True)
                if rss>start['rss_limit_bytes'] or (free_percent is not None and free_percent<8) or (available is not None and available<1024**3):
                    guard_stop='memory bound reached';stop_group(process);break
                time.sleep(5)
            process.wait(timeout=30)
        finally:
            stop_group(process)
    # Completed outputs must still refer to the initial exact artifacts.
    unchanged=(verifier.verify(source)==initial and
               (prefix/'source-verification.json').read_bytes()==verification_bytes and
               json.loads((prefix/'candidate.json').read_text())==candidate and
               sha(own_script)==start['script_sha256'] and
               all(sha(binary(prefix, name))==value for name,value in binaries.items()))
    log=(work/'bench.log').read_text()
    proof_events = []
    evidence_error = None
    try:
        proof_events = checked_log(log, fixtures, len(baselines))
    except (ValueError, TypeError, KeyError) as error:
        evidence_error = str(error)
    success=(process.returncode==0 and guard_stop is None and unchanged and evidence_error is None)
    receipt=dict(format=start['format'],all_checks_passed=success,exit_code=process.returncode,
                 guard_stop=guard_stop,inputs_unchanged=unchanged,elapsed_seconds=time.monotonic()-started,
                 peak_rss_bytes=peak,started_sha256=sha(work/'started.json'),log_sha256=sha(work/'bench.log'),
                 source_provenance_sha256=candidate['provenance_sha256'],binaries=binaries,
                 positive_fixtures_passed=positive if success else None,negative_fixtures_rejected=negative if success else None,
                 evidence_error=evidence_error, verified_proof_events=proof_events,
                 fresh_verified_proofs=len(proof_events) if success else None)
    write(work/'receipt.json',receipt)
    print(json.dumps(receipt),flush=True)
    return 0 if success else 1


if __name__=='__main__':
    sys.exit(main())
