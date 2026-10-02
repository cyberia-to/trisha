"""Strict fresh-origin inputs and native-host guards for the public-proof gate."""
import hashlib
import json
import os
from pathlib import Path
import re

REPOSITORIES = frozenset('bbg hemera honeycrisp joy lens neuron nox strata tade trident trisha zheng'.split())
TARGETS = {
    'aarch64-apple-darwin': ('Darwin', 'arm64'),
    'x86_64-apple-darwin': ('Darwin', 'x86_64'),
    'aarch64-unknown-linux-gnu': ('Linux', 'arm64'),
    'x86_64-unknown-linux-gnu': ('Linux', 'x86_64'),
    'aarch64-pc-windows-msvc': ('Windows', 'arm64'),
    'x86_64-pc-windows-msvc': ('Windows', 'x86_64'),
}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def selector(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate selector key')
            value[key] = item
        return value
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)
    require(set(value) == {'format', 'rust', 'sources'}, 'selector fields')
    require(value['format'] == 'native-public-proof-profile-v1', 'selector format')
    require(value['rust'] == '1.89.0', 'exact Rust version required')
    sources = value['sources']
    require(isinstance(sources, dict) and set(sources) == REPOSITORIES, 'complete source closure required')
    for name, revision in sources.items():
        require(isinstance(revision, str) and re.fullmatch('[0-9a-f]{40}', revision), 'full source commit: ' + name)
    return value


def native_host(target, system, machine, rustc=None, cargo=None):
    require(target in TARGETS, 'unknown native target')
    machine = machine.lower().replace('amd64', 'x86_64').replace('aarch64', 'arm64')
    require((system, machine) == TARGETS[target], 'runner OS/architecture mismatch')
    if rustc is not None:
        require(re.search(r'^release: 1\.89\.0$', rustc, re.M), 'wrong rustc version')
        require(re.search(r'^host: ' + re.escape(target) + '$', rustc, re.M), 'compiler host is not selected native target')
    if cargo is not None:
        require(re.search(r'^cargo 1\.89\.0 ', cargo), 'wrong cargo version')


def sanitized(environment):
    value = {key: item for key, item in environment.items()
             if not any(word in key.upper() for word in ('TOKEN', 'PASSWORD', 'SECRET', 'CREDENTIAL'))
             and not key.startswith(('GIT_', 'ACTIONS_ID_TOKEN_', 'RUST', 'CARGO_', 'CC_',
                                     'CXX_', 'AR_', 'CFLAGS_', 'CXXFLAGS_', 'LDFLAGS_'))
             and key not in {'SSH_AUTH_SOCK', 'SSH_AGENT_PID', 'CC', 'CXX', 'AR', 'CFLAGS',
                            'CXXFLAGS', 'LDFLAGS', 'SDKROOT', 'MACOSX_DEPLOYMENT_TARGET'}}
    value.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                 PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    return value


def fetch(family, sources, run):
    family.mkdir()
    for name, revision in sorted(sources.items()):
        dest = family / name
        run(name + '-init', ['git', 'init', dest])
        for key, value in [('core.autocrlf', 'false'), ('core.eol', 'lf'), ('core.symlinks', 'true')]:
            run(name + '-' + key, ['git', '-C', dest, 'config', key, value])
        run(name + '-origin', ['git', '-C', dest, 'remote', 'add', 'origin',
                              'https://github.com/cyberia-to/' + name + '.git'])
        run(name + '-fetch', ['git', '-C', dest, 'fetch', '--depth=1', 'origin', revision])
        run(name + '-checkout', ['git', '-C', dest, 'checkout', '--detach', 'FETCH_HEAD'])
        actual = run(name + '-head', ['git', '-C', dest, 'rev-parse', 'HEAD']).strip()
        require(actual == revision, 'origin commit mismatch: ' + name)


def inventory(family, sources, run, suffix):
    family = family.resolve(strict=True)
    result = {}
    for name, revision in sorted(sources.items()):
        root = family / name
        require(not run(name + '-status-' + suffix, ['git', '-C', root, 'status', '--porcelain=v1', '--untracked-files=all']).strip(),
                'source tree changed: ' + name)
        listing = run(name + '-files-' + suffix, ['git', '-C', root, 'ls-files', '--stage', '-z'])
        files = []
        for entry in filter(None, listing.split('\0')):
            header, relative = entry.split('\t', 1)
            mode, blob, stage = header.split()
            require(stage == '0' and mode in {'100644', '100755', '120000'}, 'unsupported tracked source mode')
            require(relative and not Path(relative).is_absolute() and '..' not in Path(relative).parts, 'unsafe source path')
            path = root / relative
            if mode == '120000':
                require(path.is_symlink(), 'source symlink was flattened: ' + str(path))
                target = os.readlink(path)
                require(not os.path.isabs(target), 'absolute source symlink')
                resolved = path.resolve(strict=True)
                require(resolved.is_relative_to(family) and resolved.is_file(), 'source symlink escapes closure')
                raw = target.replace('\\', '/').encode() if os.name == 'nt' else target.encode()
                digest, size = hashlib.sha256(raw).hexdigest(), len(raw)
            else:
                require(path.is_file() and not path.is_symlink(), 'source regular file missing')
                digest, size = sha(path), path.stat().st_size
            files.append(dict(path=relative, mode=mode, git_blob=blob, sha256=digest, bytes=size))
        actual = set()
        for folder, dirs, names in os.walk(root, followlinks=False):
            if Path(folder) == root:
                dirs[:] = [d for d in dirs if d != '.git']
            for item in names + [d for d in dirs if (Path(folder) / d).is_symlink()]:
                actual.add((Path(folder) / item).relative_to(root).as_posix())
        require(actual == {f['path'] for f in files}, 'unrecorded or missing source file: ' + name)
        result[name] = dict(commit=revision, files=files)
    return result


def closure(metadata, family, sources):
    family = family.resolve(strict=True)
    packages = []
    for package in metadata['packages']:
        path = Path(package['manifest_path']).resolve(strict=True)
        if package['source'] is None:
            require(path.is_relative_to(family), 'local Cargo dependency escapes pinned family')
            repository = path.relative_to(family).parts[0]
            require(repository in sources, 'unselected local repository')
            origin = dict(repository=repository, commit=sources[repository], manifest=path.relative_to(family).as_posix())
        else:
            origin = dict(source=package['source'])
        packages.append(dict(name=package['name'], version=package['version'], origin=origin))
    require(packages, 'empty resolved Cargo closure')
    return packages


def passed_tests(output, required=()):
    names = set(re.findall(r'^test (\S+) \.\.\. ok$', output, re.M))
    require(names, 'no passing tests were executed')
    for name in required:
        require(any(n == name or n.endswith('::' + name) for n in names), 'required test missing: ' + name)
    return sorted(names)


def warnings(output):
    return re.findall(r'^warning(?:\[[^\]\r\n]+\])?:[^\r\n]*', output, re.M)
