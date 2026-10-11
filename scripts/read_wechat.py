"""Local-only WeChat reader. Derived backend: wechatauto-replica (Apache-2.0)."""
import argparse
import contextlib
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import sys
import subprocess
import re
import time
import types
import shutil


class AmbiguousAttachment(ValueError):
    pass


def safe_output(directory, name):
    root = Path(directory).resolve()
    target = (root / name).resolve()
    if target.parent != root or Path(name).name != name:
        raise ValueError('Invalid media filename.')
    root.mkdir(parents=True, exist_ok=True)
    return str(target)


def copy_unique_file(md, row, chat, local_id, directory):
    name = md._file_name(row)
    if not name:
        return None
    base = Path(md.db.account_dir) / 'msg' / 'file'
    matches = [p for p in base.rglob('*') if p.is_file() and p.name == name]
    if len(matches) > 1:
        raise AmbiguousAttachment('Ambiguous local attachment; refusing an arbitrary copy.')
    if not matches:
        return None
    destination = safe_output(directory, '%s_%s_%s' % (chat, local_id, name))
    shutil.copyfile(matches[0], destination)
    return destination


@contextlib.contextmanager
def locked(state, timeout=30):
    import msvcrt
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'query.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Reader busy; retry after the other read finishes.')
                time.sleep(0.1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def load_backend(state):
    os.environ['WECHATAUTO_KEYS_DIR'] = str(state / 'keys')
    logger = types.ModuleType('wechatauto.logger')
    logger.wxlog = logging.getLogger('wechat-local-read')
    logger.wxlog.disabled = True
    sys.modules['wechatauto.logger'] = logger
    pkg = types.ModuleType('wechat_reader_vendor')
    pkg.__path__ = [str(Path(__file__).parent / 'vendor')]
    sys.modules[pkg.__name__] = pkg
    modules = []
    for name in ('db', 'media'):
        spec = importlib.util.spec_from_file_location(pkg.__name__ + '.' + name,
            Path(__file__).parent / 'vendor' / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules.append(module)
    import psutil
    modules[0].WeChatDB._find_weixin_pids = lambda self: [
        p.pid for p in psutil.process_iter(['name'])
        if (p.info['name'] or '').lower() == 'weixin.exe']
    return modules


def contact_ready(db):
    contacts = [rel for rel, path, _ in db._db_files if Path(path).name == 'contact.db']
    if not contacts:
        raise RuntimeError('Contact database unavailable.')
    # Do not let the upstream optional contact helper swallow read failures.
    conn = db._open(contacts[0])
    conn.close()


class IncompleteHistory(RuntimeError):
    pass


def make_database(backend, state, account=None, db_dir=None):
    root = db_dir or backend.auto_detect_db_dir()
    if not root:
        raise RuntimeError('Data directory unavailable.')
    accounts = backend._find_account_dirs(root)
    if account is None:
        if len(accounts) != 1:
            raise ValueError('Multiple or no accounts; choose --account explicitly.')
        account = Path(accounts[0]).name
    if Path(account).name != account or account in ('.', '..'):
        raise ValueError('Account must be a directory name.')
    class ScopedDB(backend.WeChatDB):
        def _msg_row_to_dict(self, row):
            result = super()._msg_row_to_dict(row)
            shard = result.get('shard', '')
            cache = getattr(self, '_local_sender_maps', {})
            if shard not in cache:
                matches = [rel for rel in self._message_dbs()
                           if Path(rel).name == shard or rel.replace('\\', '__').replace('/', '__') == shard]
                mapping = {}
                if len(matches) == 1:
                    conn = self._open(matches[0])
                    try:
                        mapping = dict(conn.execute('SELECT rowid, user_name FROM Name2Id'))
                    finally:
                        conn.close()
                cache[shard] = mapping
                self._local_sender_maps = cache
            result['sender_username'] = cache[shard].get(row['real_sender_id'], '')
            return result

        def _try_other_accounts(self):
            return False

        def _select_account_by_keys(self, cands):
            return False

        def _stable_key_dirs(self):
            return [str(state / 'keys')]

        def _warn_once(self, key, *args):
            if isinstance(key, tuple) and key and key[0] in ('shard', 'voice'):
                raise IncompleteHistory('A message shard could not be read.')
            return super()._warn_once(key, *args)

        def get_message_row(self, user, local_id, local_type=None, shard=None):
            # WeChat 4.x may wrap an attachment subtype in the upper 32 bits.
            # Upstream media routines filter exact 49 and miss wrapped file rows.
            if local_type in (3, 34, 43, 49):
                row = super().get_message_row(user, local_id, shard=shard)
                if not row:
                    return None
                raw = row['local_type']
                base = raw & 0xFFFFFFFF if raw > 0xFFFF else raw
                if base != local_type:
                    return None
                return dict(row, local_type=base, raw_local_type=raw)
            return super().get_message_row(user, local_id, local_type=local_type, shard=shard)
    return ScopedDB(db_dir=root, account=account,
                    workdir=str(state / 'cache' / account))


def execute(args):
    if hasattr(args, 'chat') and not re.fullmatch(r'[A-Za-z0-9_@.-]+', args.chat):
        raise ValueError('Invalid chat ID.')
    state = Path(args.state_dir).resolve()
    with locked(state):
        backend, media = load_backend(state)
        db = make_database(backend, state, args.account, args.db_dir)
        contact_ready(db)
        if args.command == 'status':
            return {'ready': True, 'source_read_only': True, 'cache_enabled': True}
        if args.command == 'find':
            if not args.keyword.strip():
                raise ValueError('Name keyword must not be empty.')
            return {'chats': db.search_contact(args.keyword)[:args.limit]}
        if args.command == 'messages':
            rows = db.get_messages(args.chat, limit=args.limit, offset=args.offset)
            selected = []
            for row in rows:
                if not args.start <= row.get('create_time', 0) < args.end:
                    continue
                if args.keyword and args.keyword not in str(row.get('content', '')):
                    continue
                clean = {k: row.get(k) for k in
                         ('local_id', 'type', 'sender_username', 'create_time', 'shard')}
                # Image XML contains transport keys. Return an image marker instead.
                clean['content'] = row.get('content', '') if row.get('type') == '文本' else '[media: use image command for pictures]'
                selected.append(clean)
            return {'messages': selected, 'next_offset': args.offset + len(rows),
                    'end_of_history': len(rows) < args.limit, 'scanned': len(rows),
                    'filter_scope': 'current_page', 'ordering': 'newest_first'}
        md = media.MediaDownloader(db, save_dir=args.output_dir)
        md._out = lambda directory, name: safe_output(directory or md.save_dir, name)
        # Read a previous local image-key cache for migration; new writes stay scoped.
        load_key = md._load_persisted_key
        def cached_image_key():
            key = load_key()
            if key:
                return key
            legacy = state / 'cache' / 'image_keys.json'
            try:
                key = json.loads(legacy.read_text(encoding='utf-8')).get(db.account)
                if key and md._validate_key(key):
                    return key
            except (OSError, ValueError):
                pass
            return None
        md._load_persisted_key = cached_image_key
        # One scan per operation; no hidden two-minute interaction loop.
        scan = md._scan_aes_key
        md._scan_aes_key = lambda **kw: scan(monitor=False)
        if args.command == 'image-status':
            info = md.image_status(args.chat, args.local_id, shard=args.shard)
            info.pop('md5', None)
            info['original_available'] = info.pop('available', False)
            info['local_available'] = bool(info.get('tiers'))
            return info
        shard_dir = re.sub(r'[^a-zA-Z0-9_.-]', '_', args.shard)
        if shard_dir in ('.', '..', ''):
            raise ValueError('Invalid shard.')
        save_dir = str(Path(args.output_dir) / db.account / shard_dir)
        if args.command == 'media':
            kind = args.kind
            method = {'voice': md.download_voice, 'video': md.download_video,
                      'file': md.download_file}[kind]
            if kind == 'file':
                row = db.get_message_row(args.chat, args.local_id, local_type=49, shard=args.shard)
                path = copy_unique_file(md, row, args.chat, args.local_id, save_dir) if row else None
            else:
                path = method(args.chat, args.local_id, shard=args.shard, save_dir=save_dir)
            if path is None:
                return {'available': False, 'kind': kind,
                        'reason': 'No matching local media copy. Open/download it in WeChat and retry.'}
            size = Path(path).stat().st_size
            result = {'available': size > 0, 'kind': kind, 'path': path,
                      'bytes': size, 'decoded': False}
            if kind == 'file':
                result['identity_verified'] = False
                result['match_basis'] = 'unique local filename from message resource metadata'
            if kind == 'voice':
                with open(path, 'rb') as stream:
                    header = stream.read(10)
                result['silk_header_valid'] = header.startswith(b'#!SILK_V3') or header.startswith(b'\x02#!SILK_V3')
            return result
        path = md.download_image(args.chat, args.local_id, shard=args.shard,
                                 tier=args.tier,
                                 save_dir=save_dir)
        if path is None:
            return {'available': False, 'reason': 'No local copy at requested tier; open the image in WeChat and retry.'}
        if Path(path).suffix == '.wxgf':
            return {'available': False, 'reason': 'WXGF conversion failed; ensure imageio-ffmpeg is installed.', 'path': path}
        from PIL import Image
        with Image.open(path) as image:
            image.load()
            return {'available': True, 'path': path, 'width': image.width,
                    'height': image.height, 'requested_tier': args.tier}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir', required=True, help='Private local cache and keys directory; exclude from Git.')
    p.add_argument('--account')
    p.add_argument('--db-dir')
    p.add_argument('--timeout', type=int, default=180, help='Bound total worker execution time in seconds.')
    p.add_argument('--_worker', action='store_true', help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    f = sub.add_parser('find')
    f.add_argument('keyword')
    f.add_argument('--limit', type=int, default=20)
    m = sub.add_parser('messages')
    m.add_argument('--chat', required=True)
    m.add_argument('--limit', type=int, default=50)
    m.add_argument('--offset', type=int, default=0)
    m.add_argument('--keyword', default='')
    m.add_argument('--start', type=int, default=0)
    m.add_argument('--end', type=int, default=2**63)
    for command in ('image', 'image-status', 'media'):
        i = sub.add_parser(command)
        i.add_argument('--chat', required=True)
        i.add_argument('--local-id', type=int, required=True)
        i.add_argument('--shard', required=True)
        i.add_argument('--output-dir', required=True)
        i.add_argument('--tier', choices=['best', 'original', 'mid', 'thumb'], default='best')
        if command == 'media':
            i.add_argument('--kind', choices=['voice', 'video', 'file'], required=True)
    return p


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = parser().parse_args()
    if not 1 <= getattr(args, 'limit', 1) <= 100 or getattr(args, 'offset', 0) < 0 or args.timeout < 1:
        parser().error('Limit must be 1..100 and offset nonnegative.')
    if not args._worker:
        proc = None
        try:
            proc = subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()),
                                     '--_worker'] + sys.argv[1:], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, encoding='utf-8')
            stdout, stderr = proc.communicate(timeout=args.timeout)
            sys.stdout.write(stdout)
            return proc.returncode
        except subprocess.TimeoutExpired:
            import psutil
            try:
                descendants = psutil.Process(proc.pid).children(recursive=True)
            except psutil.Error:
                descendants = []
            for child in descendants:
                try:
                    child.kill()
                except psutil.Error:
                    pass
            proc.kill()
            proc.communicate()
            psutil.wait_procs(descendants, timeout=5)
            print(json.dumps({'error': 'Timeout', 'action': 'Reader stopped; open an image if needed, then retry.'}))
            return 1
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        # No keys, message contents or local account paths in error output.
        action = 'Keep WeChat logged in; for images open a picture, then retry. Check private state directory if failure persists.'
        if isinstance(exc, IncompleteHistory):
            action = 'Partial shard read rejected; do not treat this as end of history.'
        elif isinstance(exc, AmbiguousAttachment):
            action = 'Multiple local attachments share this filename; identify the correct file before copying.'
        elif isinstance(exc, ValueError):
            action = 'Check arguments; multiple-account machines require an explicit --account.'
        elif isinstance(exc, ModuleNotFoundError):
            action = 'Use 64-bit Windows Python and install requirements.txt in that environment.'
        print(json.dumps({'error': type(exc).__name__, 'action': action}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
