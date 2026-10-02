"""Inspect an authenticated retained final native producer without executing it."""
import argparse,datetime,hashlib,json,re,tarfile,zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
SOURCE='73b50ebdd451908ca6da801a0c30b81ae6a9bc053e98cb8449db9a209b11f3f8'
PROVENANCE='9334dead92b990a12acf16a2565aeb762a07311dfc2c3d6cb896c0490dc5926e'
KIT='a3052d95c3de6d622157988a8e74826b2f0140724a634298458c3d75f6b508bd'
HEAD=None
RUN=None

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def require(condition,message):
    if not condition:raise ValueError(message)


INPUTS='6a9e9af007de7f1d3dca6cb078080270cb4b96057db182f9c64775d063d6e767'
IMPACT='a80578694041fe432df21819b166140165fe98d27ff3d0a6dcfb8a9621faa86d'
HELPER='5caa737b7c7b8b1fef0dd024a56e78f394273b8140b12a1832f29c8dad891a94'
WINDOWS_IMPACT='a80578694041fe432df21819b166140165fe98d27ff3d0a6dcfb8a9621faa86d'
WINDOWS_HELPER='e64ac2ee0e34d3de9e7acde94f839363f7c91f62b90e08f2a923e055421ddaf4'
BASES=('add14','identity_tree','loop4097','compiler-success','compiler-diagnostic')
RULES={name+'-'+suffix:(0 if suffix=='valid' else 1,'result') for name in BASES for suffix in ('valid','wrong-input','wrong-program','truncated','corrupt')}
RULES.update({'compiler-success-extract':(0,'program'),'compiler-diagnostic-extract':(1,'program')})
def additional(p,candidate,target,archive,packaged):
    # Exact script bytes from the pinned runner commit after native Git checkout.
    # The Windows image uses core.autocrlf=true; no source archive bytes change.
    impact_digest=WINDOWS_IMPACT if 'windows' in target else IMPACT
    helper_digest=WINDOWS_HELPER if 'windows' in target else HELPER
    require(archive['source']['validation_profile']=='final-host-ceiling-v1' and archive['source']['inputs_sha256']==INPUTS,'current profile or input selector differs')
    tools=json.loads((p/'toolchain-paths.json').read_text())
    require(set(tools)=={'rustc','cargo','rustdoc'},'all three actual Rust tools required')
    path_type=PureWindowsPath if 'windows' in target else PurePosixPath
    require(len({path_type(row['path']).parent for row in tools.values()})==1,'actual Rust tool paths differ')
    for name,row in tools.items():
        require(row['version'].startswith(name+' 1.89.0 ') and row['version']==(p/(name+'.log')).read_text(),'actual '+name+' observation differs')
        require(re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None,'actual Rust tool digest missing')
    require(tools['rustc']['version']==candidate['toolchain'],'candidate and actual toolchain differ')
    impact=json.loads((p/'source-impact.json').read_text())
    require(impact['status']=='passed' and impact['source_provenance_sha256']==PROVENANCE and impact['selector_sha256']==INPUTS and impact['script_sha256']==impact_digest,'current source-impact identity differs')
    require(len(impact['protected_non_joy'])==10 and len({row['repository'] for row in impact['protected_non_joy']})==10 and impact['joy_commit']=='dd61df9128f6da1f97d4698f45f154f05312fe51' and impact['joy_production_changes']==['rs/structured/limits.rs'],'source impact closure differs')
    root=p/'structured-corpus';manifest=json.loads((root/'corpus.json').read_text());generation=json.loads((root/'generation.json').read_text());verified=json.loads((p/'local-structured-verification.json').read_text())
    joy=next(row for row in candidate['binaries'] if row['name']=='joy')
    require(manifest['source_provenance_sha256']==generation['source_provenance_sha256']==verified['source_provenance_sha256']==PROVENANCE,'structured source identity differs')
    require(manifest['producer_joy_sha256']==generation['producer_joy']['sha256']==verified['producer_joy_sha256']==verified['consumer_joy']['sha256']==joy['sha256'],'structured Joy identity differs')
    require(generation['status']=='passed' and generation['script_sha256']==verified['verifier_sha256']==helper_digest,'structured helper identity or generation failed')
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
    deadline=deadline_probe(p,candidate,packaged,helper_digest)
    return dict(installed_deadline=deadline,actual_tools=tools,script_checkout=dict(impact_line_endings='LF',structured_helper_line_endings='CRLF' if 'windows' in target else 'LF',impact_sha256=impact_digest,structured_helper_sha256=helper_digest,runner_revision=HEAD),source_impact_sha256=sha(p/'source-impact.json'),structured_cases=27,structured_accepted=6,structured_rejected=21,structured_archive=dict(name=corpus.name,sha256=sha(corpus),bytes=corpus.stat().st_size))

def deadline_probe(p,candidate,packaged,structured_helper):
    root=p/'installed-host-ceiling';report=json.loads((root/'receipt.json').read_text())
    joy=next(row['sha256'] for row in candidate['binaries'] if row['name']=='joy')
    require(report['status']=='passed' and report['accepted']==15 and report['rejected']==8,'installed deadline probe failed')
    require(report['joy']['sha256']==joy and report['source_provenance_sha256']==PROVENANCE and report['candidate_sha256']==hashlib.sha256(packaged).hexdigest(),'installed deadline candidate identity differs')
    require(report['script_sha256']=='20c434ab117fe2e54e7e1a80e39f232fac4ef32f92803326bf9213e78fceebf7' and report['helper_sha256']==structured_helper and report['fixture']['sha256']=='4b118cd9c9f20764e46b16676d4cb63599dc40c7e8f3a40a47c4fe5962f752ad','installed deadline script/fixture identity differs')
    expected={}
    for producer in ('30000','7200000','14400000'):
        expected['prove-'+producer]=0
        for verifier in ('30000','7200000','14400000'):expected['verify-'+producer+'-'+verifier]=0
    expected['compiled-program-run']=0
    for operation in ('prove-artifact','verify-artifact'):
        for limit in ('0','14400001','18446744073709551615'):expected[operation+'-invalid-'+limit]=1
    expected.update({'ordinary-prove-limit':0,'ordinary-verify-limit':0,'prove-artifact-ordinary-over-limit':1,'verify-artifact-ordinary-over-limit':1})
    require(len(report['commands'])==23 and {row['name']:row['expected_exit'] for row in report['commands']}==expected,'installed deadline case map differs')
    for row in report['commands']:
        require(row['exit_code']==expected[row['name']],'installed deadline command outcome differs')
        for stream in ('stdout','stderr'):
            item=row[stream];path=root/'commands'/item['path'];require(path.resolve().is_relative_to(root.resolve()) and path.is_file() and not path.is_symlink(),'unsafe deadline stream path');require(path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'installed deadline original stream differs')
    proof_hashes={sha(root/('proof-'+ms)) for ms in ('30000','7200000','14400000')}
    require(proof_hashes=={report['proof_sha256']},'producer deadline changed certificate bytes')
    claims=[]
    for producer in ('30000','7200000','14400000'):
        for verifier in ('30000','7200000','14400000'):
            claim=json.loads((root/'commands'/('verify-'+producer+'-'+verifier+'.stdout')).read_text())['verification'];claim.pop('elapsed_micros',None);require(claim['physical_resource_claim']=='unattested' and claim.get('prover_observations') is None,'deadline claim unexpectedly attests resources');claims.append(claim)
    require(all(claim==claims[0] for claim in claims),'producer/verifier host deadline changed claims')
    require((root/'compiled').read_bytes()==(root/'generated').read_bytes()==(root/'ordinary-result').read_bytes() and (root/'result').read_bytes()==(root/'fourteen').read_bytes(),'deadline extracted or executed output differs')
    require((root/'destination').read_bytes()==b'previous destination','deadline rejection replaced output')
    return dict(receipt_sha256=sha(root/'receipt.json'),accepted=15,rejected=8,producer_deadlines=3,verifier_combinations=9,proof_sha256=report['proof_sha256'])

def container(root,run,head):
    """Bind restored bytes directly to every authenticated original ZIP member."""
    root=root.resolve();p=root/'restored'
    retention=json.loads((root/'retention.json').read_text());api=json.loads((root/'api.json').read_text())
    require(retention['run_id']==run and retention['head_sha']==head,'runner selection differs')
    require(api['workflow_run']['id']==run and api['id']==retention['artifact_id'],'Actions API identity differs')
    digest=sha(root/'artifact.zip')
    require(digest==retention['archive_sha256'] and api['digest']=='sha256:'+digest,'authenticated ZIP digest differs')
    require((root/'artifact.zip').stat().st_size==retention['archive_bytes']==api['size_in_bytes'],'authenticated ZIP size differs')
    rows=retention['files'];mapping={row['path']:row for row in rows}
    require(len(mapping)==len(rows),'duplicate retained file')
    require({q.relative_to(p).as_posix() for q in p.rglob('*') if q.is_file()}==mapping.keys(),'retained file inventory differs')
    with zipfile.ZipFile(root/'artifact.zip') as content:
        names=set()
        for member in content.infolist():
            require(member.filename not in names,'duplicate original ZIP member');names.add(member.filename)
            path=p/member.filename
            require(path.resolve().is_relative_to(p.resolve()) and not path.is_symlink(),'unsafe original ZIP member')
            require((member.external_attr >> 16)&0o170000!=0o120000,'original ZIP symlink')
            if member.is_dir():continue
            raw=content.read(member);item=mapping.get(member.filename)
            require(item is not None and item['bytes']==len(raw)==path.stat().st_size,'original/retained member size differs')
            require(item['sha256']==hashlib.sha256(raw).hexdigest()==sha(path),'original/retained member bytes differ')
        require({x.filename for x in content.infolist() if not x.is_dir()}==mapping.keys(),'original ZIP file inventory differs')
    return api,retention,digest

def package_candidate(binary,candidate,target):
    require(len(candidate['binaries'])==4 and {row['name'] for row in candidate['binaries']}=={'trident','trident-lsp','trisha','joy'},'exact four packaged binaries required')
    content=zipfile.ZipFile(binary) if binary.suffix=='.zip' else tarfile.open(binary)
    with content:
        def read(name):
            if binary.suffix=='.zip':return content.read(name)
            member=content.getmember(name)
            require(member.isfile(),'packaged executable/metadata is not a regular file')
            return content.extractfile(member).read()
        packaged=read('cyber-tools/candidate.json')
        for row in candidate['binaries']:
            raw=read('cyber-tools/bin/'+row['name']+('.exe' if 'windows' in target else ''))
            require(hashlib.sha256(raw).hexdigest()==row['sha256'],'packaged executable differs from tested inventory')
    expected_candidate={key:value for key,value in candidate.items() if key!='source'}
    require(json.loads(packaged)==expected_candidate,'packaged candidate differs from documented portable inventory')
    return packaged

def inspect(root):
    require(isinstance(RUN,int) and RUN>0 and re.fullmatch('[0-9a-f]{40}',HEAD or '') is not None,'explicit final producer run/head selection required')
    root=root.resolve();p=root/'restored'
    api,retention,digest=container(root,RUN,HEAD)
    require(not (p/'failure.txt').exists(),'producer retained a failure')
    archive=json.loads((p/'archive.json').read_text());candidate=json.loads((p/'candidate.json').read_text())
    target=archive['target'];toolchain=candidate['toolchain']
    require(api['name']=='candidate-'+target,'artifact target differs')
    require(archive['runner_revision']==HEAD and archive['source']['source_sha256']==SOURCE,'archive source/runner selection differs')
    require(archive['source']['selfhost_kit']['sha256']==KIT,'kit selection differs')
    require(candidate['provenance_sha256']==PROVENANCE,'candidate source provenance differs')
    require(toolchain.startswith('rustc 1.89.0 ') and 'release: 1.89.0\n' in toolchain and 'host: '+target+'\n' in toolchain,'actual native Rust 1.89 required')
    binary=p/archive['archive'];require(binary.parent==p and sha(binary)==archive['sha256'],'binary package identity differs')
    packaged=package_candidate(binary,candidate,target)
    cpu={}
    for component in ('trident','trisha','joy','nox'):
        path=p/(component+'-tests.log');data=path.read_text(errors='strict')
        summaries=re.findall(r'^test result:.*$',data,re.M)
        require(summaries and all(line.startswith('test result: ok.') and '; 0 failed;' in line for line in summaries),component+' CPU suite failed')
        require(not re.search(r'^warning(?:\[|:)',data,re.M),component+' emitted a Rust warning')
        cpu[component]=dict(log_sha256=sha(path),test_binaries=len(summaries),passed=sum(map(int,re.findall(r'^test result: ok\. (\d+) passed;',data,re.M))))
        if component=='joy':
            for test in ('structured::tests::compaction::explicit_compaction_deadlines_preserve_defaults_and_cancellation','structured::tests::compiler::compaction::compiler_job_binding_and_extracted_artifact_survive_repeated_collection'):
                require('test '+test+' ... ok' in data,'actual final deadline CPU regression missing: '+test)
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
    extra=additional(p,candidate,target,archive,packaged)
    return dict(scope='Final 73b50ebd feature-branch rehearsal; single native producer receipt inspection, whole matrix and full 198-proof gate separate',
        status='producer_receipts_checked',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),run_id=RUN,runner_revision=HEAD,target=target,
        artifact_id=api['id'],artifact_sha256=digest,retained_files=len(retention['files']),source_sha256=SOURCE,kit_sha256=KIT,source_provenance_sha256=PROVENANCE,
        platform=archive['platform'],actual_rustc=toolchain,cargo_version_observation='actual native Rust, Cargo and rustdoc 1.89 recorded',**extra,
        cpu=cpu,gates=gates,baseline_execution=baseline,corpus_cases=47,corpus_positive=sum(row['exit_code']==0 for row in verified['cases']),corpus_rejections=sum(row['exit_code']!=0 for row in verified['cases']),
        binary_archive=dict(name=binary.name,sha256=sha(binary),bytes=binary.stat().st_size),corpus_archive=dict(name=corpus_package.name,sha256=sha(corpus_package),bytes=corpus_package.stat().st_size),
        inspector_sha256=sha(Path(__file__)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('retained',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--run-id',type=int,required=True);parser.add_argument('--head',required=True);args=parser.parse_args();RUN=args.run_id;HEAD=args.head
    result=inspect(args.retained)
    with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','target','artifact_id','cpu','corpus_cases','corpus_positive','corpus_rejections')},indent=2))
