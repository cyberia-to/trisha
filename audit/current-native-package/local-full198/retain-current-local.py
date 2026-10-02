from pathlib import Path
import gzip,hashlib,importlib.util,json,re,tarfile
R=Path(__file__).resolve().parent.parent;L=R/'local-macos-current-rust189';P=L/'release-results';O=R/'measurements/local-rust189-complete';O.mkdir()
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(path):return json.loads(path.read_text())
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
transport=module('package_guard',R/'measurements/upload-current-local-packages.py');archive,candidate,binary,corpus=transport.guard()
driver=load(L/'driver.json');assert driver['status']=='passed' and driver['exit_code']==0 and driver['resource_stopped'] is False
baseline=P/'baselines';receipt=load(baseline/'receipt.json');started=load(baseline/'started.json')
assert receipt['all_checks_passed'] is True and receipt['exit_code']==0 and receipt['guard_stop'] is None and receipt['inputs_unchanged'] is True
assert receipt['source_provenance_sha256']==candidate['provenance_sha256']==transport.PROVENANCE
assert receipt['binaries']=={r['name']:r['sha256'] for r in candidate['binaries']}
assert started['candidate']==candidate and receipt['started_sha256']==sha(baseline/'started.json') and receipt['log_sha256']==sha(baseline/'bench.log')
checker=Path(candidate['source'])/'trisha/scripts/check-baselines.py';assert sha(checker)==started['script_sha256']
events=module('baselines',checker).checked_log((baseline/'bench.log').read_text(),started['fixtures'],len(started['baselines']))
assert len(events)==receipt['fresh_verified_proofs']==198 and events==receipt['verified_proof_events']
assert receipt['positive_fixtures_passed']==99 and receipt['negative_fixtures_rejected']==34
samples=[json.loads(line) for line in (baseline/'memory.jsonl').read_text().splitlines()]
assert max(row['rss_bytes'] for row in samples)==receipt['peak_rss_bytes']<=started['rss_limit_bytes']==28*1024**3
assert all(row['memory_free_percent'] is None or row['memory_free_percent']>=8 for row in samples)
cpu={}
for name in ['trident','trisha','joy','nox']:
 data=(P/(name+'-tests.log')).read_text();summaries=re.findall(r'^test result:.*$',data,re.M)
 assert summaries and all(row.startswith('test result: ok.') and '; 0 failed;' in row for row in summaries)
 assert not re.search(r'^warning(?:\[|:)',data,re.M)
 cpu[name]=dict(passed=sum(map(int,re.findall(r'^test result: ok\. (\d+) passed;',data,re.M))),test_binaries=len(summaries),log_sha256=sha(P/(name+'-tests.log')))
for name,field in [('installed-selfhost-smoke/receipt.json','status'),('unpacked-selfhost-smoke/receipt.json','status'),('joy-native-smoke/receipt.json','status'),('native-process-files.json','all_checks_passed'),('proof-corpus/smoke.json','all_checks_passed'),('local-corpus-verification.json','all_checks_passed')]:
 data=load(P/name);assert data[field]==('passed' if field=='status' else True)
assert 'PASS: installed LSP initialize/shutdown/exit' in (P/'unpacked-lsp.log').read_text()
for name,test in [('neptune-client.log','genuine_transaction_prepare_and_mock_gateway_process'),('neptune-binding.log','genuine_custom_lock_transaction_and_binding_mutations')]:
 data=(P/name).read_text();assert 'test '+test+' ... ok' in data and 'test result: ok. 1 passed; 0 failed;' in data
execution=load(P/'baseline-execution.json');assert execution['all_checks_passed'] is True and (execution['baselines'],execution['positive_fixtures'],execution['negative_fixtures'],execution['generated_proofs'])==(43,99,34,0)
assert len(load(P/'local-corpus-verification.json')['cases'])==47
paths=[p for p in sorted(P.rglob('*')) if p.is_file()]
paths += [p for p in sorted(L.iterdir()) if p.is_file()]
paths += [L/'.github/release-candidate.json',L/'.github/current-package-inputs.json',L/'scripts/native-candidate.py',L/'scripts/current-source-impact.py',L/'scripts/current-structured-corpus.py']
paths += [p for p in sorted((L/'audit/current-native-package/references').rglob('*')) if p.is_file()]
files=[dict(path=p.relative_to(L).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in paths]
package=O/'rehearsal-20261002-734df69d-local-rust189-evidence.tar.gz'
with package.open('xb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as zipped,tarfile.open(fileobj=zipped,mode='w') as tar:
 for row,p in zip(files,paths):
  info=tarfile.TarInfo(row['path']);info.size=row['bytes'];info.mode=0o644
  with p.open('rb') as stream:tar.addfile(info,stream)
for row,p in zip(files,paths):assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes']
report=dict(scope='Complete actual current 734df69d Mac ARM native producer and198 proof gate; cross-consumer matrix separate',status='passed',source_sha256=transport.SOURCE,source_provenance_sha256=transport.PROVENANCE,kit_sha256=transport.KIT,runner_revision=driver['bootstrap_revision'],candidate_sha256=sha(P/'candidate.json'),binaries=receipt['binaries'],cpu=cpu,proof_gate={key:receipt[key] for key in ['all_checks_passed','fresh_verified_proofs','positive_fixtures_passed','negative_fixtures_rejected','inputs_unchanged','elapsed_seconds','peak_rss_bytes','started_sha256','log_sha256']},driver_elapsed_seconds=driver['elapsed_seconds'],outer_build_smoke_process_group_peak_bytes=driver['peak_process_group_rss_bytes'],resource_scope='Outer build/smoke and inner proof process groups measured separately',archive=dict(path=package.name,bytes=package.stat().st_size,sha256=sha(package)),files=files,retainer_sha256=sha(Path(__file__)))
(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))
