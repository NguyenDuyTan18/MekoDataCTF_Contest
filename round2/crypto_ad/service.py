"""Shared transport, flag storage, and service bootstrap for Round 2 crypto challenges.

Challenge-specific code lives in challenges/<service>/challenge.py. This is an
educational lab model, not vulnerable Windows CryptoAPI or OpenSSL.
"""
import argparse
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socketserver
import sqlite3
import sys
import threading
from protocol import G, N, MAX_LINE, SERVICES
from challenges.curveball import challenge as curveball
from challenges.padding_oracle import challenge as padding_oracle
from challenges.ecdsa_nonce import challenge as ecdsa_nonce

CHALLENGES = {
    'curveball': curveball,
    'padding_oracle': padding_oracle,
    'ecdsa_nonce': ecdsa_nonce,
}


class Service:
    def __init__(self, name, config):
        if name not in SERVICES:
            raise ValueError('unknown service')
        self.name = name
        self.config = config
        self.patched = str(os.environ.get('PATCHED', config.get('patched', '0'))) == '1'
        self.path = Path(config['data_dir']) / (name + '.sqlite')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS secrets (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS flags (id TEXT PRIMARY KEY, value TEXT NOT NULL, tick INTEGER NOT NULL);''')
            for key in ('private', 'nonce', 'aes', 'mac'):
                db.execute('INSERT OR IGNORE INTO secrets VALUES (?, ?)', (key, secrets.token_hex(32)))
            self.keys = dict(db.execute('SELECT key,value FROM secrets'))
        self.private = int(self.keys['private'], 16) % (N - 1) + 1
        self.nonce = int(self.keys['nonce'], 16) % (N - 1) + 1
        self.public = G * self.private

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute('PRAGMA journal_mode=WAL')
        return db

    def flag(self, record):
        with self.connect() as db:
            row = db.execute('SELECT value FROM flags WHERE id=?', (record,)).fetchone()
        if not row:
            raise ValueError('record')
        return row[0]

    def dispatch(self, req):
        op = req.get('op')
        if op == 'info':
            return {'ok': True, 'service': self.name, 'protocol': 'line-json-v1',
                    'patched': self.patched,
                    'operations': CHALLENGES[self.name].OPERATIONS}
        if op in ('put', 'get', 'prune'):
            token = req.get('token', '')
            if not isinstance(token, str) or not hmac.compare_digest(token, self.config['admin_token']):
                return {'ok': False, 'error': 'unauthorized'}
            if op == 'get':
                return {'ok': True, 'flag': self.flag(req['record'])}
            if op == 'prune':
                with self.connect() as db:
                    db.execute('DELETE FROM flags WHERE tick < ?', (int(req['before_tick']),))
                return {'ok': True}
            record, flag, tick = req['record'], req['flag'], int(req['tick'])
            if not isinstance(record, str) or not re.fullmatch(r'[a-f0-9]{24}', record):
                raise ValueError('record')
            if not isinstance(flag, str) or not re.fullmatch(r'MekoDataCTF\{[a-f0-9]{32}\}', flag):
                raise ValueError('flag')
            with self.connect() as db:
                existing = db.execute('SELECT value,tick FROM flags WHERE id=?', (record,)).fetchone()
                if existing and existing != (flag, tick):
                    return {'ok': False, 'error': 'record_conflict'}
                db.execute('INSERT OR IGNORE INTO flags VALUES (?,?,?)', (record, flag, tick))
            return {'ok': True, 'record': record}
        if op == 'targets':
            with self.connect() as db:
                rows = db.execute('SELECT id,tick FROM flags ORDER BY tick DESC,id LIMIT 30').fetchall()
            return {'ok': True, 'targets': [{'record': r, 'tick': t} for r, t in rows]}
        result = CHALLENGES[self.name].dispatch(self, op, req)
        return result if result is not None else {'ok': False, 'error': 'unknown_operation'}

    def handle(self, req):
        if not isinstance(req, dict):
            return {'ok': False, 'error': 'invalid_request'}
        try:
            return self.dispatch(req)
        except (ValueError, KeyError, TypeError, AssertionError, OverflowError):
            return {'ok': False, 'error': 'invalid_request'}


def serve_stream(service, source, output):
    while True:
        line = source.readline(MAX_LINE + 1)
        if not line:
            return
        if len(line) > MAX_LINE or not line.endswith(b'\n'):
            output.write(b'{"ok":false,"error":"line_too_long"}\n')
            output.flush()
            return
        try:
            result = service.handle(json.loads(line))
        except (ValueError, UnicodeError):
            result = {'ok': False, 'error': 'invalid_json'}
        output.write(json.dumps(result, separators=(',', ':')).encode() + b'\n')
        output.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--service', required=True, choices=SERVICES)
    parser.add_argument('--config', required=True)
    parser.add_argument('--stdio', action='store_true', help='ncat --exec transport')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    app = Service(args.service, config)
    if args.stdio:
        serve_stream(app, sys.stdin.buffer, sys.stdout.buffer)
        return
    slots = threading.BoundedSemaphore(96)

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(25)
            try:
                serve_stream(app, self.rfile, self.wfile)
            except (OSError, ValueError):
                pass

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

        def process_request(self, request, address):
            if not slots.acquire(blocking=False):
                request.close()
                return
            try:
                super().process_request(request, address)
            except Exception:
                slots.release()
                raise

        def process_request_thread(self, request, address):
            try:
                super().process_request_thread(request, address)
            finally:
                slots.release()

    with Server((args.host, args.port or SERVICES[args.service]), Handler) as server:
        print(f'{args.service} line-JSON listening on {args.host}:{server.server_address[1]}', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
