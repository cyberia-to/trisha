"""Copy explicitly selected safe originals; preserve every selected decoded byte."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from privacy import scan

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def ident(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def compact(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, separators=(',', ':'))
        stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    args=parser.parse_args();base=args.base.resolve()
    lane=base/'whole-retention-remote-readback';actual=lane/'local-after-37047053221'
    records=[];pending=[]
    def keep(source, destination, role):
        raw=source.read_bytes()
        if len(raw)>4*1024**2:
            raise ValueError('selected original exceeds4MiB: '+str(source))
        scan(raw,source.name)
        target=ROOT/'retained'/destination
        encoding='gzip' if source.suffix=='.json' else 'identity'
        if encoding=='gzip':target=target.with_name(target.name+'.gz')
        stored=gzip.compress(raw,compresslevel=9,mtime=0) if encoding=='gzip' else raw
        pending.append((target,stored,raw,encoding))
        records.append(dict(original=str(source),original_identity=ident(raw),stored=str(target.relative_to(ROOT)),stored_identity=ident(stored),encoding=encoding,role=role))
    source_map=json.loads((REPO/'.github/whole-readback-sources.json').read_text())
    for name,wanted in source_map.items():
        raw=(REPO/name).read_bytes();assert ident(raw)==wanted
        keep(REPO/name,Path('source')/name,'exact activated source')
    keep(REPO/'.github/whole-readback-sources.json',Path('source-map.json'),'38-source manifest')
    selections={
      'root-actual':(base/'whole-retention-byte-closure-root',['receipt.json','accept.py']),
      'peer-actual':(base/'whole-retention-byte-closure-independent',['peer-review.json','receipt.json','replay.py','git-observation.json']),
      'root-activation':(lane/'root-review-activation',['receipt.json']),
      'root-source':(lane/'root-review-583c',['receipt.json','started.json','new.stdout','new.stderr','original.stdout','original.stderr']),
      'peer-source':(base/'whole-retention-remote-readback-independent',['independent-review.json','review-34ce034.json','review-7382158.json','review-3858ae4.json']),
      'peer-activation':(base/'whole-retention-remote-readback-independent/activation-9779559',['independent-review.json']),
      'activation-preparation':(lane/'activation-preparation',['receipt.json']),
      'source-preparation':(lane/'preparation5',['receipt.json']),
      'activation-tests':(lane/'tests/activation-candidate',['receipt.json','started.json','new-tests.stdout','new-tests.stderr','original-tests.stdout','original-tests.stderr','actionlint.stdout','actionlint.stderr','diff-check.stdout','diff-check.stderr']),
      'source-previous-timeout':(lane/'root-review-3858',['timeout.json']),
      'local-before':(lane/'local-before-9779559',['before.json']),
      'local-after':(actual,['receipt.json','after.json','equivalence.json','packing.json']),
      'worker':(actual/'evidence',['receipt.json']),
      'local-wrapper':(lane,['after-completed.json']),
    }
    for label,(directory,names) in selections.items():
        for name in names:keep(directory/name,Path(label)/name,'curated original evidence')
    closure=json.loads((actual/'receipt.json').read_text())
    omitted=[]
    failed=base/'whole-retention-adoption/remote-v2-36976540959-attempt-1/receipt.json'
    value=json.loads(failed.read_text());assert value['status']=='failed'
    omitted.append(dict(original=str(failed),identity=ident(failed.read_bytes()),status='failed',reason='Original failure remains local; diagnostic content is excluded from publication.'))
    omitted.append(dict(original=str(actual/'original-worker-actions.zip'),identity=closure['admitted_remote']['original_zip'],artifact=closure['admitted_remote']['artifact']['id'],reason='Authenticated original archive contains retained API/process metadata; use original artifact and reviewed private replay.'))
    omitted.append(dict(original=str(base/'whole-retention-byte-closure-independent/replay-1'),reason='Private independent extraction is excluded, including any signed URLs or raw process snapshots.'))
    for e in closure['before']['prepared']['admitted']['entries']:
        omitted.append(dict(original=e['proof']['path'],identity={k:e['proof'][k] for k in ('bytes','sha256')},reason='Full certificate bytes are retained in the22 remote parts; no local proof reread by this delivery.'))
    assert len({str(p) for p,_,_,_ in pending})==len(pending)
    assert all(not p.exists() for p,_,_,_ in pending)
    for target,stored,raw,encoding in pending:
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as output:output.write(stored)
        decoded=gzip.decompress(target.read_bytes()) if encoding=='gzip' else target.read_bytes()
        assert decoded==raw
    compact(ROOT/'references-only.json',dict(schema='trisha/byte-closure-private-references/v1',entries=omitted))
    compact(ROOT/'retention.json',dict(schema='trisha/byte-closure-selected-originals/v1',source_head='97795590613e625b6be43c5e73afff4ab87009cd',prepared_ns=time.time_ns(),records=records))
    print(json.dumps(dict(status='retained',files=len(records),decoded_bytes=sum(v['original_identity']['bytes'] for v in records),stored_bytes=sum(v['stored_identity']['bytes'] for v in records))))


if __name__=='__main__':main()
