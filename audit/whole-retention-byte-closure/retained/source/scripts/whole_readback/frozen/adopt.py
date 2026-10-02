"""Contingent transport equivalence only; execution requires an exact source review."""
import argparse
import base64
from pathlib import Path
import shutil
import signal
import time
import traceback

from common import Reconstruction, identity, load, require, save_new
from contracts import ROOT, LOCAL, MIB, RUN, SCOPE, fixed, ident, local_admission
import remote
from transport import Transport

SOURCE_NAMES = ('README.md','PLAN.md','expected.json','local-preparation.json','common.py','admission.py','contracts.py','archives.py',
                'evidence.py','remote.py','transport.py','adopt.py','test_adoption.py','fixtures.py',
                'compression-rejection/decision.json','compression-rejection/samples.json','compression-rejection/sample.py')


def sources():
    return {name:identity(ROOT/name) for name in SOURCE_NAMES}


def reconstruct(transport,entries):
    require([e['generation'] for e in entries]==[1,2] and sum(len(e['parts']) for e in entries)==22,'both full metadata admissions first')
    for entry in entries:
        value=dict(generation=entry['generation'],proof=entry['proof'],parts=[],status='reading-existing-assets')
        transport.receipt['entries'].append(value); transport.persist(); reconstruction=Reconstruction()
        for part in entry['parts']:
            path=transport.download(f"c{entry['generation']}-part-{part['sequence']:04d}",part['asset'],ident(part),chunk=True)
            reconstruction.append(path,part)
            value['parts'].append(dict(part,independently_downloaded=True)); transport.persist()
            path.unlink()  # Only this newly created, fully checked chunk; failed bytes remain.
        value.update(status='full-byte-equivalence-passed',downloaded_reconstruction=reconstruction.finish(entry['proof']))
        transport.persist()
    require(len(transport.receipt['entries'])==2 and all(e['status']=='full-byte-equivalence-passed' for e in transport.receipt['entries']),'both ordered whole digests passed')
    transport.receipt['status']='both-full-reconstructions-passed'; transport.persist()


def raw_provenance(transport):
    names=['actions-run.stdout','actions-jobs.stdout','actions-artifacts.stdout','actions-run-after-admission.stdout']
    names += [f'whole-v2-{p}-c{g}-1/receipt.json' for g in (1,2) for p in ('producer','verifier')]
    names += [f'whole-v2-{p}-c{g}-1/transport-{t}.json' for g in (1,2) for p,ts in [('producer',('pending',)),('verifier',('download','completion'))] for t in ts]
    require(sum((transport.directory/n).stat().st_size for n in names)<=8*MIB,'bounded final provenance embedding')
    return {n:dict(**identity(transport.directory/n),encoding='base64',bytes_base64=base64.b64encode((transport.directory/n).read_bytes()).decode()) for n in names}


def publish(transport,prepared,expected,entries,name,existing_metadata=None):
    require(transport.receipt['status']=='both-full-reconstructions-passed','publication follows both reconstructions')
    wanted=ident(prepared['metadata']); source=Path(prepared['metadata']['path'])
    require(identity(source)==wanted,'exact original local metadata before retention')
    if existing_metadata is None:
        copy=transport.directory/'original-local-metadata.tar.gz'; transport.budget(wanted['bytes']); shutil.copyfile(source,copy)
        retained=transport.upload('original-local-metadata',copy,name+'.original-local-metadata.tar.gz',wanted)
    else:
        readback=transport.download('existing-original-local-metadata',existing_metadata,wanted)
        require(identity(readback)==wanted,'authenticated existing original local metadata')
        retained=dict(**wanted,asset=existing_metadata)
    require(identity(source)==wanted,'original local metadata still unchanged')
    manifest=dict(schema='trident/local-remote-certificate-byte-equivalence/v1',scope=SCOPE,
                  local=dict(preparation=expected['local_preparation'],binary=prepared['admitted']['binary'],
                             source_revisions=prepared['admitted']['source_revisions'],profile=prepared['admitted']['profile_identity'],
                             entries=prepared['admitted']['entries'],original_metadata=retained),
                  remote=dict(run=expected['run'],source_selector=expected['source_selector'],profile=expected['profile'],
                              entries=[{k:v for k,v in e.items() if k!='local'} for e in entries],
                              original_actions_artifacts=transport.receipt['actions_artifacts'],raw_final_provenance=raw_provenance(transport)),
                  comparison=transport.receipt['entries'],adoption_sources=transport.sources,
                  guard_observations=transport.receipt['default_ref'],
                  reconstruction='For each generation concatenate the referenced original remote parts in sequence order, checking every part and complete SHA256.',
                  acceptance='SH8 acceptance remains separate and pending. This records equal bytes and durable transport only; local and remote executions retain distinct provenance.',
                  transaction='Draft, tag, membership and default-ref guards are observations before and after API calls, not an atomic server transaction.')
    path=transport.directory/'equivalence.json'; save_new(path,manifest)
    require(path.stat().st_size<=16*MIB,'bounded equivalence manifest')
    result=transport.upload('equivalence',path,name+'.equivalence.json',identity(path))
    transport.receipt['equivalence']=result; transport.persist()


def cancel(signum,_frame):
    raise InterruptedError('adoption interrupted: '+str(signum))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-sha256',required=True)
    parser.add_argument('--run-name',required=True)
    parser.add_argument('--existing-local-metadata-asset',type=Path)
    parser.add_argument('--execute',action='store_true',required=True)
    args=parser.parse_args()
    require(args.run_name and all(c.isascii() and (c.isalnum() or c=='-') for c in args.run_name),'unique safe run name')
    reviewed=sources(); review_path=ROOT/'independent-review.json'
    require(review_path.stat().st_size<=MIB,'bounded review receipt')
    require(identity(review_path)['sha256']==args.review_sha256,'explicit source-review identity')
    review=load(review_path); require(review['status']=='passed-source-review' and review['sources']==reviewed,'exact approved executable source set')
    signal.signal(signal.SIGALRM,cancel); signal.alarm(43200)
    expected=fixed(); prepared=local_admission(expected,scan=True)
    directory=ROOT/args.run_name; directory.mkdir()
    signal.signal(signal.SIGTERM,cancel); signal.signal(signal.SIGINT,cancel)
    transport=Transport(directory,prepared['gh'],reviewed,sources)
    transport.receipt.update(review=identity(review_path),local_preparation=expected['local_preparation']); transport.persist()
    try:
        transport.draft('initial')
        entries=remote.admit(transport,expected,prepared)
        reconstruct(transport,entries)
        require(local_admission(expected,scan=True)==prepared,'original local whole bytes and all22 parts remain exact after readback')
        if args.existing_local_metadata_asset is not None:
            require(args.existing_local_metadata_asset.is_file() and not args.existing_local_metadata_asset.is_symlink() and args.existing_local_metadata_asset.stat().st_size<=65536,'bounded explicit existing metadata pointer')
        existing=None if args.existing_local_metadata_asset is None else load(args.existing_local_metadata_asset)
        publish(transport,prepared,expected,entries,'whole-equivalence-'+args.run_name+'-'+expected['local_preparation']['sha256'][:16],existing)
        transport.draft('final')
        require(local_admission(expected)==prepared,'original local evidence final stability')
        transport.receipt['status']='byte-equivalent-transport-adopted'
    except BaseException:
        error=traceback.format_exc()
        try: transport.failure(error)
        except BaseException as terminal_error: transport.receipt['terminal_evidence_error']=repr(terminal_error)
        raise
    finally:
        transport.receipt['ended_ns']=time.time_ns()
        try:
            transport.persist()
        except BaseException:
            already_failed=transport.receipt['status']=='failed'
            if not already_failed:
                try: transport.failure(traceback.format_exc())
                except BaseException as terminal_error: transport.receipt['terminal_evidence_error']=repr(terminal_error)
                raise
        finally:
            signal.alarm(0)


if __name__=='__main__':
    main()
