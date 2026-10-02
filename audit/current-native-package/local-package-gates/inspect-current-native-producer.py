"""Inspect an authenticated retained current native producer without executing it."""
import argparse,datetime,hashlib,json,re,tarfile,zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
SOURCE='734df69dc7d43467fc9ae574c7cf7b25eb9b4ec9bc08e9ca3f96b9500131f42e'
PROVENANCE='3c6f2ced084812e73f97c069169f83807fc5d389e54b581dd52f10982cd5b227'
KIT='a3052d95c3de6d622157988a8e74826b2f0140724a634298458c3d75f6b508bd'
HEAD='ecdc4e2ea131c50a860036e34ee7636b91fb8dde'
RUN=36969168806

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def require(condition,message):
    if not condition:raise ValueError(message)


INPUTS='e8e03c81f97d6aa5f7b3ab23faca44e058a2bd13dcf1228ffde1c81edb75619f'
IMPACT='cffe213b0f0d0930c7d5c13d57cf97eecc3165d84662f7f8e30df0a07b005942'
HELPER='5caa737b7c7b8b1fef0dd024a56e78f394273b8140b12a1832f29c8dad891a94'
BASES=('add14','identity_tree','loop4097','compiler-success','compiler-diagnostic')
RULES={name+'-'+suffix:(0 if suffix=='valid' else 1,'result') for name in BASES for suffix in ('valid','wrong-input','wrong-program','truncated','corrupt')}
RULES.update({'compiler-success-extract':(0,'program'),'compiler-diagnostic-extract':(1,'program')})
def additional(p,candidate,target,archive):
    require(archive['source']['validation_profile']=='current-package-v1' and archive['source']['inputs_sha256']==INPUTS,'current profile or input selector differs')
    tools=json.loads((p/'toolchain-paths.json').read_text())
    require(set(tools)=={'rustc','cargo','rustdoc'},'all three actual Rust tools required')
    path_type=PureWindowsPath if 'windows' in target else PurePosixPath
    require(len({path_type(row['path']).parent for row in tools.values()})==1,'actual Rust tool paths differ')
    for name,row in tools.items():
        require(row['version'].startswith(name+' 1.89.0 ') and row['version']==(p/(name+'.log')).read_text(),'actual '+name+' observation differs')
        require(re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None,'actual Rust tool digest missing')
    require(tools['rustc']['version']==candidate['toolchain'],'candidate and actual toolchain differ')
    impact=json.loads((p/'source-impact.json').read_text())
    require(impact['status']=='passed' and impact['source_provenance_sha256']==PROVENANCE and impact['selector_sha256']==INPUTS and impact['checker_sha256']==IMPACT,'current source-impact identity differs')
    require(len(impact['comparisons'])==11 and len({row['repository'] for row in impact['comparisons']})==11,'source impact closure differs')
    root=p/'structured-corpus';manifest=json.loads((root/'corpus.json').read_text());generation=json.loads((root/'generation.json').read_text());verified=json.loads((p/'local-structured-verification.json').read_text())
    joy=next(row for row in candidate['binaries'] if row['name']=='joy')
    require(manifest['source_provenance_sha256']==generation['source_provenance_sha256']==verified['source_provenance_sha256']==PROVENANCE,'structured source identity differs')
    require(manifest['producer_joy_sha256']==generation['producer_joy']['sha256']==verified['producer_joy_sha256']==verified['consumer_joy']['sha256']==joy['sha256'],'structured Joy identity differs')
    require(generation['status']=='passed' and generation['script_sha256']==verified['verifier_sha256']==HELPER,'structured helper identity or generation failed')
    require(verified['status']=='passed' and verified['all_checks_passed'] is True and verified['corpus_sha256']==sha(root/'corpus.json'),'structured verification did not pass')
    require(len(manifest['cases'])==27 and {row['id']:(row['expected_exit'],row['emit']) for row in manifest['cases']}==RULES,'exact structured case map differs')
    require(verified['cases']==[dict(id=row['id'],exit_code=row['expected_exit']) for row in manifest['cases']],'structured verification cases differ')
    files=manifest['files'];require(len({row['path'] for row in files})==len(files),'duplicate structured file')
    require({path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file()}=={row['path'] for row in files}|{'corpus.json'},'structured file set differs')
    for row in files:
        path=root/row['path'];require(path.resolve().is_relative_to(root.resolve()) and not path.is_symlink(),'unsafe structured file')
        require(path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],'structured file bytes differ')
    for report,evidence in [(generation,root/'generation'),(verified,p/'local-structured-verification')]:
        for row in report['commands']:
            require(row['exit_code']==row['expected_exit'],'structured command failed')
            for stream in ('stdout','stderr'):
                item=row[stream];path=evidence/item['path'];require(path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'structured command evidence differs')
    corpus=p/('structured-corpus-'+target+'.tar.gz')
    with tarfile.open(corpus) as content:require(content.extractfile('structured-corpus/corpus.json').read()==(root/'corpus.json').read_bytes(),'structured corpus package differs')
    return dict(actual_tools=tools,source_impact_sha256=sha(p/'source-impact.json'),structured_cases=27,structured_accepted=6,structured_rejected=21,structured_archive=dict(name=corpus.name,sha256=sha(corpus),bytes=corpus.stat().st_size))

def inspect(root):
    root=root.resolve();p=root/'restored'
    retention=json.loads((root/'retention.json').read_text());api=json.loads((root/'api.json').read_text())
    require(retention['run_id']==RUN and retention['head_sha']==HEAD,'current runner selection differs')
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
    for component in ('trident','trisha','joy','nox'):
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
    extra=additional(p,candidate,target,archive)
    return dict(scope='Current 734df69d feature-branch rehearsal; single native producer receipt inspection, whole matrix and full 198-proof gate separate',
        status='producer_receipts_checked',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),run_id=RUN,runner_revision=HEAD,target=target,
        artifact_id=api['id'],artifact_sha256=digest,retained_files=len(retention['files']),source_sha256=SOURCE,kit_sha256=KIT,source_provenance_sha256=PROVENANCE,
        platform=archive['platform'],actual_rustc=toolchain,cargo_version_observation='actual native Rust, Cargo and rustdoc 1.89 recorded',**extra,
        cpu=cpu,gates=gates,baseline_execution=baseline,corpus_cases=47,corpus_positive=sum(row['exit_code']==0 for row in verified['cases']),corpus_rejections=sum(row['exit_code']!=0 for row in verified['cases']),
        binary_archive=dict(name=binary.name,sha256=sha(binary),bytes=binary.stat().st_size),corpus_archive=dict(name=corpus_package.name,sha256=sha(corpus_package),bytes=corpus_package.stat().st_size),
        inspector_sha256=sha(Path(__file__)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('retained',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    result=inspect(args.retained)
    with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','target','artifact_id','cpu','corpus_cases','corpus_positive','corpus_rejections')},indent=2))
