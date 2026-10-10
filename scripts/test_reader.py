"""Synthetic regression tests; no WeChat data or process-memory access."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import read_wechat as reader
import io
import struct


class FakeDB:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def _warn_once(self, key, *args):
        pass

    def get_message_row(self, user, local_id, local_type=None, shard=None):
        raw = (6 << 32) | 49
        return {'local_type': raw} if local_type is None else None


class ReaderTests(unittest.TestCase):
    def backend(self, accounts):
        return SimpleNamespace(WeChatDB=FakeDB, auto_detect_db_dir=lambda: 'root',
                               _find_account_dirs=lambda root: accounts)

    def test_account_and_cache_are_scoped(self):
        db = reader.make_database(self.backend(['root/a']), Path('private'))
        self.assertEqual(db.account, 'a')
        self.assertEqual(Path(db.workdir), Path('private/cache/a'))
        self.assertFalse(db._try_other_accounts())
        self.assertFalse(db._select_account_by_keys(['unused']))
        self.assertEqual(db._stable_key_dirs(), [str(Path('private/keys'))])

    def test_multiple_accounts_require_selection(self):
        backend = self.backend(['root/a', 'root/b'])
        with self.assertRaises(ValueError):
            reader.make_database(backend, Path('private'))
        db = reader.make_database(backend, Path('private'), 'b')
        self.assertEqual(db.account, 'b')

    def test_shard_failure_cannot_be_silent(self):
        db = reader.make_database(self.backend(['root/a']), Path('private'))
        with self.assertRaises(reader.IncompleteHistory):
            db._warn_once(('shard', 'fake.db', 'DatabaseError'), 'failure')

    def test_compound_file_type_is_recognized(self):
        db = reader.make_database(self.backend(['root/a']), Path('private'))
        row = db.get_message_row('synthetic', 1, local_type=49, shard='fake.db')
        self.assertEqual(row['local_type'], 49)
        self.assertEqual(row['raw_local_type'], (6 << 32) | 49)
        self.assertIsNone(db.get_message_row('synthetic', 1, local_type=43, shard='fake.db'))

    def test_source_account_path_traversal_rejected(self):
        for account in ('..', '.', '../a'):
            with self.assertRaises(ValueError):
                reader.make_database(self.backend(['root/a']), Path('private'), account)

    def test_command_scope(self):
        commands = reader.parser()._subparsers._group_actions[0].choices
        self.assertEqual(set(commands), {'status','find','messages','image','image-status','media'})

    def test_media_output_cannot_escape(self):
        with TemporaryDirectory() as temp:
            for name in ('../escape.jpg', 'nested/image.jpg', '..'):
                with self.assertRaises(ValueError):
                    reader.safe_output(temp, name)
            self.assertEqual(Path(reader.safe_output(temp, 'safe.jpg')).parent, Path(temp).resolve())

    def test_duplicate_attachment_names_are_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for month in ('2026-01', '2026-02'):
                folder = root / 'msg/file' / month
                folder.mkdir(parents=True)
                (folder / 'report.pdf').write_bytes(b'synthetic')
            md = SimpleNamespace(db=SimpleNamespace(account_dir=temp), _file_name=lambda row: 'report.pdf')
            with self.assertRaises(ValueError):
                reader.copy_unique_file(md, {}, 'synthetic', 1, root / 'export')
            self.assertFalse((root / 'export').exists())

    def test_synthetic_v2_png_is_decoded_and_loadable(self):
        from PIL import Image
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        with TemporaryDirectory() as temp:
            _, media = reader.load_backend(Path(temp))
            stream = io.BytesIO()
            Image.new('RGB', (4, 3), (23, 45, 67)).save(stream, format='PNG')
            plain = stream.getvalue()
            key, xor = '0123456789abcdef', 0x88
            aes_size, xor_size = 32, 8
            first = plain[:aes_size] + bytes([16]) * 16
            enc = Cipher(algorithms.AES(key.encode()), modes.ECB()).encryptor()
            encrypted = enc.update(first) + enc.finalize()
            data = media.V2_MAGIC + struct.pack('<LL', aes_size, xor_size) + b'\0'
            data += encrypted + plain[aes_size:-xor_size] + bytes(x ^ xor for x in plain[-xor_size:])
            source = Path(temp) / 'synthetic.dat'
            source.write_bytes(data)
            md = media.MediaDownloader(SimpleNamespace(), save_dir=temp)
            decoded = md.decrypt_image(str(source), aes_key=key, xor_key=xor)
            self.assertEqual(decoded, plain)
            with Image.open(io.BytesIO(decoded)) as image:
                image.load()
                self.assertEqual(image.getpixel((0, 0)), (23, 45, 67))

    def test_thumbnail_fallback_never_claims_original(self):
        from PIL import Image
        with TemporaryDirectory() as temp:
            _, media = reader.load_backend(Path(temp))
            stream = io.BytesIO()
            Image.new('RGB', (12, 8), (20, 40, 60)).save(stream, format='JPEG')
            plain = stream.getvalue()
            source = Path(temp) / 'thumbnail.dat'
            source.write_bytes(bytes(x ^ 0x88 for x in plain))
            db = SimpleNamespace(get_message_row=lambda *a, **kw: {'local_type': 3})
            md = media.MediaDownloader(db, save_dir=temp)
            md._img_md5 = lambda row: 'synthetic'
            md._image_files = lambda *a: {'thumb': (str(source), source.stat().st_size)}
            self.assertIsNone(md.download_image('synthetic-chat', 1, tier='original', shard='fake.db'))
            path = md.download_image('synthetic-chat', 1, tier='best', shard='fake.db')
            self.assertIn('_thumb', Path(path).name)
            with Image.open(path) as image:
                image.load()
                self.assertEqual(image.size, (12, 8))


if __name__ == '__main__':
    unittest.main()
