"""Explicit local closure and unique metadata retention for a reviewed remote replay."""
import argparse
import datetime
import json
from pathlib import Path
import re
import shutil
import signal
import time
import traceback
from urllib.parse import quote

import gate
gate.frozen()
from common import REPO, RELEASE, check_asset, identity, load, require, save_new
from contracts import MIB, ident
from transport import Transport
from local_admission import scan, compare, original
import result

SCOPE='Original local6e and remote proofdd61 executions remain distinct; new remote body replay is transport evidence; SH8 acceptance remains separate.'


class ClosureTransport(Transport):
    def upload(self,label,path,name,expected):
        require(self.receipt['status']=='ready-unique-metadata-retention' and self.receipt['admitted_remote']['status']=='passed','publication follows authenticated complete remote bytes')
        compare(self.receipt['before'],self.receipt['after'])
        require(path.parent==self.directory and identity(path)==expected and expected['bytes']<=32*MIB,'owned bounded exact local metadata publication')
        before=self.draft(label+'-before');require(name not in {a['name'] for a in before},'unique new metadata asset name')
        endpoint=f'https://uploads.github.com/repos/{REPO}/releases/{RELEASE}/assets?name='+quote(name,safe='')
        value=load(self.run(label+'-upload',['api','--method','POST',endpoint,'-H','Content-Type: application/octet-stream','--input',str(path)],data=True))
        check_asset(value,name,expected)
        after=self.draft(label+'-after');matches=[a for a in after if a['name']==name]
        require(len(matches)==1 and matches[0]['id']==value['id'],'unique fixed-draft uploaded membership');check_asset(matches[0],name,expected)
        require(identity(path)==expected,'metadata stable through publication')
        body=self.download(label+'-readback',value,expected);require(identity(body)==expected,'independent metadata readback')
        return dict(**expected,asset={k:value[k] for k in ('id','name','size','state','digest','url','browser_download_url')})


def review(path,wanted):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size<=MIB,'bounded explicit independent source review')
    require(identity(path)['sha256']==wanted,'exact requested independent review')
    value=load(path);require(value['status']=='passed-source-review' and value['sources']==gate.sources(),'exact reviewed executable source map')
    return identity(path)


def publish(t,prepared,admitted,before_path,after_path,name,existing=None):
    source=Path(prepared['metadata']['path']);wanted=ident(prepared['metadata'])
    require(identity(source)==wanted==gate.load(gate.SELECTOR)['original_metadata'],'unchanged original local metadata')
    if existing is None:
        path=t.directory/'original-local-metadata.tar.gz';t.budget(wanted['bytes']);shutil.copyfile(source,path)
        retained=t.upload('original-local-metadata',path,name+'.original-local-metadata.tar.gz',wanted)
    else:
        pointer=load(existing);body=t.download('existing-original-local-metadata',pointer,wanted);require(identity(body)==wanted,'authenticated existing identical local metadata');retained=dict(**wanted,asset=pointer)
    require(identity(source)==wanted,'original local metadata still exact')
    manifest=dict(schema='trident/local-remote-certificate-byte-equivalence/v2',scope=SCOPE,
                  local=dict(preparation=t.receipt['before']['local_preparation'],source_revisions=prepared['admitted']['source_revisions'],binary=prepared['admitted']['binary'],entries=prepared['admitted']['entries'],original_metadata=retained,before=dict(identity=identity(before_path),observation=load(before_path)),after=dict(identity=identity(after_path),observation=load(after_path))),
                  original_remote_proof=dict(run=gate.load(gate.FROZEN/'expected.json')['run'],entries=admitted['checked']['entries']),
                  remote_body_replay=admitted,worker_observation=load(t.directory/'evidence/receipt.json'),packing_observation=load(t.directory/'packing.json'),local_closure_sources=t.sources,
                  original_local_attempt='Failed original local adopter remains unchanged; this manifest records a separate successful remote body observation plus local before/after closure.',
                  reconstruction='For each generation concatenate all referenced original parts by sequence and validate every part and complete SHA256.',
                  transaction='Draft, tag, membership and default-ref guards are non-atomic observations around each API operation; no release/tag/promotion is performed.')
    path=t.directory/'equivalence.json';save_new(path,manifest);require(path.stat().st_size<=16*MIB,'bounded explicit equivalence manifest')
    t.receipt['retained_original_metadata']=retained;t.receipt['equivalence']=t.upload('equivalence',path,name+'.equivalence.json',identity(path));t.persist()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['before','after']);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--adoption',type=Path,required=True);parser.add_argument('--review',type=Path,required=True);parser.add_argument('--review-sha256',required=True);parser.add_argument('--before',type=Path);parser.add_argument('--before-sha256');parser.add_argument('--run',type=int);parser.add_argument('--head');parser.add_argument('--name');parser.add_argument('--existing-metadata',type=Path);args=parser.parse_args()
    checked=review(args.review,args.review_sha256);source=gate.sources();args.output.mkdir();t=None
    def cancel(signum,_frame):raise InterruptedError('local closure interrupted: '+str(signum))
    signal.signal(signal.SIGALRM,cancel);signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel);signal.alarm(43200)
    try:
        require(shutil.disk_usage(args.output).free>=8*1024**3,'local closure free-space floor')
        if args.mode=='before':
            require(args.before is None and args.run is None and args.head is None and args.name is None and args.existing_metadata is None,'before mode performs no network/publication')
            value=scan(args.adoption);value.update(worker_sources=source,source_manifest=identity(gate.MANIFEST),independent_review=checked)
            require(gate.sources()==source,'checking source stable');save_new(args.output/'before.json',value);print(json.dumps(dict(status=value['status'],before=identity(args.output/'before.json'))));return
        require(args.before is not None and args.before_sha256 and args.before.stat().st_size<=16*MIB and identity(args.before)['sha256']==args.before_sha256,'explicit original before observation')
        before=load(args.before);require(before['worker_sources']==source and before['source_manifest']==identity(gate.MANIFEST),'before observation exact source profile')
        require(args.run and args.head and args.name and re.fullmatch('[a-z0-9-]{1,100}',args.name),'explicit reviewed remote coordinates and unique publication name')
        prepared=before['prepared'];contract,_=original(args.adoption);expected=gate.load(gate.FROZEN/'expected.json')
        require(contract.local_admission(expected)==prepared,'all original receipts/inputs/metadata still admitted before remote receipt download')
        t=ClosureTransport(args.output,prepared['gh'],source,gate.sources);t.receipt.update(schema='trident/local-remote-byte-closure/v2',scope=SCOPE,review=checked,before=before);t.persist();t.draft('initial')
        admitted=result.admit(t,args.run,args.head);t.receipt['admitted_remote']=admitted;t.persist()
        actual_start=int(datetime.datetime.fromisoformat(admitted['jobs']['jobs'][0]['started_at'].replace('Z','+00:00')).timestamp()*10**9)
        require(before['ended_ns']<actual_start,'actual local scan predates new remote job')
        after=scan(args.adoption);compare(before,after)
        actual_end=int(datetime.datetime.fromisoformat(admitted['jobs']['jobs'][0]['completed_at'].replace('Z','+00:00')).timestamp()*10**9)
        require(after['started_ns']>actual_end,'actual local scan follows completed remote job')
        after.update(worker_sources=source,source_manifest=identity(gate.MANIFEST),independent_review=checked);save_new(args.output/'after.json',after)
        t.receipt.update(after=after,status='ready-unique-metadata-retention');t.persist()
        if args.existing_metadata is not None:require(args.existing_metadata.is_file() and not args.existing_metadata.is_symlink() and args.existing_metadata.stat().st_size<=65536,'bounded explicit existing asset pointer')
        publish(t,prepared,admitted,args.before,args.output/'after.json',args.name,args.existing_metadata)
        t.draft('final');require(contract.local_admission(expected)==prepared and gate.sources()==source,'original closure and checking sources stable after publication')
        t.receipt.update(status='byte-equivalent-transport-adopted-remote-replay',ended_ns=time.time_ns());t.persist();print(json.dumps(dict(status=t.receipt['status'],equivalence=t.receipt['equivalence'])))
    except BaseException:
        error=traceback.format_exc()
        if t is not None:
            try:t.failure(error)
            except BaseException as failure:t.receipt['terminal_evidence_error']=repr(failure)
            try:t.persist()
            except BaseException:pass
        else:save_new(args.output/'failed.json',dict(status='failed',error=error,sources=source,review=checked,ended_ns=time.time_ns()))
        raise
    finally:signal.alarm(0)


if __name__=='__main__':main()
