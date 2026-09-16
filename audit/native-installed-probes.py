"""Independent native process/file probes for exact, already-built release binaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime(path):
    if os.name != 'nt':
        command = ['otool', '-L', str(path)] if platform.system() == 'Darwin' else ['ldd', str(path)]
        text = subprocess.check_output(command, text=True)
        if 'not found' in text:
            raise AssertionError('binary has an unresolved shared library')
        return text
    data = path.read_bytes()
    header = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[header:header+4] == b'PE\0\0'
    machine, sections = struct.unpack_from('<HH', data, header+4)
    optional_size = struct.unpack_from('<H', data, header+20)[0]
    optional = header+24
    assert struct.unpack_from('<H', data, optional)[0] == 0x20b
    imports_rva = struct.unpack_from('<I', data, optional+120)[0]
    table = optional+optional_size

    def offset(rva):
        for index in range(sections):
            virtual_size, virtual_address, raw_size, raw_address = struct.unpack_from('<IIII', data, table+40*index+8)
            if virtual_address <= rva < virtual_address+max(virtual_size, raw_size):
                return raw_address+rva-virtual_address
        raise AssertionError(f'unknown PE RVA {rva}')

    position = offset(imports_rva)
    imports = []
    while any(data[position:position+20]):
        name = offset(struct.unpack_from('<I', data, position+12)[0])
        imports.append(data[name:data.index(0, name)].decode('ascii'))
        position += 20
    if any(re.match(r'(vcruntime|msvcp\d|msvcr\d)', name, re.I) for name in imports):
        raise AssertionError(f'release binary requires a separately installed MSVC runtime: {imports}')
    return dict(machine=hex(machine), imports=imports)


def verify(prefix, receipt):
    suffix = '.exe' if os.name == 'nt' else ''
    bins = {name: prefix/'bin'/(name+suffix) for name in ('trident', 'trident-lsp', 'trisha', 'joy')}
    identities = {name: sha(path) for name, path in bins.items()}
    runtimes = {name: runtime(path) for name, path in bins.items()}
    candidate = json.loads((prefix/'candidate.json').read_text())
    assert identities == {v['name']: v['sha256'] for v in candidate['binaries']}
    fixture = Path(__file__).with_name('native-neptune-fixture.rs')
    checks = []
    with tempfile.TemporaryDirectory(prefix='native probes пробел ') as directory:
        root = Path(directory).resolve()
        mock = root/('neptune-cli'+suffix)
        subprocess.run(['rustc', '--edition=2021', '-O', str(fixture), '-o', str(mock)], check=True)
        env = dict(os.environ, PATH=str(root), NEPTUNE_DATA_DIR=str(root/'data'),
                   FIXTURE_DATA=str(root/'data'), TRISHA_CONFIG_DIR=str(root/'config'), WLOG=str(root/'calls'))
        for name in ('NODE_REPLY', 'NODE_NETWORK', 'WALLET_PATH', 'LAST_INDEX', 'FAIL_ZERO'):
            env.pop(name, None)

        def run(name, args, success=True, extra=None, stdin=None):
            result = subprocess.run([str(bins[name]), *args], cwd=root, env=dict(env, **(extra or {})),
                                    input=stdin, capture_output=True, text=True, encoding='utf-8',
                                    errors='replace', timeout=30)
            if (result.returncode == 0) != success:
                raise AssertionError(f'{name} {args}: {result.returncode}: {result.stdout} {result.stderr}')
            checks.append(dict(binary=name, args=args, exit_code=result.returncode))
            return result

        def wallet(network='testnet-0'):
            return root/'data'/network/'wallet/wallet.dat'

        def neuron(args, **kwargs):
            return run('trisha', ['neuron', '--state', 'testnet', *args], **kwargs)

        def calls():
            return (root/'calls').read_text() if (root/'calls').exists() else ''

        run('trisha', ['node', 'status'], success=False, extra={'NODE_REPLY': 'offline'})
        status = run('trisha', ['node', 'status'])
        assert 'Block height : 123' in status.stdout and 'Mempool txs  : 7' in status.stdout
        run('trisha', ['node', 'status'], success=False, extra={'NODE_REPLY': 'malformed'})
        neuron(['address', 'add', '--index', '42'])
        assert 'nth-receiving-address|42|generation|--network|testnet-0|' in calls()
        before = calls()
        neuron(['address', 'add', '--key-type', 'symmetric'], success=False)
        assert calls() == before
        before = calls().count('nth-receiving-address')
        addresses = neuron(['address', 'list', '--start', '8', '--limit', '3'],
                           extra={'LAST_INDEX': str(2**64-1)})
        assert len(addresses.stdout.splitlines()) == 3 and calls().count('nth-receiving-address') == before+3
        neuron(['address', 'list', '--limit', '1001'], success=False)
        neuron(['address', 'add'], success=False, extra={'NODE_NETWORK': 'main'})
        neuron(['create'], success=False, extra={'FAIL_ZERO': '1'})
        assert not wallet().exists()
        created = neuron(['create'])
        assert wallet().is_file() and not wallet('main').exists()
        assert 'SEED PHRASE' not in created.stdout+created.stderr
        neuron(['create'], success=False)
        wallet('main').parent.mkdir(parents=True)
        wallet('main').write_text('other network fixture')
        neuron(['remove'])
        assert wallet().is_file()
        neuron(['remove', '--confirm'], success=False, extra={'WALLET_PATH': str(wallet('main'))})
        assert wallet('main').is_file()
        neuron(['remove', '--confirm'])
        assert not wallet().exists() and wallet('main').is_file()
        wallet().parent.symlink_to(wallet('main').parent, target_is_directory=True)
        neuron(['remove', '--confirm'], success=False)
        assert wallet('main').is_file()
        if os.name == 'nt':
            os.rmdir(wallet().parent)
        else:
            wallet().parent.unlink()
        imported = neuron(['import'], stdin='private-test-words\n')
        assert wallet().is_file() and 'private-test-words' not in imported.stdout+imported.stderr+calls()
        neuron(['address', 'hide', 'mock-address-0'])
        assert (root/'config/testnet-0/hidden_addresses').is_file()
        assert not (root/'config/main/hidden_addresses').exists()

        (root/'entry.tri').write_text('program entry\nfn main(){pub_write(pub_read()+3)}\n')
        (root/'valid.json').write_text('{"schema_version":1,"public":[2],"secret":[],"digests":[]}')
        assert run('trisha', ['run', 'entry.tri', '--input-file', 'valid.json']).stdout.strip() == '5'
        (root/'directory').mkdir()
        (root/'link.json').symlink_to(root/'valid.json')
        with (root/'oversized').open('wb') as stream:
            stream.truncate(64*1024*1024+1)
        for file in ('directory', 'link.json', 'oversized'):
            run('trisha', ['run', 'entry.tri', '--input-file', file], success=False)
            run('trisha', ['verify', file], success=False)
            run('joy', ['verify', 'entry.tri', '--proof', file], success=False)
        (root/'invalid.json').write_text('{"secret":"private_witness_must_not_leak"')
        rejected = run('trisha', ['run', 'entry.tri', '--input-file', 'invalid.json'], success=False)
        assert 'private_witness_must_not_leak' not in rejected.stdout+rejected.stderr
        if os.name == 'nt':
            for file in ('NUL', 'CON', r'\\.\pipe\cyber-release-no-server'):
                run('trisha', ['run', 'entry.tri', '--input-file', file], success=False)
                run('joy', ['verify', 'entry.tri', '--proof', file], success=False)
    assert identities == {name: sha(path) for name, path in bins.items()}
    with receipt.open('x', encoding='utf-8') as stream:
        json.dump(dict(all_checks_passed=True, platform=platform.platform(), binaries=identities,
                       runtime_dependencies=runtimes,
                       source_provenance_sha256=candidate['provenance_sha256'], checks=checks,
                       probe_sha256=sha(Path(__file__)), fixture_sha256=sha(fixture)), stream, indent=2)
    print(f'PASS: {len(checks)} native process/file checks')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    verify(args.candidate.resolve(), args.receipt.resolve())
