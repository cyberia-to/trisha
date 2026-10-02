"""Positive whole compiler producer, pending handoff and fresh verifier phases."""
import argparse
import json
from pathlib import Path
import shutil
import traceback

import whole_self_host as host
import whole_self_inputs as frozen
from whole_v2_common import State, bootstrap, bounded, flags, identity, load, prepare, require, save
from whole_v2_transport import CHUNK, PROFILE, Reconstruction, Transport, check_asset, prefix, validate_pending, write_chunk


def produce(state):
    r = state.report
    require(r['phase'] == 'producer' and r['status'] == 'prepared', 'prepared producer')
    binary, compiler, job = state.paths()
    value = bounded(state, [binary, 'prove-artifact', compiler, '--input', job, '--output', 'proof.joysc', *flags('producer', r['profile'])], [compiler, job])
    accepted = load(state.package / f"inputs/accepted-c{r['generation']+1}-step.json")
    r['production'] = frozen.compare(value, accepted, 'prove')
    proof = state.work / 'producer/proof.joysc'
    r['proof'] = dict(path=str(proof), **identity(proof))
    require(0 < r['proof']['bytes'] <= PROFILE['wire_bytes'], 'complete bounded certificate')
    state.final_identities('produced')
    r['status'] = 'produced-pending-fresh-verification'; state.persist()
    shutil.copy2(state.results / 'receipt.json', state.results / 'producer-receipt.json')


def stage(state):
    r = state.report
    require(r['phase'] == 'producer' and r['status'] == 'produced-pending-fresh-verification', 'complete production awaiting fresh verifier')
    proof = {k: r['proof'][k] for k in ('bytes', 'sha256')}
    source = Path(r['proof']['path']); require(identity(source) == proof, 'complete producer bytes unchanged')
    transport = Transport(state, 'pending'); name = prefix(state, 'pending', proof)
    parts, reconstruction = [], Reconstruction()
    try:
        with source.open('rb') as stream:
            offset, sequence = 0, 0
            while offset < proof['bytes']:
                transport.disk_guard(CHUNK)
                path = transport.directory / 'part'
                value = write_chunk(stream, path)
                require(value['bytes'] == min(CHUNK, proof['bytes']-offset), 'canonical chunk size')
                asset, downloaded = transport.upload(f'part-{sequence:04d}', path, name+f'.part{sequence:04d}', value)
                reconstruction.append(downloaded, value); downloaded.unlink()
                parts.append(dict(sequence=sequence, offset=offset, **value, asset=asset, downloaded_verified=True))
                transport.record['parts'] = parts; transport.persist()
                offset += value['bytes']; sequence += 1
            require(not stream.read(1), 'certificate exact EOF')
        require(identity(source) == proof, 'unchanged full certificate after staging')
        reconstructed = reconstruction.finish(proof)
        metadata = transport.metadata(name)
        _, compiler, job = state.paths()
        pending = dict(schema='trident/whole-proof-pending/v2', status='pending-fresh-verification',
                       **{k: r[k] for k in ('run', 'generation', 'profile', 'source_selector', 'input_asset')},
                       proof=proof, parts=parts, downloaded_reconstruction=reconstructed,
                       compiler=identity(compiler), job=identity(job), production=r['production'],
                       producer_binary=r['binary'], producer_tools=r['tools'], metadata=metadata,
                       producer_receipt=identity(state.results / 'producer-receipt.json'))
        validate_pending(pending, state)
        candidate = transport.directory / 'pending.json'; save(candidate, pending)
        expected = identity(candidate)
        require(expected['bytes'] <= 2 * 1024**2, 'bounded pending manifest')
        handoff = state.results / 'handoff'; handoff.mkdir()
        shutil.copy2(candidate, handoff / 'pending.json')
        asset, downloaded = transport.upload('manifest', candidate, name+'.pending.json', expected)
        downloaded.unlink()
        pointer = dict(schema='trident/whole-proof-handoff/v2', run=r['run'], generation=r['generation'],
                       status='pending-fresh-verification', manifest=expected, asset=asset)
        save(handoff / 'pointer.json', pointer)
        transport.finish('pending-staged')
        r['pending'] = pointer; r['status'] = 'pending-staged'; state.persist()
    except BaseException:
        transport.failed(); raise


def admit_handoff(state, handoff):
    require(handoff.is_dir() and not handoff.is_symlink(), 'regular handoff directory')
    require({p.name for p in handoff.iterdir()} == {'pointer.json', 'pending.json'}, 'exact small handoff files')
    for p in handoff.iterdir():
        require(p.is_file() and not p.is_symlink() and p.stat().st_size <= 2 * 1024**2, 'bounded handoff file')
    pointer, pending = load(handoff / 'pointer.json'), load(handoff / 'pending.json')
    require(pointer['schema'] == 'trident/whole-proof-handoff/v2' and pointer['status'] == 'pending-fresh-verification' and
            pointer['run'] == state.report['run'] and pointer['generation'] == state.report['generation'], 'same-run pending handoff')
    require(identity(handoff / 'pending.json') == pointer['manifest'], 'handoff manifest bytes')
    check_asset(pointer['asset'], pointer['asset']['name'], pointer['manifest'])
    validate_pending(pending, state)
    return pointer, pending


def download(state, handoff):
    r = state.report
    require(r['phase'] == 'verifier' and r['status'] == 'prepared', 'fresh prepared verifier')
    require(shutil.disk_usage(state.work).free >= PROFILE['minimum_free_start_bytes'], '48 GiB free before reconstruction')
    pointer, pending = admit_handoff(state, handoff)
    transport = Transport(state, 'download')
    try:
        manifest = transport.download('manifest', pointer['asset'], pointer['manifest'])
        require(manifest.read_bytes() == (handoff / 'pending.json').read_bytes(), 'independently downloaded exact manifest')
        shutil.copy2(manifest, state.results / 'pending.json'); manifest.unlink()
        save(state.results / 'pending-pointer.json', pointer)
        directory = state.work / 'download'; directory.mkdir()
        proof = directory / 'certificate.joysc'; reconstruction = Reconstruction()
        transport.disk_guard(pending['proof']['bytes'] + CHUNK)
        with proof.open('xb') as output:
            for part in pending['parts']:
                expected = {k: part[k] for k in ('bytes', 'sha256')}
                path = transport.download(f"part-{part['sequence']:04d}", part['asset'], expected)
                reconstruction.append(path, expected, output); output.flush(); path.unlink()
                transport.disk_guard()
        reconstruction.finish(pending['proof'])
        require(identity(proof) == pending['proof'], 'reconstructed certificate bytes')
        transport.finish('downloaded-pending-verification')
        r.update(status='downloaded-pending-verification', pending=pointer,
                 proof=dict(path=str(proof), **pending['proof']), production=pending['production'])
        state.persist()
    except BaseException:
        transport.failed(); raise


def verify(state):
    r = state.report
    require(r['phase'] == 'verifier' and r['status'] == 'downloaded-pending-verification', 'downloaded whole certificate')
    binary, compiler, job = state.paths(); proof = Path(r['proof']['path'])
    require(identity(proof) == {k: r['proof'][k] for k in ('bytes', 'sha256')}, 'exact pending certificate at verification')
    value = bounded(state, [binary, 'verify-artifact', compiler, '--input', job, '--proof', proof,
                           '--output', 'compiler.dag', '--emit', 'program', *flags('verifier', r['profile'])], [compiler, job, proof])
    accepted = load(state.package / f"inputs/accepted-c{r['generation']+1}-step.json")
    checked = frozen.compare(value, accepted, 'verify')
    for key in ('invocations', 'semantic_events', 'records', 'transport'):
        require(checked[key] == r['production'][key], 'complete producer/verifier coordinate: ' + key)
    artifact = state.work / 'verifier/compiler.dag'
    require(identity(artifact) == dict(bytes=9691488, sha256=PROFILE['expected_artifact_sha256']), 'exact complete C2/C3 ART1')
    shutil.copy2(artifact, state.results / 'compiler.dag')
    state.final_identities('verified')
    r.update(status='fresh-verified', verification=checked, compiled=identity(artifact)); state.persist()
    shutil.copy2(state.results / 'receipt.json', state.results / 'verifier-receipt.json')


def complete(state):
    r = state.report
    require(r['phase'] == 'verifier' and r['status'] == 'fresh-verified', 'independent fresh verification required')
    require(bootstrap(state.checkout) == r['bootstrap'], 'completion bootstrap stable')
    require(identity(Path(r['proof']['path'])) == {k: r['proof'][k] for k in ('bytes', 'sha256')}, 'verified complete bytes unchanged')
    require(identity(state.results / 'compiler.dag') == r['compiled'], 'verified compiler unchanged')
    pending = load(state.results / 'pending.json'); validate_pending(pending, state)
    require(identity(state.results / 'pending.json') == r['pending']['manifest'], 'exact pending identity at completion')
    transport = Transport(state, 'completion'); name = prefix(state, 'verified', pending['proof'])
    try:
        metadata = transport.metadata(name)
        value = dict(schema='trident/whole-proof-completion/v2', status='fresh-verified',
                     **{k: r[k] for k in ('run', 'generation', 'profile', 'source_selector', 'input_asset', 'verification', 'compiled')},
                     proof=pending['proof'], pending=r['pending'], metadata=metadata,
                     verifier_binary=r['binary'], verifier_tools=r['tools'],
                     verifier_receipt=identity(state.results / 'verifier-receipt.json'))
        path = transport.directory / 'completion.json'; save(path, value)
        expected = identity(path)
        shutil.copy2(path, state.results / 'completion.json')
        asset, downloaded = transport.upload('manifest', path, name+'.completion.json', expected)
        downloaded.unlink(); transport.finish('fresh-verified-retained')
        r['completion'] = dict(**expected, asset=asset); r['status'] = 'fresh-verified-retained'; state.persist()
    except BaseException:
        transport.failed(); raise


def main():
    host.cancellation_handlers()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'produce', 'stage', 'download', 'verify', 'complete'))
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--generation', type=int, choices=(1, 2))
    parser.add_argument('--phase', choices=('producer', 'verifier'))
    parser.add_argument('--handoff', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        require(args.generation in (1, 2) and args.phase in ('producer', 'verifier'), 'explicit preparation generation/phase')
    state = State(args.results, create=args.action == 'prepare', generation=args.generation, phase=args.phase)
    try:
        if args.action == 'download':
            require(args.handoff is not None, 'same-run handoff path required')
            download(state, args.handoff)
        else:
            {'prepare': prepare, 'produce': produce, 'stage': stage, 'verify': verify, 'complete': complete}[args.action](state)
    except BaseException:
        state.report.update(status='failed', error=traceback.format_exc()); state.persist(); raise
    print(json.dumps(dict(status=state.report['status'], generation=state.report['generation'], phase=state.report['phase'])))


if __name__ == '__main__':
    main()
