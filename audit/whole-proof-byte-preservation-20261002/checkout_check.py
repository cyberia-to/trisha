"""Real isolated Git checkout replay; never compile or execute native payloads."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def identity(path):
    return dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('repository',type=Path);parser.add_argument('tree');parser.add_argument('directory',type=Path);args=parser.parse_args()
    args.directory.mkdir();checkout=args.directory/'checkout';commands=[]
    def run(name,argv,cwd=None):
        tick=time.monotonic();started=time.time_ns()
        with (args.directory/(name+'.stdout')).open('xb') as out,(args.directory/(name+'.stderr')).open('xb') as err:
            result=subprocess.run(argv,cwd=cwd,stdout=out,stderr=err,timeout=180)
        row=dict(name=name,command=argv,cwd=str(cwd) if cwd else None,exit_code=result.returncode,started_ns=started,elapsed_seconds=time.monotonic()-tick,stdout=identity(args.directory/(name+'.stdout')),stderr=identity(args.directory/(name+'.stderr')));commands.append(row)
        return result.returncode
    assert run('clone',['git','clone','--shared','--no-checkout',str(args.repository),str(checkout)])==0
    assert run('autocrlf',['git','config','--local','core.autocrlf','true'],checkout)==0
    assert run('eol',['git','config','--local','core.eol','crlf'],checkout)==0
    assert run('read-tree',['git','read-tree',args.tree],checkout)==0
    assert run('checkout-index',['git','checkout-index','--all'],checkout)==0
    scopes=['whole-self-build-linux-20261002','whole-self-build-linux-clock-v2-20261002','whole-self-build-clock-v2-preparation']
    inventories={};before_unchanged={}
    for scope in scopes:
        d=checkout/'audit'/scope;manifest=json.loads((d/'files.json').read_text());actual={str(p.relative_to(d)):identity(p) for p in d.rglob('*') if p.is_file() and p.name!='__pycache__' and p!=d/'files.json'}
        assert manifest==actual,scope+' retained exact membership and bytes'
        prior=json.loads((d/'byte-preservation-prior-files.json').read_text());assert all(identity(d/n)==v for n,v in prior.items()),scope+' all historical bytes'
        inventories[scope]=dict(files=len(manifest),manifest=identity(d/'files.json'));before_unchanged[scope]=len(prior)
    # This unprotected committed text really changed through Git's smudge filter.
    control=checkout/'CLAUDE.md'; original=args.repository/'CLAUDE.md'
    assert b'\r\n' not in original.read_bytes() and control.read_bytes()==original.read_bytes().replace(b'\n',b'\r\n'),'actual CRLF conversion control'
    outcomes={}
    for i,scope in enumerate(scopes):outcomes[scope]=run('replay-'+str(i),[sys.executable,'-B','-W','error',str(checkout/'audit'/scope/'check.py')],checkout)
    # Hash-bound sources must exactly match the source Git tree, not parsed equivalents.
    activation=json.loads((checkout/'audit/whole-self-build-clock-v2-preparation/activation/selection.json').read_text())
    expected=json.loads((checkout/'audit/whole-self-build-linux-clock-v2-20261002/replay-contract/expected.json').read_text())
    source_names=set(activation['enabled_sources'])|set(expected['bootstrap'])
    import zipfile
    with zipfile.ZipFile(checkout/'audit/whole-self-build-linux-20261002/raw/whole-self-build-c1-1.zip') as stream:
        source_names|=set(json.loads(stream.read('receipt.json'))['bootstrap'])
    sources={n:dict(expected=identity(args.repository/n),checkout=identity(checkout/n)) for n in sorted(source_names)}
    changed=[n for n,v in sources.items() if v['expected']!=v['checkout']]
    status='passed-checkout-replay' if not changed and all(v==0 for v in outcomes.values()) else 'failed-bootstrap-byte-conversion'
    receipt=dict(schema='trident/git-crlf-evidence-replay/v1',status=status,tree=args.tree,driver=identity(Path(__file__)),core_autocrlf=True,real_conversion_control=dict(path='CLAUDE.md',source=identity(original),checkout=identity(control)),historical_members_unchanged=before_unchanged,inventories=inventories,sources=sources,changed_bootstrap=changed,offline_replays=outcomes,commands=commands)
    (args.directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(status=status,changed=changed,outcomes=outcomes),indent=2))
    return 0 if status=='passed-checkout-replay' else 1


if __name__=='__main__':sys.exit(main())
