"""Replay authenticated original Actions members and native command claims."""
import json
from pathlib import PurePosixPath
import re

from common import CHUNK, identity, load, require, unique
from contracts import common_remote, ident, semantics

BASE = '/home/runner/work/_temp'
HOST = ['--arena-nodes', '1000000000', '--budget', '20000000000', '--frames', '65536', '--time-ms', '7200000',
        '--validation-visits', '16777216', '--resident-nodes', '3145728', '--collection-work', '10000000000']
PROOF = ['--proof-bytes', str(24*CHUNK), '--proof-decoded-bytes', str(96*CHUNK), '--proof-records', '12000000000',
         '--proof-steps', '16000000000', '--proof-cache-slots', '262144']
SDK = ['/usr/local/lib/android', '/usr/share/dotnet', '/opt/ghc', '/usr/local/.ghcup',
       '/usr/local/share/powershell', '/usr/local/share/boost', '/usr/share/swift', '/usr/lib/jvm',
       '/opt/hostedtoolcache/CodeQL', '/opt/hostedtoolcache/go', '/opt/hostedtoolcache/Java_Temurin-Hotspot_jdk',
       '/opt/hostedtoolcache/Java_Adopt_jdk', '/opt/hostedtoolcache/Ruby']


def no_failure(value):
    require(not any(k in value for k in ('error', 'resource_stop', 'orphan_group')), 'no failed or partial command')


def phase_paths(generation, phase):
    work = f'{BASE}/whole-v2-{phase}-c{generation}'
    return dict(work=work, binary=work+'/target/release/joy', compiler=work+f'/frozen/inputs/c{generation}.dag',
                job=work+f'/frozen/inputs/c{generation}-job.dag', proof=work+('/producer/proof.joysc' if phase == 'producer' else '/download/certificate.joysc'),
                family=work+'/family', results=BASE+f'/whole-v2-{phase}-results')


def exact_command(row, argv, cwd):
    require(row['command'] == argv and row['cwd'] == cwd and row['exit_code'] == 0, 'exact successful argv/cwd')
    require(type(row['elapsed_ns']) is int and row['elapsed_ns'] > 0 and type(row['started_ns']) is int, 'actual command clocks')
    no_failure(row)


def raw_commands(evidence, receipt, paths, expected):
    rows = receipt['commands']; names = [r['name'] for r in rows]
    require(len(names) == len(set(names)) and len(names) <= 250, 'bounded unique preparation commands')
    result = {r['name']: r for r in rows}
    for row in rows:
        name = row['name']; require(re.fullmatch('[a-z0-9.-]+', name), 'simple command name')
        require(row['exit_code'] == 0, 'preparation command success'); no_failure(row)
        for field in ('stdout', 'stderr'):
            expected_path = paths['results'] + '/' + name + '.' + field
            if name == 'input-download' and field == 'stdout':
                require(row[field] == dict(path=paths['work']+'/'+expected['input_asset']['name'], **ident(expected['input_asset'])), 'input download exact bytes')
                continue
            require(row[field]['path'] == expected_path and identity(evidence / (name+'.'+field)) == ident(row[field]), 'raw original preparation log')
            require(not re.search(rb'^warning(?:\[[^\]\r\n]+\])?:', (evidence / (name+'.'+field)).read_bytes(), re.M), 'zero warning preparation')
    return result


def source_commands(evidence, receipt, paths, expected, rows, want):
    final = 'produced' if receipt['phase'] == 'producer' else 'verified'
    inventories = {suffix: load(evidence / f'sources-{suffix}.json') for suffix in ('before', 'prepared', final)}
    require(inventories['before'] == inventories['prepared'] == inventories[final], 'complete source inventory unchanged')
    require(receipt['source_inventory_identities'] == {f'sources-{s}.json': identity(evidence / f'sources-{s}.json') for s in inventories}, 'all source inventory byte bindings')
    sources = expected['source_selector']['sources']
    require(set(inventories['before']) == set(sources), 'exact 12 source repositories')
    for name, revision in sources.items():
        dest = paths['family']+'/'+name
        commands = {'init':['git','init',dest], 'origin':['git','-C',dest,'remote','add','origin','https://github.com/cyberia-to/'+name+'.git'],
                    'fetch':['git','-C',dest,'fetch','--depth=1','origin',revision], 'checkout':['git','-C',dest,'checkout','--detach','FETCH_HEAD'],
                    'head':['git','-C',dest,'rev-parse','HEAD']}
        commands.update({'core.'+key:['git','-C',dest,'config','core.'+key,value] for key,value in [('autocrlf','false'),('eol','lf'),('symlinks','true')]})
        for suffix, argv in commands.items():
            key=name+'-'+suffix; want.add(key); exact_command(rows[key],argv,paths['work'])
        require((evidence/(name+'-head.stdout')).read_text().strip() == revision, 'actual fetched source head')
        recorded = inventories['before'][name]
        require(recorded['commit'] == revision and recorded['files'], 'source inventory pinned commit')
        files = recorded['files']; require(len({f['path'] for f in files}) == len(files), 'unique tracked inventory')
        for suffix in inventories:
            for kind, tail in [('status',['status','--porcelain=v1','--untracked-files=all']),('files',['ls-files','--stage','-z'])]:
                key=f'{name}-{kind}-{suffix}'; want.add(key); exact_command(rows[key],['git','-C',dest,*tail],paths['work'])
            require(not (evidence/f'{name}-status-{suffix}.stdout').read_bytes(), 'clean complete source status')
            listing = (evidence/f'{name}-files-{suffix}.stdout').read_text()
            require(listing == ''.join(f"{f['mode']} {f['git_blob']} 0\t{f['path']}\0" for f in files), 'exact Git tracked inventory raw listing')


def preparation_commands(evidence, receipt, paths, expected):
    rows = raw_commands(evidence, receipt, paths, expected); want = set()
    def check(name, argv, cwd=None):
        want.add(name); exact_command(rows[name], argv, cwd or paths['work'])
    checkout='/home/runner/work/trisha/trisha'
    check('bootstrap-head',['git','rev-parse','HEAD'],checkout)
    check('bootstrap-status',['git','status','--porcelain=v1','--untracked-files=all'],checkout)
    require((evidence/'bootstrap-head.stdout').read_text().strip() == expected['run']['head'] and
            not (evidence/'bootstrap-status.stdout').read_bytes(), 'clean reviewed bootstrap head')
    cleanup=load(evidence/'disk-cleanup.json')
    require(cleanup['allowlist'] == SDK and len(set(cleanup['removed'])) == len(cleanup['removed']) and set(cleanup['removed']) <= set(SDK), 'explicit cleanup allowlist')
    for name in cleanup['removed']:
        check('remove-unused-sdk-'+str(SDK.index(name)),['/usr/bin/sudo','/bin/rm','-rf','--',name])
    endpoint=f"repos/cyberia-to/trisha/releases/assets/{expected['input_asset']['asset_id']}"
    check('input-metadata',['gh','api',endpoint]); check('input-download',['gh','api',endpoint,'-H','Accept: application/octet-stream'])
    require(load(evidence/'input-metadata.stdout') == receipt['input_asset_metadata'], 'input server raw metadata')
    input_meta=receipt['input_asset_metadata']; asset=expected['input_asset']
    require(all(input_meta[k] == asset[v] for k,v in [('id','asset_id'),('name','name'),('size','bytes')]) and input_meta['digest']=='sha256:'+asset['sha256'], 'immutable input metadata')
    source_commands(evidence,receipt,paths,expected,rows,want)
    toolchain='1.89.0-x86_64-unknown-linux-gnu'
    rustup=rows['install-rust']['command'][0]
    require(rustup.startswith('/') and PurePosixPath(rustup).name == 'rustup', 'absolute rustup manager')
    check('install-rust',[rustup,'toolchain','install',toolchain,'--profile','minimal'])
    tools=receipt['tools']; require(set(tools)=={'cargo','rustc','rustdoc'}, 'exact native toolchain')
    for name,t in tools.items():
        check('resolve-'+name,[rustup,'which','--toolchain',toolchain,name])
        require((evidence/('resolve-'+name+'.stdout')).read_text().strip() == t['path'] and t['path'].startswith('/') and
                PurePosixPath(t['path']).name == name, 'resolved absolute tool path')
    require(len({str(PurePosixPath(t['path']).parent) for t in tools.values()}) == 1, 'one native toolchain bin')
    check('rustc-version',[tools['rustc']['path'],'-vV']); check('cargo-version',[tools['cargo']['path'],'-vV'])
    rustc=(evidence/'rustc-version.stdout').read_text(); cargo=(evidence/'cargo-version.stdout').read_text()
    require(re.search(r'^release: 1\.89\.0$',rustc,re.M) and re.search(r'^host: x86_64-unknown-linux-gnu$',rustc,re.M) and cargo.startswith('cargo 1.89.0 '), 'actual Rust 1.89 native Linux')
    env=receipt['build_environment']
    fixed_env=dict(CARGO_HOME=paths['work']+'/cargo-home',CARGO_TARGET_DIR=paths['work']+'/target',RUSTC=tools['rustc']['path'],RUSTDOC=tools['rustdoc']['path'],RUSTUP_TOOLCHAIN=toolchain,RUSTFLAGS='-Dwarnings',CARGO_BUILD_JOBS='2')
    require({k:v for k,v in env.items() if k!='PATH'}==fixed_env and env['PATH'].split(':')[0]==str(PurePosixPath(tools['cargo']['path']).parent), 'isolated pinned build environment')
    joy=paths['family']+'/joy'; manifest=joy+'/Cargo.toml'; c=tools['cargo']['path']
    check('cargo-fetch',[c,'fetch','--manifest-path',manifest,'--locked'],joy)
    check('cargo-metadata',[c,'metadata','--manifest-path',manifest,'--format-version','1','--locked','--offline'],joy)
    check('native-build',[c,'build','--manifest-path',manifest,'--release','-p','cyber-joy','--locked','--offline'],joy)
    python=rows['native-boundary']['command'][0]; require(python.startswith('/') and 'python' in PurePosixPath(python).name,'absolute Python')
    check('native-boundary',[python,'-B',joy+'/scripts/check-soft3-boundary.py'],joy)
    check('repack-job',[paths['binary'],'pack-job','--compiler',paths['compiler'],'--manifest',paths['work']+'/frozen/inputs/package.json','--output',paths['work']+'/repacked-job.dag',*HOST])
    require(set(rows)==want, 'exact full preparation command set')
    metadata=load(evidence/'cargo-metadata.stdout'); closure=[]
    for p in metadata['packages']:
        if p['source'] is None:
            path=PurePosixPath(p['manifest_path']); family=PurePosixPath(paths['family'])
            require(path.is_relative_to(family) and '..' not in path.parts, 'Cargo closure within pinned family')
            rel=path.relative_to(family); repo=rel.parts[0]
            require(repo in expected['source_selector']['sources'],'selected Cargo repository')
            origin=dict(repository=repo,commit=expected['source_selector']['sources'][repo],manifest=str(rel))
        else:
            origin=dict(source=p['source'])
        closure.append(dict(name=p['name'],version=p['version'],origin=origin))
    require(closure and closure == receipt['closure'], 'raw Cargo metadata complete closure')


def native_command(evidence, receipt, paths, expected, entry):
    phase=receipt['phase']; require(len(receipt['proof_commands'])==1,'one actual native command')
    row=receipt['proof_commands'][0]; require(row['name']==phase and row['status']=='passed','successful actual phase')
    flags=list(HOST); flags[flags.index('--time-ms')+1]=str(expected['profile'][phase+'_time_ms'])
    argv=[paths['binary'],'prove-artifact' if phase=='producer' else 'verify-artifact',paths['compiler'],'--input',paths['job']]
    argv += ['--output','proof.joysc'] if phase=='producer' else ['--proof',paths['proof'],'--output','compiler.dag','--emit','program']
    exact_command(row,argv+flags+PROOF,paths['work']+'/'+phase)
    env=row['environment']; require(set(env) in ({'PATH','LANG'},{'PATH','LANG','RUNNER_TRACKING_ID'}) and env['PATH']=='' and env['LANG']=='C.UTF-8','token-free isolated proof environment')
    inputs={paths[k]:expected['frozen_inputs'][f"inputs/c{entry['generation']}"+('.dag' if k=='compiler' else '-job.dag')] for k in ('compiler','job')}
    if phase=='verifier': inputs[paths['proof']]=ident(entry['proof'])
    require(row['inputs_before']==row['inputs_after']==inputs and row['binary_before']==row['binary_after']==ident(receipt['binary']),'immutable actual command inputs/binary')
    require(row['elapsed_ns'] <= (expected['profile'][phase+'_outer_seconds']+10)*10**9 and row['sampled_peak_rss_bytes'] <= 6*CHUNK,'native observed resource bounds')
    require(row['logs']=={k:identity(evidence/(phase+'.'+k)) for k in ('stdout','stderr')} and row['logs']['stderr']['bytes']==0,'exact native raw logs with empty stderr')
    value=load(evidence/(phase+'.stdout'))
    require(value['ok'] is True and value['schema']==('joy/artifact-proof/v1' if phase=='producer' else 'joy/artifact-verification/v1'),'actual native report schema')
    semantics(value['verification'],entry['verification'])
    require(value['verification']==receipt['production' if phase=='producer' else 'verification'],'actual semantic report binding')
    last=None; peak=0
    with (evidence/(phase+'-resources.jsonl')).open() as source:
        for line in source:
            sample=json.loads(line,object_pairs_hook=unique)
            require(sample['rss_bytes']==sum(p['rss_bytes'] for p in sample['processes']) and sample['rss_bytes']<=6*CHUNK and sample['attempt_bytes']<=30*CHUNK and sample['free_bytes']>=8*CHUNK,'raw bounded resource sample')
            require(sample['elapsed_ns']>0 and (last is None or sample['elapsed_ns']>=last['elapsed_ns']),'ordered resource samples')
            peak=max(peak,sample['rss_bytes']); last=sample
    require(last is not None and peak==row['sampled_peak_rss_bytes'] and last==row['latest_sample'],'raw sample summary equality')
    return row


def phase(evidence, expected, entry, role):
    receipt=load(evidence/'receipt.json'); common_remote(receipt,expected,entry['generation']); no_failure(receipt)
    require(receipt['schema']=='trident/whole-proof-native-phase/v2' and receipt['phase']==role and receipt['status']==('pending-staged' if role=='producer' else 'fresh-verified-retained'),'final authenticated Actions phase receipt')
    require(receipt['bootstrap']==expected['bootstrap'] and receipt['frozen_inputs_before']==receipt['frozen_inputs_after']==expected['frozen_inputs'],'reviewed bootstrap and complete frozen inputs')
    require(receipt['host']['system']=='Linux' and receipt['host']['machine']=='x86_64','native Linux x64')
    paths=phase_paths(entry['generation'],role)
    require(receipt['binary']['path']==paths['binary'] and identity(evidence/'joy-linux-x64')==ident(receipt['binary']),'retained actual native binary')
    require(receipt['proof']==dict(path=paths['proof'],**ident(entry['proof'])),'actual full proof binding')
    preparation_commands(evidence,receipt,paths,expected)
    row=native_command(evidence,receipt,paths,expected,entry)
    snapshot=load(evidence/(role+'-receipt.json'))
    original_status='produced-pending-fresh-verification' if role=='producer' else 'fresh-verified'
    require(snapshot['status']==original_status,'pre-retention native snapshot')
    removed=('pending',) if role=='producer' else ('completion',)
    require({k:v for k,v in receipt.items() if k not in (*removed,'status')} == {k:v for k,v in snapshot.items() if k!='status'},'final native receipt changes only explicit retention pointer/status')
    if role=='verifier':
        require('prover_observations' not in receipt['verification'] and receipt['compiled']==expected['frozen_inputs']['inputs/c2.dag'] and identity(evidence/'compiler.dag')==receipt['compiled'],'exact fresh extracted artifact')
    return receipt,row
