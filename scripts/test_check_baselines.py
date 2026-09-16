"""Acceptance and cleanup regressions; no STARK generation or wallet actions."""
import copy
import hashlib
import os
import shutil
import tempfile
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

# Keep the test runner's own dynamic import out of the working source tree too.
sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location('gate', Path(__file__).with_name('check-baselines.py'))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class BaselineGate(unittest.TestCase):
    def setUp(self):
        self.fixtures = [dict(absolute_path='/f/positive.bench.toml', negative=False,
                              input=[7], hand_input=[19], output=[31]),
                         dict(absolute_path='/f/negative.bench.toml', negative=True,
                              input=[], hand_input=[], output=[])]
        self.events = [dict(schema_version=1, fixture=self.fixtures[0]['absolute_path'],
                            implementation=kind, format='stark-triton-v7', program_hash=[1,2,3,4,5],
                            public_input=values, public_output=[31], proof_hemera='ab'*32,
                            proof_bytes=128, generated_and_verified=True)
                       for kind, values in [('classic', [7]), ('hand', [19])]]
        self.rows = ['/f/positive.bench.toml\t10\t20\t20/10\tPASS',
                     '/f/negative.bench.toml\t-\t-\t-\tPASS (both executions rejected)',
                     '2 / 2 fixtures passed; 1 / 1 baselines verified']

    def log(self, events=None, rows=None):
        return '\n'.join(['TRISHA_PROOF_VERIFIED\t'+json.dumps(e)
                          for e in (self.events if events is None else events)]
                         + (self.rows if rows is None else rows))

    def test_complete_explicit_verified_pairs_bind_distinct_implementation_inputs(self):
        self.assertEqual(gate.checked_log(self.log(), self.fixtures, 1), self.events)

    def test_windows_extended_paths_bind_the_same_fixture_and_still_reject_unknowns(self):
        fixtures = copy.deepcopy(self.fixtures)
        events = copy.deepcopy(self.events)
        for fixture in fixtures:
            fixture['absolute_path'] = fixture['absolute_path'].replace('/f/', 'C:\\source\\')
        for event in events:
            event['fixture'] = '\\\\?\\' + fixtures[0]['absolute_path']
        rows = [row.replace('/f/', 'C:\\source\\') for row in self.rows]
        normalize = gate.fixture_key
        with patch.object(gate, 'fixture_key', side_effect=lambda path: normalize(path, windows=True)):
            self.assertEqual(gate.checked_log(self.log(events, rows), fixtures, 1), events)
            events[0]['fixture'] += '.unknown'
            with self.assertRaises(ValueError):
                gate.checked_log(self.log(events, rows), fixtures, 1)
        self.assertEqual(normalize('\\\\?\\UNC\\host\\share\\file', windows=True),
                         normalize('\\\\host\\share\\file', windows=True))

    def test_execution_only_and_generation_only_logs_cannot_claim_proofs(self):
        for log in [self.log([]), 'Proof generated (10 cycles, padded height 256)\n'*2+self.log([])]:
            with self.assertRaises(ValueError): gate.checked_log(log, self.fixtures, 1)

    def test_missing_duplicate_unknown_and_negative_proof_events_fail(self):
        invalid = [self.events[:1], self.events*2]
        for change in [dict(fixture='/unknown'), dict(fixture='/f/negative.bench.toml'), dict(implementation='neural')]:
            events=copy.deepcopy(self.events);events[0].update(change);invalid.append(events)
        for events in invalid:
            with self.assertRaises(ValueError): gate.checked_log(self.log(events), self.fixtures, 1)

    def test_false_verification_and_changed_claim_or_proof_identity_fail(self):
        for change in [dict(generated_and_verified=False),dict(public_input=[19]),dict(public_output=[32]),
                       dict(format='stark-triton-v2'),dict(program_hash=[1]),dict(proof_bytes=0),dict(proof_hemera='')]:
            events=copy.deepcopy(self.events);events[0].update(change)
            with self.assertRaises(ValueError): gate.checked_log(self.log(events), self.fixtures, 1)

    def test_duplicate_missing_or_unexpected_fixture_rows_and_summary_fail(self):
        for rows in [self.rows+self.rows[:1],self.rows[:1]+self.rows[2:],self.rows[:-1],self.rows+self.rows[-1:],
                     [self.rows[0].replace('/f/positive','/f/unknown')]+self.rows[1:]]:
            with self.assertRaises(ValueError): gate.checked_log(self.log(rows=rows), self.fixtures, 1)

    def test_events_must_precede_fixture_success(self):
        lines=self.log().splitlines(); lines=lines[2:3]+lines[:2]+lines[3:]
        with self.assertRaises(ValueError): gate.checked_log('\n'.join(lines),self.fixtures,1)

    def test_full_contract_requires_198_verified_events_for_99_positive_and_34_negative(self):
        fixtures, events, rows = [], [], []
        for index in range(133):
            fixture = copy.deepcopy(self.fixtures[0 if index < 99 else 1])
            fixture['absolute_path'] = f'/f/{index}.bench.toml'
            fixtures.append(fixture)
            if index < 99:
                for template in self.events:
                    event = copy.deepcopy(template)
                    event['fixture'] = fixture['absolute_path']
                    events.append('TRISHA_PROOF_VERIFIED\t'+json.dumps(event))
                rows.append(f"{fixture['absolute_path']}\t10\t20\t20/10\tPASS")
            else:
                rows.append(f"{fixture['absolute_path']}\t-\t-\t-\tPASS (both executions rejected)")
        summary = '133 / 133 fixtures passed; 43 / 43 baselines verified'
        self.assertEqual(len(gate.checked_log('\n'.join(events+rows+[summary]),fixtures,43)),198)
        with self.assertRaises(ValueError):
            gate.checked_log('\n'.join(events[:-1]+rows+[summary]),fixtures,43)

    def test_plain_python_preflight_preserves_exact_source_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'source'
            scripts = source/'trisha/scripts'
            scripts.mkdir(parents=True)
            for name in ('check-baselines.py', 'verify-source.py', 'windows_process.py'):
                shutil.copyfile(Path(__file__).with_name(name), scripts/name)
            for name in ('trident', 'joy'):
                (source/name).mkdir()
                (source/name/'lib.rs').write_text('fixture source')
            inventory = []
            for name in ('trident', 'trisha', 'joy'):
                records = []
                for path in sorted((source/name).rglob('*')):
                    if path.is_file():
                        content = path.read_bytes()
                        records.append(dict(path=path.relative_to(source/name).as_posix(),
                                            type='file', bytes=len(content),
                                            sha256=hashlib.sha256(content).hexdigest()))
                inventory.append(dict(repository=name, mode='committed', files=records))
            (source/'sources.json').write_text(json.dumps(inventory))
            (source/'trisha/.vendor').mkdir()
            vendor = source/'trisha/.vendor/lib.rs'
            vendor.write_text('vendor source')
            (source/'vendor-sources.json').write_text(json.dumps([dict(
                path='lib.rs', type='file', bytes=len(vendor.read_bytes()), sha256=gate.sha(vendor))]))
            (source/'BUILD.txt').write_text('fixture instructions')
            env = os.environ.copy()
            for name in ('PYTHONDONTWRITEBYTECODE', 'PYTHONPYCACHEPREFIX'):
                env.pop(name, None)
            # Execute the real verifier directly to create a genuine receipt;
            # neither this nor the gate command uses -B or an equivalent env flag.
            verified = subprocess.run([sys.executable, str(scripts/'verify-source.py'), str(source)],
                                      env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            prefix = root/'candidate'
            (prefix/'bin').mkdir(parents=True)
            receipt = prefix/'source-verification.json'
            receipt.write_text(verified.stdout)
            binaries = []
            for name in ('trident', 'trident-lsp', 'trisha', 'joy'):
                binary = gate.binary(prefix, name)
                binary.write_text('never executed')
                binaries.append(dict(name=name, sha256=gate.sha(binary)))
            (prefix/'candidate.json').write_text(json.dumps(dict(
                source=str(source), source_verified=True, binaries=binaries,
                source_verification_sha256=gate.sha(receipt),
                provenance_sha256=gate.sha(source/'sources.json'))))
            before = {p.relative_to(source).as_posix(): p.read_bytes()
                      for p in source.rglob('*') if p.is_file()}
            result = subprocess.run([sys.executable, str(scripts/'check-baselines.py'),
                                     str(prefix), str(root/'work')],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
            # Passing the real source verifier and receipt comparison reaches
            # the deliberately empty baseline inventory, before starting work.
            self.assertIn('inventory changed: 0 baselines, 0 positive, 0 negative', result.stderr)
            self.assertFalse((root/'work').exists())
            self.assertFalse(list(source.rglob('__pycache__')))
            self.assertEqual(before, {p.relative_to(source).as_posix(): p.read_bytes()
                                      for p in source.rglob('*') if p.is_file()})

    def test_cleanup_signals_group_even_after_parent_exits(self):
        process=Mock(pid=1234);process.wait.return_value=0
        with patch.object(gate.os,'killpg') as kill:
            gate.stop_group(process)
        self.assertEqual(kill.call_args_list[0].args,(1234,signal.SIGTERM))
        self.assertEqual(kill.call_args_list[1].args,(1234,signal.SIGKILL))

    def test_cleanup_reaps_real_owned_process(self):
        process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True)
        gate.stop_group(process)
        self.assertIsNotNone(process.poll())


if __name__ == '__main__': unittest.main()
