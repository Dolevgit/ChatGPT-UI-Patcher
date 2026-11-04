"""Offline copy-only patch engine. Never writes to an installed package."""
from pathlib import Path
import contextlib
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import uuid
import re
import stat
import app_icon
import selector_patch
import sidebar_patch
import floating_patch
import floating_chunks
from collections import Counter
from selector_patch import UnsupportedPatch

ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'patches'
PACKAGE_NAME = 'OpenAI.Codex'
CHUNK = 4 * 1024 * 1024
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def windows_env():
    env = {k: v for k, v in os.environ.items() if k.lower() != 'psmodulepath'}
    # PowerShell 7 can pass a module path that breaks Windows PowerShell 5.1.
    return env


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def powershell(command):
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                             "[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); $ErrorActionPreference='Stop'; " + command],
                            capture_output=True, encoding='utf-8', env=windows_env(), creationflags=FLAGS, timeout=90)
    if result.returncode:
        raise RuntimeError('Windows inspection failed: ' + result.stderr.strip()[:500])
    return result.stdout.strip()


def detect():
    raw = powershell("Get-AppxPackage | Where-Object { $_.Name -in @('OpenAI.Codex','OpenAI.ChatGPT-Desktop') } | Select-Object Name,@{n='Version';e={$_.Version.ToString()}},@{n='Architecture';e={$_.Architecture.ToString()}},InstallLocation,@{n='Status';e={$_.Status.ToString()}},@{n='SignatureKind';e={$_.SignatureKind.ToString()}} | ConvertTo-Json -Compress")
    items = json.loads(raw) if raw else []
    return [items] if isinstance(items, dict) else items


def verify_source(package):
    if package.get('Name') != PACKAGE_NAME:
        raise UnsupportedPatch('Combined ChatGPT/Codex installation not found')
    if package.get('Status') != 'Ok' or package.get('SignatureKind') != 'Store':
        raise RuntimeError('Expected a healthy Store package; no changes made.')
    root = Path(package['InstallLocation']) / 'app'
    no_links(root)
    if not (root / 'ChatGPT.exe').is_file() or not (root / 'resources/app.asar').is_file():
        raise UnsupportedPatch('The installed app has a different file layout')
    # Use an environment value rather than placing a path inside shell source.
    env = windows_env()
    env['PATCHER_VERIFY_EXE'] = str(root / 'ChatGPT.exe')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                             "(Get-AuthenticodeSignature -LiteralPath $env:PATCHER_VERIFY_EXE).Status.ToString()"],
                            capture_output=True, text=True, env=env, creationflags=FLAGS, timeout=30)
    if result.returncode or result.stdout.strip() != 'Valid':
        raise RuntimeError('The source launcher signature is not valid.')
    return root


def plan_patch(root):
    try:
        return _plan_patch(root)
    except UnsupportedPatch:
        raise
    except (RuntimeError, ValueError, KeyError, struct.error) as error:
        raise UnsupportedPatch('Could not prepare the product-selector change') from error


def _plan_patch(root):
    matches = []
    with (root / 'resources/app.asar').open('rb') as f:
        tree, start, header_hash = header(f)
        if (root / 'ChatGPT.exe').read_bytes().count(header_hash.encode()) != 1:
            raise UnsupportedPatch('The archive integrity reference was not found')
        for name, entry in entries(tree):
            if not name.startswith('webview/') or not name.endswith('.js') or 'offset' not in entry or entry.get('unpacked'):
                continue
            f.seek(start + int(entry['offset']))
            data = f.read(entry['size'])
            if not all(token in data for token in (b'codexAvailable', b'onModeSelect', b'sidebarElectron.productMode.trigger')):
                continue
            if sha(data) != entry.get('integrity', {}).get('hash'):
                raise UnsupportedPatch('The product selector bundle failed its integrity check')
            for candidate in selector_patch.analyze(data):
                matches.append(dict(candidate, ui=name, uiHash=sha(data), headerHash=header_hash))
    if len(matches) != 1:
        raise UnsupportedPatch('Could not identify one native ChatGPT/Codex selector')
    return matches[0]


def plan_changes(root, options):
    bundles = {}
    try: tabs = plan_patch(root) if options['tabs'] else None
    except UnsupportedPatch as error:
        error.feature='tabs';raise
    contracts = Counter()
    floating_roots = {key: [] for key in ('ChatGptConversationPage', 'WorkSideChatContent', 'startNewConversation')}
    floating_roots['conversationActions'] = []
    floating_bundle = floating_chunks.Chunks() if options.get('floating_chat') else None
    with (root / 'resources/app.asar').open('rb') as f:
        tree, start, header_hash = header(f)
        if (root / 'ChatGPT.exe').read_bytes().count(header_hash.encode()) != 1:
            raise UnsupportedPatch('The archive integrity reference was not found')
        if tabs and tabs['headerHash'] != header_hash: raise UnsupportedPatch('The app changed during preparation')
        for name,entry in entries(tree):
            if not name.startswith('webview/') or not name.endswith('.js') or 'offset' not in entry or entry.get('unpacked'): continue
            f.seek(start+int(entry['offset']));data=f.read(entry['size'])
            if options.get('floating_chat'):
                floating_bundle.scan(name, data)
                for key in floating_roots:
                    if re.search(rb'\bas\s+' + key.encode() + rb'\b', data): floating_roots[key].append(name)
                if all(token in data for token in (b'protectedProjectId',b'draftKey',b'requireNonEmpty',b'previousTitle')):
                    floating_roots['conversationActions'].append(name)
            edits=[]
            if tabs and name==tabs['ui']:
                changed=selector_patch.rewrite(data,dict(tabs,fixNavigation=options['bug_fixes']),(ASSETS/'mode-tabs.js').read_text(encoding='utf-8'))
                suffix=len(data)-tabs['end']
                replacement=changed[tabs['start']:len(changed)-suffix if suffix else len(changed)].decode()
                edits.append({'start':tabs['start'],'end':tabs['end'],'replacement':replacement,'feature':'tabs'})
            candidate=(options['hide_gpt_projects'] or options['separate_recents']) and b'linkedProjectsOnly' in data and b'flatConversationHistory' in data
            candidate=candidate or ((options['hide_gpt_projects'] or options['bug_fixes']) and b'codexLocalAccessStatus' in data)
            if candidate:
                optional,found=sidebar_patch.discover(data,options);edits.extend(optional);contracts.update(found)
            if edits:
                if sha(data)!=entry.get('integrity',{}).get('hash'):raise UnsupportedPatch('A UI bundle failed its integrity check')
                bundles[name]={'ui':name,'uiHash':sha(data),'edits':edits}
        if options.get('floating_chat'):
            table = dict(entries(tree))
            def read_module(name):
                entry = table.get(name)
                if entry is None or entry.get('unpacked') or 'offset' not in entry:
                    raise UnsupportedPatch('Missing floating-chat dependency', 'floating_chat')
                f.seek(start+int(entry['offset']));data=f.read(entry['size'])
                if sha(data) != entry.get('integrity',{}).get('hash'):
                    raise UnsupportedPatch('Floating-chat dependency failed its integrity check', 'floating_chat')
                return data
            try:
                bundled = bool(floating_bundle.side_loads and not floating_roots['WorkSideChatContent'])
                planner = floating_chunks.plan if bundled else floating_patch.plan
                floating_edits = planner(read_module, floating_bundle if bundled else floating_roots,
                    (ASSETS/'floating-state.js').read_text(encoding='utf-8')+'\n'+(ASSETS/'floating-chat.js').read_text(encoding='utf-8'),
                    (ASSETS/'floating-host.js').read_text(encoding='utf-8'))
            except UnsupportedPatch:
                raise
            except (KeyError, ValueError, AttributeError, IndexError) as error:
                raise UnsupportedPatch('Could not resolve native floating-chat contracts', 'floating_chat') from error
            for name, edits in floating_edits.items():
                data = read_module(name)
                bundle = bundles.setdefault(name, {'ui':name,'uiHash':sha(data),'edits':[]})
                bundle['edits'].extend(edits)
            contracts['floating_chat'] = 1
    expected=[]
    if options['hide_gpt_projects']:expected.extend([('hide_gpt_projects',key) for key in ['project_mode','project_layout','project_navigation','recent_expansion']])
    if options['separate_recents']:expected.extend([('separate_recents','source_filter'),('separate_recents','source_filter_ui')])
    if options['bug_fixes']:expected.append(('bug_fixes','product_navigation'))
    for feature,key in expected:
        if contracts[key]!=1:raise UnsupportedPatch('One of the selected sidebar changes could not be identified uniquely',feature)
    return {'headerHash':header_hash,'bundles':list(bundles.values()),'contracts':dict(contracts)}


def no_links(path):
    path = Path(path).absolute()
    for p in [path, *path.parents]:
        if p.exists() and (p.is_symlink() or getattr(p, 'is_junction', lambda: False)()):
            raise RuntimeError('Linked paths are not supported: ' + str(p))
    return path.resolve()


def inventory(root):
    root = no_links(root)
    result = {}
    pending = [root]
    while pending:
        for p in pending.pop().iterdir():
            info = p.lstat()
            if getattr(info, 'st_file_attributes', 0) & 0x400:
                raise RuntimeError('Linked paths are not supported: ' + str(p))
            if stat.S_ISDIR(info.st_mode):
                pending.append(p)
            elif stat.S_ISREG(info.st_mode):
                result[p.relative_to(root).as_posix()] = digest(p)
    return result


def entries(node, prefix=''):
    for name, e in node.get('files', {}).items():
        if name in ('.', '..') or '/' in name or '\\' in name:
            raise RuntimeError('Invalid ASAR name')
        if 'files' in e:
            yield from entries(e, prefix + name + '/')
        else:
            yield prefix + name, e


def header(stream):
    prefix = stream.read(16)
    if len(prefix) != 16:
        raise UnsupportedPatch('Truncated ASAR prefix')
    a, b, c, d = struct.unpack('<4I', prefix)
    if a != 4 or c + 4 != b or d > 64 * 1024 * 1024 or d + 8 > b:
        raise UnsupportedPatch('Invalid ASAR header')
    raw = stream.read(d)
    if len(raw) != d:
        raise UnsupportedPatch('Truncated ASAR header')
    return json.loads(raw), 8 + b, sha(raw)


def patch_archive(source, dest, launcher, plan):
    with source.open('rb') as f:
        tree, start, old_hash = header(f)
        table = dict(entries(tree))
        if old_hash != plan['headerHash']:
            raise UnsupportedPatch('The app archive changed during preparation')
        payloads={}
        if 'bundles' in plan:
            for bundle in plan['bundles']:
                item=table[bundle['ui']];f.seek(start+int(item['offset']));data=f.read(item['size'])
                if sha(data)!=bundle['uiHash']:raise UnsupportedPatch('A UI bundle changed during preparation')
                payloads[bundle['ui']]=sidebar_patch.apply(data,bundle['edits'])
        else:
            item=table[plan['ui']];f.seek(start+int(item['offset']));data=f.read(item['size'])
            payloads[plan['ui']]=selector_patch.rewrite(data,plan,(ASSETS/'mode-tabs.js').read_text(encoding='utf-8'))
        packed = sorted(((n, e) for n, e in table.items() if 'offset' in e and not e.get('unpacked')), key=lambda x: int(x[1]['offset']))
        old = {n: (int(e['offset']), e['size']) for n, e in packed}
        offset = 0
        for name, entry in packed:
            if name in payloads:
                patched=payloads[name]
                block = entry.get('integrity', {}).get('blockSize', CHUNK)
                entry['size'] = len(patched)
                entry['integrity'] = {'algorithm': 'SHA256', 'hash': sha(patched), 'blockSize': block,
                                      'blocks': [sha(patched[i:i+block]) for i in range(0, len(patched), block)]}
            entry['offset'] = str(offset)
            offset += entry['size']
        raw = json.dumps(tree, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        pad = (-len(raw)) % 4
        pickle = struct.pack('<II', 4 + len(raw) + pad, len(raw)) + raw + b'\0' * pad
        with dest.open('xb') as out:
            out.write(struct.pack('<II', 4, len(pickle)) + pickle)
            for name, entry in packed:
                if name in payloads:
                    out.write(payloads[name])
                else:
                    pos, size = old[name]
                    f.seek(start + pos)
                    while size:
                        chunk = f.read(min(CHUNK, size))
                        if not chunk:
                            raise UnsupportedPatch('Truncated archive payload')
                        out.write(chunk)
                        size -= len(chunk)
    binary = launcher.read_bytes()
    if binary.count(old_hash.encode()) != 1:
        raise UnsupportedPatch('Expected exactly one embedded ASAR integrity hash')
    launcher.write_bytes(binary.replace(old_hash.encode(), sha(raw).encode()))


def verify_archive(path):
    with path.open('rb') as f:
        tree, start, value = header(f)
        for name, entry in entries(tree):
            if entry.get('unpacked') or 'offset' not in entry:
                continue
            f.seek(start + int(entry['offset']))
            integrity = entry.get('integrity')
            if not integrity or integrity.get('algorithm') != 'SHA256':
                raise UnsupportedPatch('Missing integrity: ' + name)
            whole = hashlib.sha256()
            remaining = entry['size']
            blocks = []
            while remaining:
                data = f.read(min(remaining, integrity['blockSize']))
                if not data:
                    raise UnsupportedPatch('Truncated entry: ' + name)
                whole.update(data)
                blocks.append(sha(data))
                remaining -= len(data)
            if whole.hexdigest() != integrity['hash'] or blocks != integrity['blocks']:
                # Electron encodes one empty block for empty files in some builds.
                if not (entry['size'] == 0 and whole.hexdigest() == integrity['hash'] and integrity['blocks'] in ([], [sha(b'')])):
                    raise UnsupportedPatch('Archive integrity failed: ' + name)
    return value


def atomic_json(path, data):
    temporary = path.with_suffix('.pending')
    with temporary.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


# Imported last so the storage layer can use the archive helpers above.
from storage import Store
