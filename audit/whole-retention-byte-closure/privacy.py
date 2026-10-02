"""Reject credential-bearing URLs and raw host process snapshots in this packet."""
import json
import re

SIGNED = re.compile(r'https?://[^\s"\'<>]*(?:[?&](?:sig|signature|token|access_token|x-amz-[^=&\s]+|x-goog-[^=&\s]+)=[^&\s"\'<>]+)', re.I)
TOKEN = re.compile(r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}\b')
PROCESS = re.compile(r'^\s*\d+\s+\d+(?:\s+\d+)?\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\w+\s+\d+\s+\d\d:\d\d:\d\d\s+\d{4}', re.M)


def scan(raw, name):
    text = raw.decode('utf-8')
    if SIGNED.search(text) or TOKEN.search(text):
        raise ValueError('credential-bearing URL/token: '+name)
    if PROCESS.search(text):
        raise ValueError('raw process snapshot: '+name)
    if name.endswith('.json'):
        def visit(value):
            if isinstance(value, dict):
                if any(k in value for k in ('raw_stdout', 'raw_stderr')):
                    raise ValueError('embedded raw process/command stream: '+name)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(json.loads(text))
