from pathlib import Path
from unittest import TestCase, mock
import json
import tempfile
import uuid
import engine
import test_engine


class UpdateTests(TestCase):
    def prepare(self, root):
        source = root / 'source'; source.mkdir()
        archive, exe, spec = test_engine.ArchiveTests().fixture(source)
        (source / 'resources').mkdir()
        archive.rename(source / 'resources/app.asar')
        (source / 'flat.ico').write_bytes(b'icon-fixture')
        store = engine.Store(root / 'data')
        with store.lock():
            profile = store.root / 'profile'; profile.mkdir()
            (profile / 'session').write_bytes(b'do-not-replace-existing-login')
            home = store.root / 'codex-home'; home.mkdir()
            (home / 'settings').write_bytes(b'keep-settings')
        return source, store, spec

    def contexts(self, source, spec):
        import contextlib
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(engine, 'verify_source', return_value=source))
        stack.enter_context(mock.patch.object(engine.Store, 'idle'))
        stack.enter_context(mock.patch('app_icon.source_icon', side_effect=lambda app: app/'flat.ico'))
        stack.enter_context(mock.patch('app_icon.replace'))
        stack.enter_context(mock.patch('app_icon.refresh'))
        return stack

    def assert_account(self, store):
        self.assertEqual((store.root/'profile/session').read_bytes(), b'do-not-replace-existing-login')
        self.assertEqual((store.root/'codex-home/settings').read_bytes(), b'keep-settings')

    def test_migrate_update_same_app_remove_backups_preserve_login(self):
        with tempfile.TemporaryDirectory() as directory:
            source, store, spec = self.prepare(Path(directory))
            legacy = uuid.uuid4().hex
            (store.root/'releases'/legacy).mkdir(parents=True)
            (store.root/'releases'/legacy/'ChatGPT.exe').write_bytes(b'old-custom-app')
            backup = store.root/'backup-26.1016.8120.0'; backup.mkdir()
            (backup/'original').write_bytes(b'unneeded-source-backup')
            (store.root/(legacy+'.json')).write_text('{}')
            engine.atomic_json(store.root/'current.json', {'release':legacy, 'version':'26.1016.8120.0', 'tabs':True})
            with self.contexts(source, spec):
                store.build({'Version':'26.1016.8120.0'})
                app_path = store.app_path()
                self.assertEqual(app_path, store.root/'releases'/legacy)
                self.assertTrue((app_path/'ChatGPT.exe').exists())
                self.assertFalse(backup.exists())
                self.assertEqual(list((store.root/'releases').iterdir()), [app_path])
                (source/'version.txt').write_text('new-version-content')
                store.build({'Version':'26.1016.8622.0'})
                self.assertEqual((app_path/'version.txt').read_text(), 'new-version-content')
                self.assertEqual(store.current()['version'], '26.1016.8622.0')
                self.assertEqual(store.current()['layout'], 'single-app')
                self.assert_account(store)
                self.assertFalse(any(p.name.startswith(('backup-', '.old-', '.build-')) for p in store.root.iterdir()))

    def test_failed_update_leaves_active_app_and_login(self):
        with tempfile.TemporaryDirectory() as directory:
            source, store, spec = self.prepare(Path(directory))
            with self.contexts(source, spec):
                store.build({'Version':'26.1016.8120.0'})
                original = engine.inventory(store.root/'app')
                state = store.current()
                with mock.patch.object(engine, 'patch_archive', side_effect=RuntimeError('injected build failure')):
                    with self.assertRaisesRegex(RuntimeError, 'injected build failure'):
                        store.build({'Version':'26.1016.8622.0'})
                self.assertEqual(engine.inventory(store.root/'app'), original)
                self.assertEqual(store.current(), state)
                self.assert_account(store)

    def test_interrupted_commit_finishes_on_next_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            source, store, spec = self.prepare(Path(directory))
            with self.contexts(source, spec):
                store.build({'Version':'26.1016.8120.0'})
                with mock.patch.object(store, '_publish', side_effect=OSError('injected power-loss boundary')):
                    with self.assertRaisesRegex(OSError, 'power-loss'):
                        store.build({'Version':'26.1016.8622.0'})
                self.assertTrue((store.root/'update.json').exists())
                with store.lock(): store._recover()
                self.assertFalse((store.root/'update.json').exists())
                self.assertEqual(store.current()['version'], '26.1016.8622.0')
                self.assert_account(store)
                self.assertFalse(any(p.name.startswith(('.old-', '.build-')) for p in store.root.iterdir()))

    def test_cleanup_cannot_remove_account_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source, store, spec = self.prepare(Path(directory))
            with self.assertRaisesRegex(RuntimeError, 'Refusing cleanup'):
                store._discard(store.root/'profile')
            self.assert_account(store)

    def test_unsupported_structure_keeps_existing_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            source,store,spec=self.prepare(Path(directory))
            with self.contexts(source,spec):
                store.build({'Version':'1.0.0.0'})
                before=engine.inventory(store.app_path());state=store.current()
                with mock.patch.object(engine,'plan_patch',side_effect=engine.UnsupportedPatch('no native selector')):
                    with self.assertRaises(engine.UnsupportedPatch):store.build({'Version':'9999.0.0.0'})
                self.assertEqual(engine.inventory(store.app_path()),before)
                self.assertEqual(store.current(),state)
                self.assert_account(store)
