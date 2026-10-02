"""Read all canonical retained certificate parts once on a fresh hosted worker."""
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import sys
import time
import traceback

import gate


def replay(transport,entries):
    from common import Reconstruction, identity, require
    from contracts import ident
    from metadata import reserve
    require([e['generation'] for e in entries]==[1,2] and sum(len(e['parts']) for e in entries)==22,'all22 identities admitted first')
    for entry in entries:
        row=dict(generation=entry['generation'],proof=entry['proof'],parts=[],status='reading-existing-assets')
        transport.receipt['entries'].append(row);transport.persist();whole=Reconstruction()
        for part in entry['parts']:
            reserve(transport.directory,gate.sources(),entry['generation'],part['sequence'])  # Early capacity check; authoritative record is after membership in Readback.run.
            path=transport.download(f"c{entry['generation']}-part-{part['sequence']:04d}",part['asset'],ident(part),chunk=True)
            whole.append(path,part);transport.budget()
            row['parts'].append(dict(part,independently_downloaded=True));transport.persist()
            require(identity(path)==ident(part),'stable checked owned temporary before deletion');path.unlink()
        row.update(status='ordered-whole-bytes-passed',downloaded_reconstruction=whole.finish(entry['proof']));transport.persist()
    require(all(e['status']=='ordered-whole-bytes-passed' for e in transport.receipt['entries']),'both complete reconstructions')


def main():
    started=time.monotonic();transport=None;primary=None
    def cancel(signum,_frame):raise InterruptedError('remote byte replay interrupted: '+str(signum))
    signal.signal(signal.SIGALRM,cancel);signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel);signal.alarm(5400)
    try:
        source,selected,expected,prepared=gate.activation()
        from bounded import Readback, SCHEMA, SCOPE
        from metadata import PROFILE
        from common import identity, load, require
        import remote
        from packing import pack
        require(selected['bounds']==PROFILE,'exact reviewed remote profile selector')
        root=Path(os.environ['RUNNER_TEMP'])/'whole-readback';root.mkdir();directory=root/'data';directory.mkdir()
        gh=Path(shutil.which('gh')).resolve();gh_value=dict(path=str(gh),**identity(gh))
        transport=Readback(directory,gh_value,source,gate.sources);transport.tick=started
        own=dict(id=int(os.environ['GITHUB_RUN_ID']),attempt=1,head=os.environ['GITHUB_SHA'],repository=os.environ['GITHUB_REPOSITORY'],branch=selected['branch'],workflow=selected['workflow'],event=os.environ['GITHUB_EVENT_NAME'])
        transport.receipt.update(schema=SCHEMA,scope=SCOPE,worker=own,source_manifest=identity(gate.MANIFEST),selector=identity(gate.SELECTOR),python=dict(path=str(Path(sys.executable).resolve()),version=platform.python_version(),**identity(Path(sys.executable).resolve())),gh=gh_value,local_preparation=selected['local_preparation'],original_local_metadata=selected['original_metadata'],capability='contents:write for fixed unpublished draft visibility; only GET operations are implemented and allowed')
        transport.persist();transport.draft('initial')
        entries=remote.admit(transport,expected,prepared)
        require(entries==selected['remote_entries'],'all original admitted receipt/part/whole identities equal frozen selector')
        actual={n:dict(id=v['metadata']['id'],zip=v['zip']) for n,v in transport.receipt['actions_artifacts'].items()}
        require(actual==selected['actions_artifacts'],'same six original authenticated Actions archives')
        replay(transport,entries);transport.draft('final')
        require(gate.sources()==source,'worker source stable after all22 bodies')
        # Keep the independently replayed source snapshots in the same bounded evidence.
        copies=directory/'worker-sources';copies.mkdir()
        for name,value in source.items():
            target=copies/name;target.parent.mkdir(parents=True,exist_ok=True);transport.budget(value['bytes']);shutil.copyfile(gate.REPOSITORY/name,target);require(identity(target)==value,'exact worker source evidence')
        transport.sample_tick=-1;transport.sample();transport.sampling_closed=True
        transport.receipt.update(status='completed-byte-replay',ended_ns=time.time_ns(),elapsed_monotonic_seconds=time.monotonic()-started);transport.persist()
        pack(transport,root/'artifact/evidence.zip')
        print(json.dumps(dict(status='completed-byte-replay',worker=own,receipt=identity(directory/'receipt.json'))))
    except BaseException:
        primary=traceback.format_exc()
        if transport is not None:
            try:transport.failure(primary)
            except BaseException as error:transport.receipt['terminal_evidence_error']=repr(error)
            transport.receipt['ended_ns']=time.time_ns()
            try:transport.persist()
            except BaseException:pass
            # Move only the worker's pre-reserved failure record into its small artifact.
            terminal=transport.directory/'terminal-failure.json'
            if terminal.exists():
                artifact=transport.directory.parent/'artifact';artifact.mkdir(exist_ok=True)
                terminal.rename(artifact/'terminal-failure.json')
        raise
    finally:signal.alarm(0)


if __name__=='__main__':main()
