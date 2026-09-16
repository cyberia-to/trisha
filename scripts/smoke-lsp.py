"""Exercise the installed LSP over its real framed stdio protocol."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading


def smoke(binary):
    process = subprocess.Popen([str(Path(binary).resolve(strict=True))], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    messages = queue.Queue()

    def read():
        try:
            while True:
                header = process.stdout.readline()
                if not header:
                    return
                if not header.lower().startswith(b'content-length:'):
                    raise ValueError('invalid LSP frame')
                length = int(header.split(b':', 1)[1])
                if not 0 < length <= 1024 * 1024:
                    raise ValueError('invalid LSP frame length')
                if process.stdout.readline() != b'\r\n':
                    raise ValueError('invalid LSP header separator')
                raw = process.stdout.read(length)
                if len(raw) != length:
                    raise ValueError('truncated LSP response')
                messages.put(json.loads(raw))
        except Exception as error:
            messages.put(error)

    threading.Thread(target=read, daemon=True).start()

    def send(method, params=None, identifier=None):
        message = dict(jsonrpc='2.0', method=method)
        if params is not None:
            message['params'] = params
        if identifier is not None:
            message['id'] = identifier
        raw = json.dumps(message).encode()
        process.stdin.write(f'Content-Length: {len(raw)}\r\n\r\n'.encode() + raw)
        process.stdin.flush()

    def response(identifier):
        # Notifications can interleave with the response; bound their count too.
        for _ in range(32):
            message = messages.get(timeout=15)
            if isinstance(message, Exception):
                raise message
            if message.get('id') == identifier:
                if 'error' in message or 'result' not in message:
                    raise ValueError(f'LSP request failed: {message}')
                return message['result']
        raise ValueError('LSP response missing')

    try:
        send('initialize', dict(processId=None, rootUri=None, capabilities={}), 1)
        result = response(1)
        if not isinstance(result, dict) or not isinstance(result.get('capabilities'), dict):
            raise ValueError('LSP did not advertise capabilities')
        send('initialized', {})
        send('shutdown', identifier=2)
        if response(2) is not None:
            raise ValueError('invalid LSP shutdown response')
        send('exit')
        process.stdin.close()
        if process.wait(timeout=15) != 0:
            raise ValueError('LSP exited unsuccessfully')
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
    print('PASS: installed LSP initialize/shutdown/exit')


if __name__ == '__main__':
    smoke(sys.argv[1])
