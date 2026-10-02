"""Inspect an authenticated retained frozen native producer without executing it."""
import argparse,datetime,hashlib,json,re,tarfile,zipfile
from pathlib import Path
SOURCE='e4bac7ff7260a5f395febc196b3e4792653e0ff81d7887d688e16ea0959aa361'
PROVENANCE='9fddb8002ebb49ad724dfeb20972066c1de0b75b22f806b5360609bb12eaaec5'
KIT='a3052d95c3de6d622157988a8e74826b2f0140724a634298458c3d75f6b508bd'
HEAD='c94da47247457f9e819c2682e74d34f5f1756f62'
RUN=36949324686

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def require(condition,message):
    if not condition:raise ValueError(message)

def inspect(root):
    root=root.resolve();p=root/'restored'
    retention=json.loads((root/'retention.json').read_text());api=json.loads((root/'api.json').read_text())
    require(retention['run_id']==RUN and retention['head_sha']==HEAD,'frozen runner selection differs')
    require(api['workflow_run']['id']==RUN and api['id']==retention['artifact_id'],'Actions API producer identity differs')
    digest=sha(root/'artifact.zip')
    require(digest==retention['archive_sha256'] and api['digest']=='sha256:'+digest,'authenticated ZIP digest differs')
    require((root/'artifact.zip').stat().st_size==retention['archive_bytes']==api['size_in_bytes'],'authenticated ZIP size differs')
    for item in retention['files']:
        path=p/item['path']
        require(path.resolve().is_relative_to(p.resolve()) and not path.is_symlink(),'unsafe retained member')
        require(path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'retained member identity differs: '+item['path'])
    require(not (p/'failure.txt').exists(),'producer retained a failure')
    archive=json.loads((p/'archive.json').read_text());candidate=json.loads((p/'candidate.json').read_text())
    target=archive['target'];toolchain=candidate['toolchain']
    require(api['name']=='candidate-'+target,'artifact target differs')
    require(archive['runner_revision']==HEAD and archive['source']['source_sha256']==SOURCE,'archive source/runner selection differs')
    require(archive['source']['selfhost_kit']['sha256']==KIT,'kit selection differs')
    require(candidate['provenance_sha256']==PROVENANCE,'candidate source provenance differs')
    require(toolchain.startswith('rustc 1.89.0 ') and 'release: 1.89.0\n' in toolchain and 'host: '+target+'\n' in toolchain,'actual native Rust 1.89 required')
    binary=p/archive['archive'];require(binary.parent==p and sha(binary)==archive['sha256'],'binary package identity differs')
    if binary.suffix=='.zip':
        with zipfile.ZipFile(binary) as content:packaged=content.read('cyber-tools/candidate.json')
    else:
        with tarfile.open(binary) as content:packaged=content.extractfile('cyber-tools/candidate.json').read()
    expected_candidate={key:value for key,value in candidate.items() if key!='source'}
    require(json.loads(packaged)==expected_candidate,'packaged candidate differs from documented portable inventory')
    cpu={}
    for component in ('trident','trisha','joy'):
        path=p/(component+'-tests.log');data=path.read_text(errors='strict')
        summaries=re.findall(r'^test result:.*$',data,re.M)
        require(summaries and all(line.startswith('test result: ok.') and '; 0 failed;' in line for line in summaries),component+' CPU suite failed')
        require(not re.search(r'^warning(?:\[|:)',data,re.M),component+' emitted a Rust warning')
        cpu[component]=dict(log_sha256=sha(path),test_binaries=len(summaries),passed=sum(map(int,re.findall(r'^test result: ok\. (\d+) passed;',data,re.M))))
    for path in p.glob('candidate-*-build.log'):
        require(not re.search(r'^warning(?:\[|:)',path.read_text(errors='strict'),re.M),'candidate build emitted a Rust warning')
    baseline=json.loads((p/'baseline-execution.json').read_text())
    require(baseline['all_checks_passed'] is True and baseline['target']==target and baseline['source_provenance_sha256']==PROVENANCE,'baseline execution receipt differs')
    require((baseline['baselines'],baseline['positive_fixtures'],baseline['negative_fixtures'],baseline['generated_proofs'])==(43,99,34,0),'baseline execution coverage differs')
    require(baseline['candidate_sha256']==sha(p/'candidate.json') and baseline['log_sha256']==sha(p/'baseline-execution.log'),'baseline identity differs')
    gates={}
    for name,field in [('installed-selfhost-smoke/receipt.json','status'),('unpacked-selfhost-smoke/receipt.json','status'),('joy-native-smoke/receipt.json','status'),('native-process-files.json','all_checks_passed'),('proof-corpus/smoke.json','all_checks_passed'),('local-corpus-verification.json','all_checks_passed')]:
        data=json.loads((p/name).read_text());require(data[field]==('passed' if field=='status' else True),name+' did not pass');gates[name]=sha(p/name)
    corpus=json.loads((p/'proof-corpus/corpus.json').read_text());verified=json.loads((p/'local-corpus-verification.json').read_text())
    require(corpus['source_provenance_sha256']==PROVENANCE and len(corpus['cases'])==47,'corpus source or cases differ')
    require(verified['corpus_sha256']==sha(p/'proof-corpus/corpus.json') and len(verified['cases'])==47,'corpus verifier identity differs')
    corpus_package=p/('proof-corpus-'+target+'.tar.gz')
    with tarfile.open(corpus_package) as content:require(content.extractfile('proof-corpus/corpus.json').read()==(p/'proof-corpus/corpus.json').read_bytes(),'corpus package differs')
    for name,test in [('neptune-client.log','genuine_transaction_prepare_and_mock_gateway_process'),('neptune-binding.log','genuine_custom_lock_transaction_and_binding_mutations')]:
        data=(p/name).read_text();require('test '+test+' ... ok' in data and 'test result: ok. 1 passed; 0 failed;' in data,name+' did not pass');gates[name]=sha(p/name)
    require('PASS: installed LSP initialize/shutdown/exit' in (p/'unpacked-lsp.log').read_text(),'unpacked LSP did not pass')
    return dict(scope='Frozen e4bac7ff feature-branch rehearsal; single native producer receipt inspection, whole matrix and full 198-proof gate separate',
        status='producer_receipts_checked',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),run_id=RUN,runner_revision=HEAD,target=target,
        artifact_id=api['id'],artifact_sha256=digest,retained_files=len(retention['files']),source_sha256=SOURCE,kit_sha256=KIT,source_provenance_sha256=PROVENANCE,
        platform=archive['platform'],actual_rustc=toolchain,cargo_version_observation='not separately recorded by frozen producer',
        cpu=cpu,gates=gates,baseline_execution=baseline,corpus_cases=47,corpus_positive=sum(row['exit_code']==0 for row in verified['cases']),corpus_rejections=sum(row['exit_code']!=0 for row in verified['cases']),
        binary_archive=dict(name=binary.name,sha256=sha(binary),bytes=binary.stat().st_size),corpus_archive=dict(name=corpus_package.name,sha256=sha(corpus_package),bytes=corpus_package.stat().st_size),
        inspector_sha256=sha(Path(__file__)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('retained',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    result=inspect(args.retained)
    with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','target','artifact_id','cpu','corpus_cases','corpus_positive','corpus_rejections')},indent=2))
