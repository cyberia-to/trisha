"""Retain completed final source reproduction originals without the duplicate large archive."""
from pathlib import Path
import gzip,hashlib,json,shutil
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci';R=M/'source-reproduction-readback';report=json.loads((R/'receipt.json').read_text());assert report['status']=='passed';original=Path(report['original_container']);O=CI/'audit/final-host-ceiling-package/source-reproduction';O.mkdir();rows=[]
def keep(source,relative,compress=False):
 raw=source.read_bytes();destination=O/relative;destination.parent.mkdir(parents=True,exist_ok=True)
 if compress:destination=destination.with_name(destination.name+'.gz');destination.write_bytes(gzip.compress(raw,mtime=0))
 else:destination.write_bytes(raw)
 data=destination.read_bytes();assert (gzip.decompress(data) if compress else data)==raw
 rows.append(dict(original=str(source),retained=str(destination.relative_to(O)),encoding='gzip' if compress else 'identity',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),retained_sha256=hashlib.sha256(data).hexdigest()))
for name in ('artifact.zip','api.json','retention.json'):keep(original/name,'original-container/'+name)
for name in ('receipt.json','source-impact.json'):keep(original/'restored'/name,'original-preparer/'+name)
for p in sorted(R.iterdir()):
 if p.is_file() and p.name!='source-export.tar.gz':keep(p,'readback/'+p.name,p.suffix in ('.stdout','.stderr') or p.name in ('sources.json','vendor-sources.json'))
for p in sorted((M/'inactive-workflow-startup').iterdir()):
 if p.is_file():keep(p,'inactive-workflow-startup/'+p.name,p.suffix in ('.stdout','.stderr'))
for name in ('collect-native.py','check-source-reproduction.py','source-reproduction-collector.stdout','source-reproduction-collector.stderr','source-reproduction-readback.stdout','source-reproduction-readback.stderr'):
 keep(M/name,name,name.endswith(('.stdout','.stderr')))
keep(Path(__file__),Path(__file__).name)
(O/'retention-manifest.json').write_text(json.dumps(dict(scope='Complete original authenticated preparer container plus independent source asset readback metadata; 536837002-byte archive retained at exact draft asset and original local paths',files=rows,source_archive=dict(asset_id=report['asset']['id'],bytes=report['archive_bytes'],sha256=report['source_sha256'],local_original=str(M/'source-export.tar.gz'),local_readback=str(R/'source-export.tar.gz'))),indent=2)+'\n');print(json.dumps(dict(status='retained',files=len(rows),asset_id=report['asset']['id'])))
