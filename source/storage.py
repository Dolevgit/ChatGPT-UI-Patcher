"""One replaceable app directory with persistent account data beside it."""
from pathlib import Path
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import engine
import app_icon
import features as customization


class Store:
    def __init__(self, root):
        self.root = engine.no_links(root)
        if 'windowsapps' in [p.lower() for p in self.root.parts]:
            raise RuntimeError('Data must be outside WindowsApps')

    @contextlib.contextmanager
    def lock(self):
        import msvcrt
        engine.no_links(self.root)
        if self.root.exists() and not (self.root / 'owner.json').exists():
            raise RuntimeError('Data folder already exists without a patcher ownership marker')
        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = engine.no_links(self.root / 'operation.lock')
        with lock_path.open('a+b') as f:
            if f.tell() == 0:
                f.write(b'0'); f.flush()
            f.seek(0)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError('Another patcher operation is running')
            try:
                marker = engine.no_links(self.root / 'owner.json')
                if marker.exists():
                    if json.loads(marker.read_text()) != {'owner': 'chatgpt-ui-patcher-v1'}:
                        raise RuntimeError('Unrecognized data directory')
                else:
                    engine.atomic_json(marker, {'owner': 'chatgpt-ui-patcher-v1'})
                # Account folders are never walked, copied, removed or reset.
                for child in self.root.iterdir():
                    engine.no_links(child)
                yield
            finally:
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

    def idle(self):
        raw = engine.powershell("Get-CimInstance Win32_Process -Filter \"Name = 'ChatGPT.exe'\" | Select-Object ExecutablePath | ConvertTo-Json -Compress")
        items = json.loads(raw) if raw else []
        if isinstance(items, dict): items = [items]
        for p in items:
            if not p.get('ExecutablePath'):
                raise RuntimeError('Cannot inspect a running ChatGPT process. Close it before continuing.')
            if Path(p['ExecutablePath']).resolve().is_relative_to(self.root):
                raise RuntimeError('Close the custom ChatGPT before updating it')

    def current(self):
        p = engine.no_links(self.root / 'current.json')
        if not p.exists(): return None
        value = json.loads(p.read_text(encoding='utf-8'))
        if value.get('layout') == 'single-app':
            self._app_for(value.get('directory', 'app'))
            return value
        # Accept the earlier layout for migration, keeping its exact profile.
        name = value.get('release', '')
        if not re.fullmatch('[0-9a-f]{32}', name):
            raise RuntimeError('Invalid release reference')
        return value

    def _app_for(self, directory):
        if directory != 'app' and not re.fullmatch(r'releases/[0-9a-f]{32}', directory):
            raise RuntimeError('Invalid app directory')
        return engine.no_links(self.root / directory)

    def app_path(self):
        state = self.current()
        if not state: return self.root / 'app'
        return self._app_for(state.get('directory', 'app') if state.get('layout') == 'single-app' else 'releases/' + state['release'])

    def _discard(self, path):
        path = engine.no_links(path)
        allowed = (path.name == 'releases' or re.fullmatch(r'\.(?:build|old)-[0-9a-f]{32}', path.name)
                   or re.fullmatch(r'backup-(?:pending-[0-9a-f]{32}|[0-9]+(?:\.[0-9]+){3})(?:\.json)?', path.name)
                   or re.fullmatch(r'[0-9a-f]{32}\.json', path.name))
        legacy_child = path.parent == self.root / 'releases' and re.fullmatch('[0-9a-f]{32}', path.name)
        if path == self.app_path() or (not legacy_child and (path.parent != self.root or not allowed)):
            raise RuntimeError('Refusing cleanup outside owned app artifacts: ' + str(path))
        if path.is_dir():
            # Reject every linked descendant before a recursive removal.
            for p in path.rglob('*'): engine.no_links(p)
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    def _cleanup(self):
        if not self.current() or self.current().get('layout') != 'single-app' or not self.app_path().is_dir():
            return
        active = self.app_path()
        for p in list(self.root.iterdir()):
            if p.name == 'releases' and active.parent == p:
                for child in p.iterdir():
                    if child != active: self._discard(child)
                continue
            if (p.name == 'releases' or re.fullmatch(r'\.(?:build|old)-[0-9a-f]{32}', p.name)
                or re.fullmatch(r'backup-(?:pending-[0-9a-f]{32}|[0-9]+(?:\.[0-9]+){3})(?:\.json)?', p.name)
                or re.fullmatch(r'[0-9a-f]{32}\.json', p.name)):
                self._discard(p)

    def _publish(self, stage):
        engine.atomic_json(self.root / 'app-files.json', json.loads((stage / 'files.json').read_text()))
        engine.atomic_json(self.root / 'current.json', json.loads((stage / 'state.json').read_text()))
        (self.root / 'update.json').unlink()

    def _recover(self):
        journal = self.root / 'update.json'
        if not journal.exists(): return
        value = json.loads(journal.read_text())
        if not re.fullmatch(r'\.build-[0-9a-f]{32}', value.get('stage', '')) or not re.fullmatch(r'\.old-[0-9a-f]{32}', value.get('previous', '')):
            raise RuntimeError('Invalid update journal')
        stage = engine.no_links(self.root / value['stage'])
        previous = engine.no_links(self.root / value['previous'])
        app = self._app_for(value.get('directory', 'app'))
        if app.exists() and not (stage / 'app').exists():
            if engine.inventory(app) != json.loads((stage / 'files.json').read_text()):
                raise RuntimeError('Interrupted update needs inspection; account data is intact')
            self._publish(stage)
        else:
            if not app.exists() and previous.exists(): previous.rename(app)
            journal.unlink()
            self._discard(stage)
        self._cleanup()

    def _activate(self, stage):
        directory = json.loads((stage / 'state.json').read_text()).get('directory', 'app')
        app = self._app_for(directory)
        app.parent.mkdir(exist_ok=True)
        previous = self.root / ('.old-' + uuid.uuid4().hex)
        engine.atomic_json(self.root / 'update.json', {'stage': stage.name, 'previous': previous.name, 'directory': directory})
        try:
            if app.exists(): app.rename(previous)
            (stage / 'app').rename(app)
        except BaseException:
            if not app.exists() and previous.exists(): previous.rename(app)
            (self.root / 'update.json').unlink()
            raise
        self._publish(stage)

    def build(self, package, tabs=True, progress=lambda s: None, features=None):
        selected=customization.normalize(features,tabs)
        source = engine.verify_source(package)
        if self.root == source or self.root.is_relative_to(source) or source.is_relative_to(self.root):
            raise RuntimeError('Source and destination must be separate')
        with self.lock():
            self.idle()
            self._recover()
            self._cleanup()
            progress('Preparing selected changes...')
            plan = engine.plan_changes(source,selected) if any(selected.values()) else None
            progress('Reading the installed version...')
            original = engine.inventory(source)
            size = sum((source / n).stat().st_size for n in original)
            if shutil.disk_usage(self.root).free < size + (source / 'resources/app.asar').stat().st_size + 100*1024*1024:
                raise RuntimeError('Not enough space for the updated app')
            stage = self.root / ('.build-' + uuid.uuid4().hex)
            stage.mkdir()
            progress('Creating the updated app...')
            try:
                shutil.copytree(source, stage / 'app')
                target = stage / 'app'
                if engine.inventory(target) != original:
                    raise RuntimeError('The installed files changed while copying; retry after the update finishes')
                engine.verify_source(package)
                if plan:
                    progress('Applying selected changes...')
                    archive = target / 'resources/app.asar'
                    temporary = archive.with_suffix('.building')
                    engine.patch_archive(source / 'resources/app.asar', temporary, target / 'ChatGPT.exe', plan)
                    os.replace(temporary, archive)
                progress('Updating the icon and checking files...')
                try:
                    app_icon.replace(target / 'ChatGPT.exe', app_icon.source_icon(target))
                except (RuntimeError, ValueError) as error:
                    raise engine.UnsupportedPatch('Could not update the copied app icon') from error
                header_hash = engine.verify_archive(target / 'resources/app.asar')
                if (target / 'ChatGPT.exe').read_bytes().count(header_hash.encode()) != 1:
                    raise engine.UnsupportedPatch('Launcher integrity reference mismatch')
                files = engine.inventory(target)
                allowed = {'ChatGPT.exe', 'resources/app.asar'}
                if files.keys() != original.keys() or any(files[n] != h for n, h in original.items() if n not in allowed):
                    raise engine.UnsupportedPatch('Unexpected output change')
                engine.atomic_json(stage / 'files.json', files)
                directory = self.app_path().relative_to(self.root).as_posix()
                state = {'layout': 'single-app', 'directory': directory, 'version': package['Version'], 'tabs': selected['tabs'],'features':selected}
                engine.atomic_json(stage / 'state.json', state)
                self._activate(stage)
            except BaseException:
                if not (self.root / 'update.json').exists() and stage.exists(): self._discard(stage)
                raise
            shutil.copyfile(app_icon.source_icon(self.app_path()), self.root / 'ChatGPT.ico')
            self._cleanup()
            app_icon.refresh(self.app_path() / 'ChatGPT.exe')
            progress('Done.')
            return state

    def launch(self):
        with self.lock():
            self.idle()
            self._recover()
            state = self.current()
            if not state: raise RuntimeError('Create ChatGPT first')
            if state.get('layout') == 'single-app':
                app = self.app_path()
                manifest = self.root / 'app-files.json'
            else:
                app = self.root / 'releases' / state['release']
                manifest = self.root / (state['release'] + '.json')
            if engine.inventory(app) != json.loads(manifest.read_text()):
                raise RuntimeError('Custom app files have changed; create it again')
            profile = engine.no_links(self.root / 'profile')
            codex_data = self.codex_data_path(state)
            profile.mkdir(exist_ok=True); codex_data.mkdir(exist_ok=True)
            env = os.environ.copy()
            env['CODEX_ELECTRON_USER_DATA_PATH'] = str(profile)
            env['CODEX_HOME'] = str(codex_data)
            subprocess.Popen([str(app / 'ChatGPT.exe'), '--user-data-dir=' + str(profile)],
                             cwd=app, env=env, creationflags=engine.FLAGS)

    def codex_data_path(self,state):
        if not state.get('features',{}).get('bug_fixes',False):
            return engine.no_links(self.root/'codex-home')
        configured=os.environ.get('CODEX_HOME')
        target=Path(configured).expanduser().absolute() if configured else Path.home()/'.codex'
        if target.resolve().is_relative_to(self.root):target=Path.home()/'.codex'
        if 'windowsapps' in [part.lower() for part in target.parts]:raise RuntimeError('Invalid Codex data directory')
        return engine.no_links(target)
