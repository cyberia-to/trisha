"""Bounded identities and chunks, adapted from Trisha ec05b13 whole retainer."""
import hashlib
import json
from pathlib import Path
import stat

GIB = 1024**3
CHUNK = GIB
REPO = 'cyberia-to/trisha'
RELEASE = 389977897
TAG = 'candidate-20260916.1'
SCOPE = 'fresh-verified complete certificate; SH8 acceptance pending'


def require(value, message):
    if not value:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def save_new(path, value):
    with Path(path).open('x') as output:
        json.dump(value, output, indent=2)
        output.write('\n')


def identity(path):
    path = Path(path)
    require(stat.S_ISREG(path.lstat().st_mode), 'regular non-symlink file: ' + str(path))
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while data := stream.read(1024**2):
            digest.update(data)
            size += len(data)
    return dict(bytes=size, sha256=digest.hexdigest())


def scan_parts(path, expected, chunk_size=CHUNK):
    require(type(chunk_size) is int and 0 < chunk_size <= CHUNK, 'positive bounded chunk')
    require(stat.S_ISREG(Path(path).lstat().st_mode), 'regular certificate')
    full, offset, parts = hashlib.sha256(), 0, []
    with Path(path).open('rb') as source:
        while offset < expected['bytes']:
            wanted = min(chunk_size, expected['bytes'] - offset)
            part, count = hashlib.sha256(), 0
            while count < wanted:
                data = source.read(min(1024**2, wanted - count))
                require(data, 'truncated certificate')
                part.update(data)
                full.update(data)
                count += len(data)
            parts.append(dict(sequence=len(parts), offset=offset, bytes=count, sha256=part.hexdigest()))
            offset += count
        require(not source.read(1), 'appended certificate bytes')
    require(dict(bytes=offset, sha256=full.hexdigest()) == expected, 'full certificate identity')
    return parts


def write_chunk(source, path, expected):
    digest, size = hashlib.sha256(), 0
    require(0 < expected['bytes'] <= CHUNK, 'bounded nonempty part')
    with Path(path).open('xb') as output:
        while size < expected['bytes']:
            data = source.read(min(1024**2, expected['bytes'] - size))
            require(data, 'truncated part')
            output.write(data)
            digest.update(data)
            size += len(data)
    require(dict(bytes=size, sha256=digest.hexdigest()) == expected, 'prepared part identity')


class Reconstruction:
    def __init__(self):
        self.digest = hashlib.sha256()
        self.bytes = 0
        self.sequence = 0

    def append(self, path, part):
        require(part['sequence'] == self.sequence and part['offset'] == self.bytes, 'ordered part')
        require(0 < part['bytes'] <= CHUNK, 'bounded part')
        expected = {k: part[k] for k in ('bytes', 'sha256')}
        require(identity(path) == expected, 'independently downloaded part bytes')
        with Path(path).open('rb') as stream:
            while data := stream.read(1024**2):
                self.digest.update(data)
                self.bytes += len(data)
        self.sequence += 1

    def finish(self, expected):
        actual = dict(bytes=self.bytes, sha256=self.digest.hexdigest())
        require(actual == expected, 'complete ordered download reconstruction')
        return actual


def check_asset(asset, name, expected):
    require(type(asset.get('id')) is int and asset['id'] > 0 and asset.get('state') == 'uploaded', 'uploaded numeric asset')
    require(asset['url'] == f"https://api.github.com/repos/{REPO}/releases/assets/{asset['id']}", 'fixed-repository asset URL')
    require(asset['name'] == name and asset['size'] == expected['bytes'] and
            asset.get('digest') == 'sha256:' + expected['sha256'], 'server asset identity')
