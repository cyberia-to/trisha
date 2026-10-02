"""Move authenticated native rehearsal outputs to the existing draft transport."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile
import traceback
import zipfile


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require_pinned_toolchain(candidate, target):
    observed = candidate.get('toolchain', '')
    if (not observed.startswith('rustc 1.89.0 ')
            or 'release: 1.89.0\n' not in observed
            or 'host: ' + target + '\n' not in observed):
        raise ValueError('candidate must record actual native Rust 1.89.0')
    return observed


def main():
    checkout = Path.cwd()
    spec = json.loads((checkout / os.environ.get('REHEARSAL_ASSETS_SELECTOR', '.github/native-rehearsal-assets.json')).read_text())
    if spec.get('validation_profile') == 'final-host-ceiling-v1' and spec.get('status') != 'active':
        raise ValueError('final asset selector is not activated')
    results = checkout / 'rehearsal-assets-results'
    results.mkdir()
    work = Path(os.environ['RUNNER_TEMP']) / 'native-rehearsal-assets'
    work.mkdir()
    report = dict(scope=spec['scope'], status='running', selector=spec, commands=[], assets=[])

    def save():
        (results / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')

    def api(name, endpoint, *, absent=False):
        command = ['gh', 'api', endpoint]
        result = subprocess.run(command, capture_output=True)
        for stream in ('stdout', 'stderr'):
            (results / (name + '.' + stream)).write_bytes(getattr(result, stream))
        report['commands'].append(dict(name=name, command=command, exit_code=result.returncode))
        save()
        data = json.loads(result.stdout)
        if absent:
            if result.returncode != 1 or str(data.get('status')) != '404':
                raise ValueError('draft tag must remain absent')
        elif result.returncode:
            raise RuntimeError(name + ' failed')
        return data

    def draft(name):
        data = api(name, 'repos/cyberia-to/trisha/releases/' + str(spec['release_id']))
        if data.get('draft') is not True or data['tag_name'] != spec['release_tag']:
            raise ValueError('existing unpublished draft required')
        api(name + '-tag', 'repos/cyberia-to/trisha/git/ref/tags/' + spec['release_tag'], absent=True)
        return data

    save()
    try:
        existing = {a['name'] for a in draft('draft-before')['assets']}
        selected = set()
        for entry in spec['producers']:
            target = entry['target']
            if target in selected:
                raise ValueError('duplicate native producer target')
            selected.add(target)
            run_id = str(entry['run_id'])
            run = api(target + '-run', 'repos/cyberia-to/trisha/actions/runs/' + run_id)
            if run['status'] != 'completed' or run['conclusion'] != 'success' or run['head_sha'] != entry['head_sha']:
                raise ValueError('successful exact producer run required')
            metadata = api(target + '-artifact', 'repos/cyberia-to/trisha/actions/artifacts/' + str(entry['artifact_id']))
            if (metadata['expired'] or metadata['name'] != 'candidate-' + target
                    or metadata['workflow_run']['id'] != entry['run_id']
                    or metadata['digest'] != 'sha256:' + entry['zip_sha256']):
                raise ValueError('producer artifact API identity mismatch')
            archive = work / (target + '.zip')
            command = ['gh', 'api', metadata['archive_download_url']]
            with archive.open('xb') as stream:
                result = subprocess.run(command, stdout=stream, stderr=subprocess.PIPE)
            report['commands'].append(dict(command=command, exit_code=result.returncode))
            (results / (target + '-download.stderr')).write_bytes(result.stderr)
            if result.returncode or sha(archive) != entry['zip_sha256']:
                raise ValueError('native artifact ZIP identity mismatch')
            restored = work / target
            restored.mkdir()
            with zipfile.ZipFile(archive) as content:
                names = set()
                for member in content.infolist():
                    if (member.filename in names or stat.S_ISLNK(member.external_attr >> 16)
                            or not (restored / member.filename).resolve().is_relative_to(restored.resolve())):
                        raise ValueError('unsafe artifact ZIP member')
                    names.add(member.filename)
                content.extractall(restored)
            if (restored / 'failure.txt').exists():
                raise ValueError('producer retained a failure')
            produced = json.loads((restored / 'archive.json').read_text())
            candidate = json.loads((restored / 'candidate.json').read_text())
            corpus = json.loads((restored / 'proof-corpus/corpus.json').read_text())
            if (produced['target'] != target or produced['source']['source_sha256'] != spec['source_sha256']
                    or produced['source']['selfhost_kit']['sha256'] != spec['kit_sha256']
                    or candidate['provenance_sha256'] != spec['provenance_sha256']
                    or corpus['source_provenance_sha256'] != spec['provenance_sha256']):
                raise ValueError('producer source/kit provenance mismatch')
            observed_toolchain = require_pinned_toolchain(candidate, target)
            observed = dict(target=target, rustc=observed_toolchain,
                            cargo_version_observation='not separately recorded by the frozen producer')
            current = spec.get('validation_profile') in ('current-package-v1', 'final-host-ceiling-v1')
            if current:
                if produced['source'].get('validation_profile') != spec['validation_profile']:
                    raise ValueError('current package producer validation profile differs')
                paths = json.loads((restored / 'toolchain-paths.json').read_text())
                for name in ('rustc', 'cargo', 'rustdoc'):
                    if not paths[name]['version'].startswith(name + ' 1.89.0 '):
                        raise ValueError('actual producer tool version differs: ' + name)
                if paths['rustc']['version'] != observed_toolchain:
                    raise ValueError('preflight and candidate compiler differ')
                impact = json.loads((restored / 'source-impact.json').read_text())
                if (impact['status'] != 'passed' or impact['source_provenance_sha256'] != spec['provenance_sha256']
                        or impact['selector_sha256'] != spec['inputs_sha256']):
                    raise ValueError('current package source impact guard differs')
                observed.update(cargo_version_observation=paths['cargo']['version'], rustdoc=paths['rustdoc']['version'])
            if spec.get('validation_profile') == 'final-host-ceiling-v1':
                deadline = json.loads((restored / 'installed-host-ceiling/receipt.json').read_text())
                joy = next(row['sha256'] for row in candidate['binaries'] if row['name'] == 'joy')
                if (deadline['status'] != 'passed' or deadline['accepted'] != 15 or deadline['rejected'] != 8
                        or len(deadline['commands']) != 23 or deadline['joy']['sha256'] != joy
                        or deadline['source_provenance_sha256'] != spec['provenance_sha256']
                        or deadline['candidate_sha256'] != sha(restored / 'candidate.json')):
                    raise ValueError('final installed deadline probe differs from actual native package')
            report.setdefault('producer_toolchains', []).append(observed)
            binary = restored / produced['archive']
            if binary.parent != restored or sha(binary) != produced['sha256']:
                raise ValueError('native binary archive identity mismatch')
            proof = restored / ('proof-corpus-' + target + '.tar.gz')
            with tarfile.open(proof) as content:
                member = content.getmember('proof-corpus/corpus.json')
                if not member.isfile() or content.extractfile(member).read() != (restored / 'proof-corpus/corpus.json').read_bytes():
                    raise ValueError('corpus archive differs from retained producer inventory')
            # Preserve the authenticated Actions container beyond its retention
            # period as well as the exact deployable binary and proof archives.
            # This is the original ZIP, not a reconstructed evidence bundle.
            payloads = [('binary', binary), ('corpus', proof)]
            if current:
                structured = restored / ('structured-corpus-' + target + '.tar.gz')
                manifest_path = restored / 'structured-corpus/corpus.json'
                manifest = json.loads(manifest_path.read_text())
                verified = json.loads((restored / 'local-structured-verification.json').read_text())
                producer_joy = next(row['sha256'] for row in candidate['binaries'] if row['name'] == 'joy')
                if (manifest['schema'] != 'joy/current-package-structured-corpus/v1'
                        or manifest['source_provenance_sha256'] != spec['provenance_sha256']
                        or manifest['producer_joy_sha256'] != producer_joy
                        or manifest['producer_platform'] != candidate['platform']
                        or len(manifest['cases']) != 27 or len(verified['cases']) != 27
                        or verified['all_checks_passed'] is not True
                        or verified['corpus_sha256'] != sha(manifest_path)
                        or verified['consumer_joy']['sha256'] != producer_joy):
                    raise ValueError('current structured corpus producer identity differs')
                with tarfile.open(structured) as content:
                    if content.extractfile('structured-corpus/corpus.json').read() != manifest_path.read_bytes():
                        raise ValueError('structured corpus archive identity differs')
                payloads.append(('structured-corpus', structured))
            payloads.append(('evidence', archive))
            for kind, source in payloads:
                name = spec['asset_prefix'] + '-' + source.name
                if name in existing:
                    raise ValueError('unique transport asset name is occupied')
                named = work / name
                source.rename(named)
                digest = sha(named)
                command = ['gh', 'release', 'upload', spec['release_tag'], str(named), '--repo', 'cyberia-to/trisha']
                result = subprocess.run(command, capture_output=True)
                for stream in ('stdout', 'stderr'):
                    (results / (target + '-' + kind + '-upload.' + stream)).write_bytes(getattr(result, stream))
                report['commands'].append(dict(command=command, exit_code=result.returncode))
                if result.returncode:
                    raise RuntimeError('draft asset upload failed')
                release = draft(target + '-' + kind + '-draft')
                asset = next(a for a in release['assets'] if a['name'] == name)
                if asset.get('digest') != 'sha256:' + digest or asset['size'] != named.stat().st_size:
                    raise ValueError('uploaded native archive identity mismatch')
                report['assets'].append(dict(kind=kind, target=target, asset_id=asset['id'], name=name,
                                             sha256=digest, bytes=named.stat().st_size,
                                             producer_run_id=entry['run_id'], producer_artifact_id=entry['artifact_id']))
                save()
                print(target, kind, asset['id'], digest, flush=True)
        report['status'] = 'passed'
    except BaseException:
        report.update(status='failed', error=traceback.format_exc())
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
