"""The committed worker source and fixed original certificate selector."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPOSITORY=Path(__file__).resolve().parents[2]
ROOT=Path(__file__).resolve().parent
FROZEN=ROOT/'frozen'
SELECTOR=REPOSITORY/'.github/whole-readback.json'
MANIFEST=REPOSITORY/'.github/whole-readback-sources.json'


def require(value,reason):
    if not value:raise ValueError(reason)


def unique(pairs):
    value={}
    for k,v in pairs:require(k not in value,'unique JSON key');value[k]=v
    return value


def load(path):return json.loads(path.read_text(),object_pairs_hook=unique)


def identity(path):
    require(path.is_file() and not path.is_symlink(),'regular source file')
    with path.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
    return dict(bytes=path.stat().st_size,sha256=digest)


def sources():
    recorded=load(MANIFEST);require(isinstance(recorded,dict) and len(recorded)<80,'bounded source manifest')
    for name,value in recorded.items():
        path=REPOSITORY/name;require(path.is_relative_to(REPOSITORY) and '..' not in Path(name).parts,'source under checkout')
        require(identity(path)==value,'exact committed worker source: '+name)
    fixed={'.gitattributes','.github/whole-readback.json','.github/whole-readback-activation.json',
           '.github/workflows/whole-retention-readback.yml','.claude/plans/whole-retention-byte-replay.md',
           'docs/reference/whole-retention-byte-replay.md'}
    owned={str(p.relative_to(REPOSITORY)) for p in ROOT.rglob('*') if p.is_file()}
    require(set(recorded)==fixed|owned,'exact complete owned worker source membership')
    return recorded


def frozen():
    selected=load(SELECTOR);recorded=load(FROZEN/'sources.json')
    require(identity(FROZEN/'sources.json')==selected['frozen_sources_manifest'],'unchanged reviewed original helper source map')
    for name,value in recorded.items():require(identity(FROZEN/name)==value,'unchanged reviewed pure/helper source '+name)
    sys.path.insert(0,str(FROZEN))
    import contracts
    expected=contracts.fixed();prepared=load(FROZEN/'local-preparation.json')
    require(selected['local_preparation']==expected['local_preparation']==identity(FROZEN/'local-preparation.json'),'exact original canonical preparation')
    return selected,expected,prepared


def activation():
    source=sources();selected,expected,prepared=frozen();armed=load(REPOSITORY/'.github/whole-readback-activation.json')
    require(selected['enabled'] is True and armed['enabled'] is True,'reviewed activation is enabled')
    require(selected['repository']==os.environ.get('GITHUB_REPOSITORY')=='cyberia-to/trisha','fixed own repository')
    require(os.environ.get('GITHUB_REF')=='refs/heads/'+selected['branch'] and armed['branch']==selected['branch'],'exact reviewed feature branch')
    require(os.environ.get('GITHUB_EVENT_NAME') in ('push','workflow_dispatch'),'explicit reviewed trigger')
    event=load(Path(os.environ['GITHUB_EVENT_PATH']));require(event['repository']['private'] is False,'public free-runner repository')
    require(os.environ.get('RUNNER_OS')=='Linux' and os.environ.get('RUNNER_ARCH')=='X64','fresh native Linux x64 worker')
    require(os.environ.get('GITHUB_RUN_ATTEMPT')=='1','single initial worker attempt; no automatic retry')
    git=subprocess.run(['git','rev-parse','HEAD'],cwd=REPOSITORY,env={'PATH':'/usr/bin:/bin','LANG':'C'},capture_output=True,timeout=10)
    require(git.returncode==0 and git.stdout.decode().strip()==os.environ['GITHUB_SHA'],'exact checkout execution head')
    clean=subprocess.run(['git','status','--porcelain','--untracked-files=all'],cwd=REPOSITORY,env={'PATH':'/usr/bin:/bin','LANG':'C'},capture_output=True,timeout=10)
    require(clean.returncode==0 and not clean.stdout,'clean committed worker source')
    return source,selected,expected,prepared
