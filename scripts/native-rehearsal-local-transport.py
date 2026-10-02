"""Supply byte-verified local source/kit transport to the unchanged native bootstrap."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
ROOT=Path(__file__).resolve().parent
FAMILY=ROOT.parent
spec=importlib.util.spec_from_file_location('native_candidate',ROOT/'scripts/native-candidate.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
original=module.download
cache={604481115:FAMILY/'measurements/source-export.tar.gz',604463150:FAMILY/'trisha/audit/selfhost-kit/accepted/selfhost-kit.tar.gz'}
if (ROOT/'asset-cache.json').exists():
 cache={int(key):Path(value).resolve(strict=True) for key,value in json.loads((ROOT/'asset-cache.json').read_text()).items()}
rows=[]
def download(asset,destination,env,maximum=None):
 source=cache.get(int(asset['asset_id']))
 if source is None:return original(asset,destination,env,maximum)
 if maximum is not None and source.stat().st_size>maximum:raise ValueError('cached archive exceeds bound')
 if module.sha(source)!=asset['sha256']:raise ValueError('cached input identity mismatch')
 with source.open('rb') as inp,destination.open('xb') as out:shutil.copyfileobj(inp,out)
 if module.sha(destination)!=asset['sha256']:raise ValueError('copied input identity mismatch')
 rows.append(dict(asset_id=asset['asset_id'],source=str(source),destination=str(destination),bytes=source.stat().st_size,sha256=asset['sha256'],scope='byte-verified local transport; no claim of remote asset availability'))
 (ROOT/'local-transport.json').write_text(json.dumps(rows,indent=2)+'\n')
original_run=module.run
def run(command,log,env,cwd):
 result=original_run(command,log,env,cwd)
 if log.name=='build.log':
  built=json.loads((cwd/'candidate/candidate.json').read_text())
  if not built['toolchain'].startswith('rustc 1.89.0 '):raise ValueError('built candidate used a different Rust toolchain')
 return result
module.run=run
module.download=download
module.main()
