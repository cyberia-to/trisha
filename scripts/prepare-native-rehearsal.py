"""Reproduce a pinned source archive near GitHub's draft asset transport."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import traceback
import urllib.request


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    checkout = Path.cwd()
    spec = json.loads((checkout / '.github/native-rehearsal-source.json').read_text())
    results = checkout / 'rehearsal-source-results'
    results.mkdir()
    work = Path(os.environ['RUNNER_TEMP']) / 'native-rehearsal-source'
    work.mkdir()
    auth = dict(os.environ)
    env = dict(auth, RUSTUP_TOOLCHAIN='1.89.0', CARGO_BUILD_JOBS='2',
               PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS',
                'CARGO_BUILD_TARGET', 'CARGO_TARGET_DIR'):
        env.pop(key, None)
    report = dict(scope=spec['scope'], status='running', selector=spec, commands=[])

    def save():
        (results / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(name, command, *, authenticated=False, allowed=(0,), cwd=work):
        row = dict(name=name, command=list(map(str, command)), cwd=str(cwd))
        report['commands'].append(row)
        save()
        result = subprocess.run(row['command'], cwd=cwd, env=auth if authenticated else env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for stream in ('stdout', 'stderr'):
            path = results / (name + '.' + stream)
            path.write_bytes(getattr(result, stream))
            row[stream] = dict(path=path.name, bytes=path.stat().st_size, sha256=sha(path))
        row['exit_code'] = result.returncode
        save()
        if result.returncode not in allowed:
            print(result.stderr.decode(errors='replace')[-8000:], flush=True)
            raise RuntimeError(name + ' failed')
        print(name, result.returncode, flush=True)
        return result.stdout.decode()

    def draft(name):
        data = json.loads(run(name, ['gh', 'api', 'repos/cyberia-to/trisha/releases/'
                                     + str(spec['release_id'])], authenticated=True))
        if data.get('draft') is not True or data['tag_name'] != spec['release_tag']:
            raise ValueError('existing unpublished draft required')
        tag = json.loads(run(name + '-tag', ['gh', 'api', 'repos/cyberia-to/trisha/git/ref/tags/'
                                           + spec['release_tag']], authenticated=True, allowed=(1,)))
        if str(tag.get('status')) != '404':
            raise ValueError('draft tag must remain absent')
        return data

    save()
    try:
        before = draft('draft-before')
        if any(asset['name'] == spec['asset_name'] for asset in before['assets']):
            raise ValueError('transport asset name is occupied')
        family = work / 'family'
        family.mkdir()
        for source in spec['sources']:
            name = source['repository']
            destination = family / name
            url = 'https://github.com/cyberia-to/' + name + '.git'
            refs = run(name + '-origin', ['git', 'ls-remote', '--heads', url])
            if source['origin_head'] + '\t' + source['origin_ref'] not in refs.splitlines():
                raise ValueError('previously observed origin ref changed: ' + name)
            run(name + '-init', ['git', 'init', str(destination)])
            run(name + '-fetch', ['git', '-C', destination, 'fetch', '--depth=1', url, source['commit']])
            run(name + '-checkout', ['git', '-C', destination, 'checkout', '--detach', 'FETCH_HEAD'])
            if run(name + '-head', ['git', '-C', destination, 'rev-parse', 'HEAD']).strip() != source['commit']:
                raise ValueError('source commit mismatch')
        archive = work / 'nu.tar.gz'
        with urllib.request.urlopen('https://github.com/nushell/nushell/releases/download/0.112.2/nu-0.112.2-x86_64-unknown-linux-gnu.tar.gz', timeout=60) as response, archive.open('xb') as stream:
            while block := response.read(1 << 20):
                stream.write(block)
        if sha(archive) != '4038c171dd2618f2413a2aa615b8dab7e9d04852be8200f1755df3e422328395':
            raise ValueError('Nushell archive mismatch')
        nu_root = work / 'nu'
        nu_root.mkdir()
        with tarfile.open(archive) as content:
            content.extractall(nu_root, filter='data')
        nu = next(nu_root.rglob('nu'))
        env['PATH'] = str(nu.parent) + os.pathsep + env['PATH']
        run('rustup', ['rustup', 'toolchain', 'install', '1.89.0', '--profile', 'minimal'])
        run('vendor', [nu, '--no-config-file', family / 'trisha/patches/apply.nu'])
        run('source', [nu, '--no-config-file', family / 'trisha/scripts/package-source.nu', work / 'source-export'])
        source = work / 'source-export.tar.gz'
        report['archive'] = dict(bytes=source.stat().st_size, sha256=sha(source))
        save()
        if report['archive']['sha256'] != spec['source_sha256']:
            raise ValueError('remote archive differs from independently prepared pinned source')
        run('guard', ['python3', '-B', family / 'trisha/scripts/verify-source.py', work / 'source-export'])
        named = work / spec['asset_name']
        source.rename(named)
        run('upload', ['gh', 'release', 'upload', spec['release_tag'], named,
                       '--repo', 'cyberia-to/trisha'], authenticated=True)
        after = draft('draft-after')
        asset = next(item for item in after['assets'] if item['name'] == spec['asset_name'])
        if asset.get('digest') != 'sha256:' + spec['source_sha256'] or asset['size'] != named.stat().st_size:
            raise ValueError('uploaded source asset mismatch')
        report.update(status='passed', asset=asset)
    except BaseException:
        report.update(status='failed', error=traceback.format_exc())
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
