from pathlib import Path
from unittest import TestCase, mock
import io
import json
import struct
import tempfile
import os
import engine
import selector_patch


class ArchiveTests(TestCase):
    def fixture(self, root):
        ui = b'prefix;' + (Path(__file__).parent / 'fixtures/original-selector.js').read_bytes() + b';suffix'
        data = {'files': {'webview': {'files': {'assets': {'files': {'ui.js': {'offset': '0', 'size': len(ui), 'integrity': {
            'algorithm': 'SHA256', 'hash': engine.sha(ui), 'blockSize': 4096,
            'blocks': [engine.sha(ui[i:i+4096]) for i in range(0, len(ui), 4096)]}}}}}}}}
        raw = json.dumps(data).encode()
        pad = (-len(raw)) % 4
        pickle = struct.pack('<II', len(raw)+4+pad, len(raw)) + raw + b'\0'*pad
        source = root / 'original.asar'
        source.write_bytes(struct.pack('<II', 4, len(pickle)) + pickle + ui)
        launcher = root / 'ChatGPT.exe'
        launcher.write_bytes(b'fake-PE-' + engine.sha(raw).encode() + b'-end')
        plan = dict(selector_patch.analyze(ui)[0], ui='webview/assets/ui.js', uiHash=engine.sha(ui), headerHash=engine.sha(raw))
        return source, launcher, plan

    def test_patch_round_trip_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, launcher, spec = self.fixture(root)
            original = source.read_bytes()
            engine.patch_archive(source, root/'patched.asar', launcher, spec)
            value = engine.verify_archive(root/'patched.asar')
            self.assertIn(value.encode(), launcher.read_bytes())
            self.assertEqual(original, source.read_bytes())
            data = (root/'patched.asar').read_bytes()
            (root/'patched.asar').write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
            with self.assertRaisesRegex(RuntimeError, 'integrity failed'):
                engine.verify_archive(root/'patched.asar')

    def test_reject_wrong_ui_and_repeated_launcher_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, launcher, spec = self.fixture(root)
            with self.assertRaisesRegex(RuntimeError, 'UI changed'):
                engine.patch_archive(source, root/'wrong.asar', launcher, dict(spec, uiHash='wrong'))
            self.assertFalse((root/'wrong.asar').exists())
            launcher.write_bytes(launcher.read_bytes()*2)
            with self.assertRaisesRegex(RuntimeError, 'exactly one'):
                engine.patch_archive(source, root/'duplicate.asar', launcher, spec)

    def test_malformed_header(self):
        for data in [b'', b'0'*16, struct.pack('<4I', 4, 16, 12, 100)]:
            with self.assertRaises(RuntimeError): engine.header(io.BytesIO(data))


class StoreTests(TestCase):
    def test_powershell_environment_handles_uppercase_key(self):
        with mock.patch.dict(os.environ, {'PSMODULEPATH':'invalid'}, clear=True):
            self.assertFalse(any(k.lower() == 'psmodulepath' for k in engine.windows_env()))

    def test_concurrent_operation_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            store = engine.Store(Path(directory)/'data')
            with store.lock():
                with self.assertRaisesRegex(RuntimeError, 'Another patcher'):
                    with store.lock(): pass

    def test_block_installed_target_and_wrong_app(self):
        with self.assertRaisesRegex(RuntimeError, 'outside WindowsApps'):
            engine.Store(Path('C:/Program Files/WindowsApps/test'))
        with self.assertRaises(engine.UnsupportedPatch):
            engine.verify_source({'Name': 'Other.App', 'Version': '999.0'})

    def test_unknown_version_is_not_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); app=root/'app'; (app/'resources').mkdir(parents=True)
            (app/'ChatGPT.exe').write_bytes(b'fixture'); (app/'resources/app.asar').write_bytes(b'fixture')
            package={'Name':'OpenAI.Codex','Version':'9999.12.31.0','Status':'Ok','SignatureKind':'Store','InstallLocation':str(root)}
            with mock.patch.object(engine.subprocess,'run',return_value=mock.Mock(returncode=0,stdout='Valid')):
                self.assertEqual(engine.verify_source(package),app)

    def test_unowned_directory_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            store = engine.Store(Path(directory))
            with self.assertRaisesRegex(RuntimeError, 'ownership'):
                with store.lock(): pass
            (Path(directory)/'current.json').write_text('{"release":"../escape"}')
            with self.assertRaisesRegex(RuntimeError, 'Invalid release'):
                store.current()

    def test_running_copy_blocks_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = engine.Store(Path(directory)/'data')
            with mock.patch.object(engine, 'powershell', return_value=json.dumps({'ExecutablePath':str(store.root/'releases/x/ChatGPT.exe')})):
                with self.assertRaisesRegex(RuntimeError, 'Close the custom'): store.idle()
