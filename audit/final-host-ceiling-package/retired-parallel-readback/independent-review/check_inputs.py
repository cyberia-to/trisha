from pathlib import Path
import hashlib,json,shutil,time
R=Path(__file__).resolve().parents[1];M=R/'measurements';O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
items=[M/'readback-final-remote-parallel.py',M/'guard-final-parallel-readback.py',M/'parallel-continuation-plan.json',M/'parallel-continuation-pause.json',M/'inspect-final-native-producer.py',M/'remote-package-parallel-readback/original-serial-snapshot.json',R/'trisha-native-ci/.github/final-package-assets.json',M/'native-runs/37000157290/11223880977/restored/receipt.json']
D=O/'originals';D.mkdir(exist_ok=False);records=[]
for i,p in enumerate(items):
 data=p.read_bytes();dest=D/(str(i)+'-'+p.name);dest.write_bytes(data);assert dest.read_bytes()==data
 records.append(dict(original=str(p),stored=str(dest.relative_to(O)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
plan=json.loads(items[2].read_text());transport=json.loads(items[-1].read_text());prior=json.loads(items[5].read_text());assign=plan['parallel_assignments'];rows=transport['assets']
assert len(assign)==len(rows)==20
assert len({x['asset_id'] for x in assign})==len({(x['target'],x['kind']) for x in assign})==20
assert {x['asset_id']:(x['target'],x['kind'],x['bytes'],x['sha256']) for x in assign}=={x['asset_id']:(x['target'],x['kind'],x['bytes'],x['sha256']) for x in rows}
assert sum(x['bytes'] for x in assign)==plan['payload_byte_cap']==626572077
assert plan['total_owned_byte_cap']==plan['payload_byte_cap']+16*1024*1024==643349293
assert plan['disk_free_floor_bytes']==8*1024**3 and plan['wall_seconds_cap']==2700
parallel=(M/'remote-package-parallel-readback').resolve();serial=(M/'remote-package-readback').resolve()
for x in assign:
 p=parallel/x['relative_destination'];q=Path(x['serial_destination']).resolve()
 assert p.resolve().is_relative_to(parallel) and q.is_relative_to(serial) and not p.resolve().is_relative_to(serial) and p.resolve()!=q and not p.is_symlink()
checks=[]
for x in prior['assets']:
 p=Path(x['download_path']);wanted=next(y for y in assign if y['asset_id']==x['asset_id'])
 assert p.resolve().is_relative_to(serial) and p.stat().st_size==wanted['bytes']==x['bytes'] and sha(p)==wanted['sha256']==x['sha256']
 checks.append(dict(asset_id=x['asset_id'],path=str(p),bytes=x['bytes'],sha256=x['sha256']))
assert len(checks)==3
receipt=dict(status='passed-read-only-input-checks',observed_unix_ns=time.time_ns(),sources=records,assignments=20,distinct_asset_ids=20,distinct_target_kind_pairs=20,immutable_snapshot_completed_bodies_rehashed=checks,payload_bytes=plan['payload_byte_cap'],owned_cap_bytes=plan['total_owned_byte_cap'],scope='Static assignment/provenance consistency and three complete snapshot bodies only; no network calls, source import, real process signals or continuation. Does not repair or accept supervisor bounds.')
(O/'input-checks.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(status=receipt['status'],sources=len(records),snapshot_bodies=len(checks))))
