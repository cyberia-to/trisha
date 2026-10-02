"""Explicit final128MiB archive profile and reserved observation capacity."""
import re
import time

from common import CHUNK, require
from contracts import MIB

PROFILE=dict(total_seconds=5400,api_seconds=120,body_seconds=1800,chunk_bytes=CHUNK,
             sidecar_bytes=512*MIB,failure_reserve_bytes=MIB,rss_bytes=2*CHUNK,
             free_floor_bytes=8*CHUNK,artifact_zip_bytes=256*MIB,artifact_decoded_bytes=128*MIB,
             receipt_bytes=4*MIB,resources_bytes=4*MIB,inventory_bytes=MIB,packing_receipt_bytes=MIB)
EXPANDED={f'whole-v2-{phase}-c{g}-1' for phase in ('producer','verifier','pending') for g in (1,2)}

def selected(directory):
    paths=list(directory.rglob('*'));require(len(paths)<=50000 and all(not p.is_symlink() for p in paths),'bounded ordinary metadata tree')
    files=[p for p in paths if p.is_file() and p!=directory/'chunk' and p.relative_to(directory).parts[0] not in EXPANDED]
    require(len(files)<=10000,'bounded final metadata membership')
    return files

def reserve(directory,sources,generation,sequence):
    size=lambda p:p.stat().st_size if p.exists() else 0
    ordinary=size(directory/'receipt.json');resources=size(directory/'resources.jsonl');inventory=size(directory/'evidence-files.json')
    require(ordinary<=PROFILE['receipt_bytes'] and resources<=PROFILE['resources_bytes'] and inventory<=PROFILE['inventory_bytes'],'bounded receipt/resource observations')
    missing=sum(value['bytes'] for name,value in sources.items() if not (directory/'worker-sources'/name).exists())
    parts=dict(receipt=PROFILE['receipt_bytes']-ordinary,resources=PROFILE['resources_bytes']-resources,
               source_copies=missing,inventory=PROFILE['inventory_bytes']-inventory,packing=PROFILE['packing_receipt_bytes'])
    present=sum(p.stat().st_size for p in selected(directory));required=present+sum(parts.values())
    require(required<=PROFILE['artifact_decoded_bytes'],'128MiB final metadata plus reserved observation capacity')
    return dict(time_ns=time.time_ns(),generation=generation,sequence=sequence,present_bytes=present,
                ordinary_receipt_bytes=ordinary,resource_bytes=resources,reserved=parts,required_bytes=required)

def record_body(transport,name,output,data):
    if output!=transport.directory/'chunk':return
    matched=re.fullmatch(r'c([12])-part-([0-9]{4})-download',name)
    require(data and matched is not None,'exact known proof body boundary')
    generation,sequence=map(int,matched.groups())
    row=reserve(transport.directory,transport.sources,generation,sequence)
    row['boundary']='after-membership-before-body'
    transport.capacity_coordinate=(generation,sequence)
    transport.receipt.setdefault('metadata_reservations',[]).append(row)
    transport.persist()

def check_profile(value):
    require(value==PROFILE and all(type(v) is int for v in value.values()),'exact integer remote observation profile')

def observations(rows,sources,commands,started):
    expected=[(g,s) for g,count in ((1,12),(2,10)) for s in range(count)]
    # Actual canonical part counts come from authenticated entries; the fixed pair is12+10.
    require([(r['generation'],r['sequence']) for r in rows]==expected,'all22 body metadata reservations')
    for row in rows:
        require(row['boundary']=='after-membership-before-body','authoritative actual body boundary')
        for key in ('time_ns','generation','sequence','present_bytes','ordinary_receipt_bytes','resource_bytes','required_bytes'):
            require(type(row[key]) is int and row[key]>=0,'integer nonnegative metadata observation')
        reserved=row['reserved'];require(set(reserved)=={'receipt','resources','source_copies','inventory','packing'},'exact reservation categories')
        require(all(type(v) is int and v>=0 for v in reserved.values()),'nonnegative reserved bytes')
        require(reserved['receipt']+row['ordinary_receipt_bytes']==PROFILE['receipt_bytes'] and reserved['resources']+row['resource_bytes']==PROFILE['resources_bytes'],'remaining bounded observation capacity')
        require(reserved['source_copies']==sum(v['bytes'] for v in sources.values()),'all source copies reserved before final copy phase')
        require(reserved['inventory']==PROFILE['inventory_bytes'] and reserved['packing']==PROFILE['packing_receipt_bytes'],'fixed final metadata overhead')
        require(row['present_bytes']+sum(reserved.values())==row['required_bytes']<=PROFILE['artifact_decoded_bytes'],'exact bounded reservation arithmetic')
        body=next(c for c in commands if c['name']==f"c{row['generation']}-part-{row['sequence']:04d}-download")
        require(started<=row['time_ns']<=body['started_ns'],'in-interval reserve precedes body download')
    require(all(a['time_ns']<=b['time_ns'] for a,b in zip(rows,rows[1:])),'ordered metadata admissions')

def resources(samples,observer,started,ended,peak,latest=None,packing=False):
    require(type(observer) is int and observer>0,'positive integer observer PID')
    require(type(peak) is int and 0<=peak<=PROFILE['rss_bytes'],'nonnegative bounded resource peak')
    require(samples and len(samples)<=6000,'bounded nonempty resource samples')
    for sample in samples:
        require(type(sample['time_ns']) is int and started<=sample['time_ns']<=ended,'integer in-interval resource time')
        require(type(sample['rss_bytes']) is int and 0<=sample['rss_bytes']<=PROFILE['rss_bytes'],'nonnegative integer sampled RSS')
        rows=sample['processes'];require(isinstance(rows,list) and 0<len(rows)<=32768,'nonempty bounded process sample')
        ids=[]
        for row in rows:
            require(set(row)=={'pid','ppid','pgid','rss_bytes'},'exact process observation fields')
            require(all(type(v) is int and v>=0 for v in row.values()) and row['pid']>0,'integer process identity and nonnegative RSS')
            ids.append(row['pid'])
        require(len(ids)==len(set(ids)) and observer in ids,'distinct PIDs including actual observer')
        require(not packing or ids==[observer],'packing samples only the active observer')
        require(sum(row['rss_bytes'] for row in rows)==sample['rss_bytes'],'exact resource sum')
    require(all(a['time_ns']<=b['time_ns'] for a,b in zip(samples,samples[1:])),'ordered resource observations')
    require(max(s['rss_bytes'] for s in samples)==peak,'raw resource peak binding')
    require(latest is None or samples[-1]==latest,'latest raw resource binding')
