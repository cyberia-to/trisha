#!/usr/bin/env python3
"""Check retained bytes and replay recorded claim checks; never rerun a proof."""
import argparse
import ast
import gzip
import hashlib
import io
import json
import ntpath
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import types

CHECKER = '29b98dac0b6f07f579b3f44fdbe7e41c262b0372088d2909acf4e0d076cd229b'
BENCH = 'c27bf22f042458b412c32d1d1aa149a6e14aab189f2c9bd96b1d1bc12389c112'
MAX_RAW = 64 << 20


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def bounded(path, maximum):
    require(stat.S_ISREG(path.lstat().st_mode) and path.stat().st_size <= maximum,
            f'bounded ordinary file required: {path}')
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    require(len(data) <= maximum, 'file grew beyond bound')
    return data


def check(directory):
    index = json.loads(bounded(directory / 'files.json', 4 << 20))
    require(index['schema'] == 'local/cpu-proof-retention/v1', 'index schema')
    require(identity(bounded(Path(__file__), 1 << 20)) == index['checker'] and
            identity(bounded(directory / 'collect.py', 1 << 20)) == index['collector'],
            'retention helper identities')
    archive = bounded(directory / 'raw-evidence.tar.gz', 40 << 20)
    require(identity(archive) == index['archive'], 'compressed archive identity')
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as stream:
        raw = stream.read(MAX_RAW + 1)
    require(len(raw) <= MAX_RAW and identity(raw) == index['tar'], 'raw tar identity/bound')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as source:
        for member in source:
            path = PurePosixPath(member.name)
            require(member.isfile() and not path.is_absolute() and
                    path.as_posix() == member.name and
                    all(part not in ('', '.', '..') for part in path.parts), 'ordinary canonical member')
            require(member.name not in files and len(files) < 128 and
                    0 <= member.size <= MAX_RAW, 'member count/size/uniqueness')
            files[member.name] = source.extractfile(member).read()
    require({name: identity(data) for name, data in files.items()} == index['files'],
            'exact member set and raw bytes')
    load = lambda name: json.loads(files[name])
    driver = load('cpu-and-proofs.json')
    require(driver['status'] in ('passed', 'failed'), 'completed original driver required')
    require(identity(files['cpu-and-proofs.py']) == driver['driver'], 'measured driver identity')
    require(identity(files['source/check-baselines.py'])['sha256'] == CHECKER and
            identity(files['source/bench.rs'])['sha256'] == BENCH, 'pinned gate implementation')
    require(identity(files['source/native-candidate.py']) == driver['archived_coordinator'],
            'archived coordinator identity')
    for command in driver['commands']:
        for stream in ('stdout', 'stderr'):
            if stream in command:
                row = command[stream]
                require(identity(files[row['path']]) == {k: row[k] for k in ('bytes', 'sha256')},
                        'exact command raw log')
    cpu = {}
    for name in ('trident', 'trisha', 'joy'):
        command = next(row for row in driver['commands'] if row['name'] == name + '-tests')
        data = files[command['stdout']['path']] + files[command['stderr']['path']]
        summaries = re.findall(rb'test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored;', data)
        totals = dict(zip(('passed', 'failed', 'ignored'),
                          map(sum, zip(*(tuple(map(int, row[1:])) for row in summaries)))))
        warnings = len(re.findall(rb'^warning(?:\[[^\]\r\n]+\])?:', data, re.M))
        require(totals == command['rust_totals'] and len(summaries) == command['rust_summaries']
                and warnings == command['warning_lines'], 'actual CPU summaries/warnings')
        cpu[name] = dict(**totals, summaries=len(summaries), warnings=warnings,
                         exit_code=command['exit_code'])
    candidate = load('metadata/candidate.json')
    require(identity(files['metadata/candidate.json']) == driver['candidate_start'] == driver['candidate_end'],
            'candidate start/end identity')
    require(driver['binaries_start'] == driver['binaries_end'] and
            {n: row['sha256'] for n, row in driver['binaries_end'].items()} ==
            {row['name']: row['sha256'] for row in candidate['binaries']}, 'recorded binary identity continuity')
    require(identity(files['metadata/sources.json'])['sha256'] == candidate['provenance_sha256'] and
            identity(files['metadata/source-verification.json'])['sha256'] ==
            candidate['source_verification_sha256'], 'source manifest binding')
    prepare = load('metadata/prepare.json')
    tools_end = load('metadata/tools-end.json')['tools']
    require(set(tools_end) == {'cargo', 'rustc', 'z3'}, 'exact recorded tool set')
    for name, row in tools_end.items():
        original = (load('metadata/z3.json')['binary']['sha256'] if name == 'z3'
                    else prepare['tool_paths'][name]['sha256'])
        require(row['unchanged'] is True and row['start_sha256'] == row['end']['sha256'] == original,
                'recorded Rust/solver start-end hashes')
    proof = load('baseline-proofs/receipt.json')
    started = load('baseline-proofs/started.json')
    require(identity(files['baseline-proofs/started.json'])['sha256'] == proof['started_sha256'] and
            identity(files['baseline-proofs/bench.log'])['sha256'] == proof['log_sha256'], 'proof raw log binding')
    require(started['script_sha256'] == CHECKER and started['candidate'] == candidate and
            started['rss_limit_bytes'] == 28 * 1024**3 and started['rayon_threads'] == 4 and
            started['lde_trace'] == 'no_cache', 'original proof command profile')
    require(proof['binaries'] == {row['name']: row['sha256'] for row in candidate['binaries']},
            'proof installed binary bindings')
    # Only these two functions from the exact pinned archived checker are loaded.
    # Preserve the recorded POSIX path semantics even on a Windows replay host.
    tree = ast.parse(files['source/check-baselines.py'])
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ('fixture_key', 'checked_log')]
    require(len(selected) == 2, 'pinned oracle functions')
    namespace = dict(os=types.SimpleNamespace(name='posix'), ntpath=ntpath, json=json, re=re)
    exec(compile(ast.Module(body=selected, type_ignores=[]), 'retained-check-baselines.py', 'exec'), namespace)
    log = files['baseline-proofs/bench.log'].decode()
    if driver['status'] == 'passed':
        events = namespace['checked_log'](log, started['fixtures'], len(started['baselines']))
        require(len(started['fixtures']) == 133 and len(started['baselines']) == 43 and
                len(events) == 198 and events == proof['verified_proof_events'], 'complete exact recorded oracle coverage')
        require(proof['all_checks_passed'] is True and proof['exit_code'] == 0 and
                proof['guard_stop'] is None and proof['inputs_unchanged'] is True and
                proof['positive_fixtures_passed'] == 99 and proof['negative_fixtures_rejected'] == 34 and
                proof['fresh_verified_proofs'] == 198, 'original proof gate verdict')
        require(all(c['exit_code'] == 0 and c['failed'] == c['warnings'] == 0 for c in cpu.values()),
                'original CPU gate verdict')
        require(all(c['status'] == 'completed' and c['exit_code'] == 0 for c in driver['commands']),
                'all original driver commands completed')
        require([(cpu[n]['passed'], cpu[n]['failed'], cpu[n]['ignored'])
                 for n in ('trident', 'trisha', 'joy')] == [(1231, 0, 5), (429, 0, 6), (172, 0, 0)],
                'exact measured CPU coverage')
        require(json.loads(files['cpu-results/source-before.stdout']) ==
                json.loads(files['cpu-results/source-after.stdout']) ==
                load('metadata/source-verification.json'), 'exact original source guards')
        # Synthetic failures check the retained log parser, not proof cryptography.
        lines = log.splitlines()
        position = next(i for i, line in enumerate(lines) if line.startswith('TRISHA_PROOF_VERIFIED\t'))
        changed = json.loads(lines[position].split('\t', 1)[1])
        changed['public_output'] = [0] if not changed['public_output'] else []
        variants = [lines[:position] + lines[position + 1:],
                    lines[:position] + [lines[position]] + lines[position:],
                    lines[:position] + ['TRISHA_PROOF_VERIFIED\t' + json.dumps(changed)] + lines[position + 1:]]
        for variant in variants:
            try:
                namespace['checked_log']('\n'.join(variant), started['fixtures'], len(started['baselines']))
            except (ValueError, TypeError, KeyError):
                continue
            raise ValueError('synthetic missing/duplicate/altered claim accepted')
    return dict(status='retention-consistent', original_gate_status=driver['status'], cpu=cpu,
                retained_files=len(files), fresh_verified_proofs=proof['fresh_verified_proofs'],
                oracle_rejection_checks=3 if driver['status'] == 'passed' else 0,
                proof_payloads_retained=False,
                scope='Archive integrity and recorded oracle replay; no cryptographic proof re-verification')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.directory), indent=2))
