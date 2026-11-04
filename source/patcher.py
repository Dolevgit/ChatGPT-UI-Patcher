"""Portable Windows GUI. Apply affects a separate local copy only."""
from pathlib import Path
import json
import os
import queue
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import engine
from features import OPTIONS


def make_shortcut(base, start_menu=False):
    if not getattr(sys, 'frozen', False):
        if start_menu: raise RuntimeError('Use the built EXE to add ChatGPT to the Start menu.')
        return
    env = engine.windows_env()
    env.update(PATCHER_SHORTCUT=str(base / 'ChatGPT.lnk'), PATCHER_LAUNCHER=sys.executable,
               PATCHER_ICON=str(base / 'ChatGPT-UI-data' / 'ChatGPT.ico'),
               PATCHER_START_MENU='1' if start_menu else '0')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        "$ErrorActionPreference='Stop'; $path=$env:PATCHER_SHORTCUT; "
        "if ($env:PATCHER_START_MENU -eq '1') { "
        "$programs=[Environment]::GetFolderPath('Programs'); "
        "if (-not $programs) { throw 'Start menu folder was not found' }; "
        "[IO.Directory]::CreateDirectory($programs) | Out-Null; "
        "$path=Join-Path $programs 'ChatGPT C.lnk' }; "
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($path); "
        "$s.TargetPath=$env:PATCHER_LAUNCHER; $s.Arguments='--launch'; $s.IconLocation=$env:PATCHER_ICON+',0'; "
        "$s.Description='ChatGPT'; $s.Save()"], env=env, capture_output=True, creationflags=engine.FLAGS)
    if result.returncode: raise RuntimeError('Could not create the ChatGPT shortcut')


def format_packages(packages):
    names = {'OpenAI.Codex': 'ChatGPT / Codex', 'OpenAI.ChatGPT-Desktop': 'ChatGPT Classic'}
    return '   |   '.join(names.get(p['Name'], p['Name']) + ': ' + p['Version'] for p in packages) or 'ChatGPT not found.'


class App:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.events = queue.Queue()
        self.package = None
        self.compatible = False
        base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
        self.base = base
        self.store = engine.Store(base / 'ChatGPT-UI-data')
        root.title('ChatGPT UI Patcher')
        icon = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'assets' / 'chatgpt.ico'
        if icon.exists(): root.iconbitmap(str(icon))
        root.geometry('760x470')
        root.minsize(760, 470)
        root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style()
        if 'vista' in style.theme_names(): style.theme_use('vista')
        style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        style.configure('TLabel', font=('Segoe UI', 10))
        panel = ttk.Frame(root, padding=24)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='ChatGPT customizations', style='Title.TLabel').pack(anchor='w')
        self.summary = tk.StringVar(value='Detecting ChatGPT...')
        self.version_label = ttk.Label(panel, textvariable=self.summary)
        self.version_label.pack(anchor='w', pady=(8, 8))
        folders = ttk.Frame(panel)
        folders.pack(fill='x', pady=(0, 12))
        self.original_folder = ttk.Button(folders, text='Open original folder',
                                         command=lambda: self.run(lambda: self.show_folder(False)))
        self.original_folder.pack(side='left')
        self.copy_folder = ttk.Button(folders, text='Open custom folder',
                                     command=lambda: self.run(lambda: self.show_folder(True)))
        self.copy_folder.pack(side='left', padx=8)
        self.start_menu = ttk.Button(folders, text='Add to Start menu',
                                     command=lambda: self.run(self.add_to_start_menu))
        self.start_menu.pack(side='left')
        frame = ttk.LabelFrame(panel, text='Available changes', padding=12)
        frame.pack(fill='x')
        try: saved=self.store.current() or {}
        except (RuntimeError,ValueError,OSError): saved={}
        preferences=saved.get('features',{})
        self.feature_vars={};self.feature_controls=[]
        for key,label in OPTIONS:
            default=saved.get('tabs',True) if key=='tabs' else key!='floating_chat'
            value=tk.BooleanVar(value=preferences.get(key,default))
            control=ttk.Checkbutton(frame,text=label,variable=value)
            control.pack(anchor='w',pady=1);control.state(['disabled'])
            self.feature_vars[key]=value;self.feature_controls.append(control)
        self.selected=self.feature_vars['tabs'];self.check=self.feature_controls[0]
        buttons = ttk.Frame(panel)
        buttons.pack(fill='x', pady=(16, 0))
        self.scan = ttk.Button(buttons, text='Refresh', command=self.detect)
        self.scan.pack(side='left')
        self.apply = ttk.Button(buttons, text='Create / update ChatGPT', command=self.build, state='disabled')
        self.apply.pack(side='left', padx=8)
        self.open = ttk.Button(buttons, text='Open ChatGPT', command=lambda: self.run(self.store.launch))
        self.open.pack(side='left', padx=8)
        self.progress = ttk.Progressbar(panel, mode='indeterminate')
        self.progress.pack(fill='x', pady=(18, 8))
        self.log = tk.Text(panel, height=4, wrap='word', font=('Segoe UI', 10), state='disabled')
        self.log.pack(fill='both', expand=True)
        self.widgets = [self.scan, self.apply, self.open, self.original_folder, self.copy_folder, self.start_menu, *self.feature_controls]
        root.after(100, self.poll)
        if '--self-test' not in sys.argv: root.after(200, self.detect)

    def report(self, message): self.events.put(('log', message))

    def add_to_start_menu(self):
        if not self.store.current() or not self.store.app_path().is_dir():
            raise RuntimeError('Create ChatGPT first.')
        make_shortcut(self.base, start_menu=True)
        self.report('Added ChatGPT C to the Start menu. Keep the patcher and its data in this folder so the shortcut keeps working.')

    def show_folder(self, custom):
        if custom:
            if not self.store.current(): raise RuntimeError('Create ChatGPT first.')
            path = self.store.app_path()
        else:
            package = next((p for p in engine.detect() if p['Name'] == engine.PACKAGE_NAME), None)
            if not package: raise RuntimeError('ChatGPT / Codex was not found.')
            path = Path(package['InstallLocation']) / 'app'
        path = engine.no_links(path)
        if not path.is_dir(): raise RuntimeError('The app folder no longer exists. Click Refresh.')
        os.startfile(str(path))
        self.report(str(path))

    def write(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def run(self, action, startup=False):
        if self.busy: return
        self.busy = True
        for widget in self.widgets: widget.state(['disabled'])
        self.progress.start()
        def task():
            try:
                result = action()
                self.events.put(('done', result))
            except engine.UnsupportedPatch as error:
                self.events.put(('scan_error' if startup else 'unsupported', error.feature))
            except Exception as error:
                self.events.put(('scan_error' if startup else 'error', str(error)))
        threading.Thread(target=task, daemon=False).start()

    def detect(self):
        self.compatible = False
        def action():
            packages = engine.detect()
            self.events.put(('packages', packages))
            candidate = next((p for p in packages if p['Name'] == engine.PACKAGE_NAME), None)
            if candidate is None:
                self.report('ChatGPT / Codex was not found.')
                return
            self.events.put(('compatible', candidate))
        self.run(action, startup=True)

    def build(self):
        if not self.compatible or not self.package: return
        selected={key:value.get() for key,value in self.feature_vars.items()}
        def create():
            packages = engine.detect()
            self.events.put(('packages', packages))
            current = next((p for p in packages if p['Name'] == engine.PACKAGE_NAME), None)
            if current is None: raise RuntimeError('ChatGPT / Codex was not found. Click Refresh.')
            result = self.store.build(current, selected['tabs'], self.report,features=selected)
            make_shortcut(self.base)
            return result
        self.run(create)

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log': self.write(value)
                elif kind == 'packages':
                    self.summary.set(format_packages(value))
                elif kind == 'compatible':
                    self.package = value
                    self.compatible = True
                    self.write('Ready.')
                elif kind in ('done', 'error', 'unsupported', 'scan_error'):
                    self.busy = False
                    self.progress.stop()
                    for widget in self.widgets: widget.state(['!disabled'])
                    if not self.compatible:
                        self.apply.state(['disabled'])
                        for control in self.feature_controls:control.state(['disabled'])
                    if kind == 'error':
                        self.write(value)
                    elif kind == 'unsupported':
                        label = dict(OPTIONS).get(value)
                        if label:
                            self.write(f'Could not apply {label}. Uncheck it and try again.')
                        else:
                            self.write('Could not prepare the custom app. Your existing copy was kept.')
                    elif kind == 'scan_error':
                        self.write('Could not detect ChatGPT. Click Refresh to try again.')
        except queue.Empty: pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('Operation in progress', 'Please wait for the current operation to finish.', parent=self.root)
        else: self.root.destroy()


def main():
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    if '--launch' in sys.argv or '--refresh-shortcut' in sys.argv:
        try:
            if '--refresh-shortcut' in sys.argv: make_shortcut(base)
            else: engine.Store(base / 'ChatGPT-UI-data').launch()
        except Exception as error:
            root = tk.Tk(); root.withdraw()
            messagebox.showerror('ChatGPT', str(error), parent=root)
            root.destroy()
        return
    if '--inspect' in sys.argv:
        packages = engine.detect()
        report = {'packages': packages, 'compatibilityMethod': 'discover-native-selector-no-version-list'}
        report['compatibility'] = []
        for package in packages:
            try:
                source = engine.verify_source(package)
                plan = engine.plan_changes(source,{key:True for key,label in OPTIONS})
                report['compatibility'].append({'name': package['Name'], 'patchPrepared': True, 'contracts':plan['contracts'],'bundles':[b['ui'] for b in plan['bundles']]})
            except Exception as error:
                report['compatibility'].append({'name': package['Name'], 'patchPrepared': False, 'reason': str(error)})
        dest = Path(sys.argv[sys.argv.index('--inspect') + 1])
        dest.write_text(json.dumps(report, indent=2), encoding='utf-8')
        return
    root = tk.Tk()
    app = App(root)
    if '--self-test' in sys.argv:
        app.summary.set(format_packages([
            {'Name': 'OpenAI.Codex', 'Version': '99.42.7.0'},
            {'Name': 'OpenAI.ChatGPT-Desktop', 'Version': '1.2026.190.0'},
        ]))
        root.update()
        report = {'title': root.title(), 'size': [root.winfo_width(), root.winfo_height()],
                  'buttons': [w.cget('text') for w in app.widgets], 'applyDisabledBeforeScan': app.apply.instate(['disabled']),
                  'versionsSingleLine': '\n' not in app.summary.get(), 'versionText': app.summary.get(),
                  'versionLabelFits': app.version_label.winfo_reqwidth() <= root.winfo_width() - 48}
        dest = Path(sys.argv[sys.argv.index('--self-test') + 1])
        dest.write_text(json.dumps(report, indent=2), encoding='utf-8')
        root.destroy()
        return
    root.mainloop()


if __name__ == '__main__': main()
