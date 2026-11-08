from pathlib import Path
from unittest import TestCase,mock
import itertools
import json
import os
import subprocess
import tempfile
import engine
import sidebar_patch
from selector_patch import UnsupportedPatch


class SidebarTests(TestCase):
    def test_project_grouping_follows_the_imported_selector(self):
        data = b'''
        export const __webpack_modules__ = {
          grouping(module, out, load) {
            const group = atom(ctx, (mode, {get}) => { return get(setting, mode); });
            load.d(out, {}, {selected: group});
          },
          sidebar(module, out, load) {
            const namespace = load("grouping");
            const config = atom(ctx, (mode, {get}) => {
              const current = get(namespace.selected, mode);
              return {source: "all", mode: current, conversationFilter: "all",
                      flatConversationHistory: false, workLocalSidebarContentVisible: true,
                      linkedProjectsOnly: false};
            });
          }
        };
        '''
        options = {'hide_gpt_projects': True, 'separate_recents': False, 'bug_fixes': False}
        edits, counts = sidebar_patch.discover(data, options)
        result = sidebar_patch.apply(data, edits)
        self.assertEqual(counts, {'project_mode': 1})
        self.assertIn(b'if(mode==="chatgpt")return "list"; return get(setting, mode)', result)
        with self.assertRaisesRegex(UnsupportedPatch, 'one imported sidebar mode selector'):
            sidebar_patch.discover(data.replace(b'{selected: group}', b'{other: group}'), options)

    def test_all_option_combinations_have_independent_contracts(self):
        fixtures=Path(__file__).parent/'fixtures'
        for hide,separate,bugs in itertools.product([False,True],repeat=3):
            with self.subTest(hide=hide,separate=separate,bugs=bugs):
                options={'hide_gpt_projects':hide,'separate_recents':separate,'bug_fixes':bugs}
                found={}
                for name in ['sidebar-initial.js','sidebar-primary.js']:
                    data=(fixtures/name).read_bytes();edits,counts=sidebar_patch.discover(data,options)
                    for key,value in counts.items():found[key]=found.get(key,0)+value
                    result=sidebar_patch.apply(data,edits)
                    if not any(options.values()):self.assertEqual(result,data)
                for contract in ['project_mode','project_layout','project_navigation','recent_expansion']:self.assertEqual(found.get(contract,0),int(hide))
                self.assertEqual(found.get('source_filter',0),int(separate))
                self.assertEqual(found.get('source_filter_ui',0),int(separate))
                self.assertEqual(found.get('product_navigation',0),int(bugs))

    def test_native_sidebar_and_navigation_behavior(self):
        fixtures=Path(__file__).parent/'fixtures'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for hide,separate in itertools.product([False,True],repeat=2):
                options={'hide_gpt_projects':hide,'separate_recents':separate,'bug_fixes':True}
                for kind in ['initial','primary']:
                    data=(fixtures/('sidebar-'+kind+'.js')).read_bytes();edits,counts=sidebar_patch.discover(data,options)
                    (root/f'{kind}-{int(hide)}-{int(separate)}.js').write_bytes(sidebar_patch.apply(data,edits))
            result=subprocess.run(['node',str(Path(__file__).parent/'sidebar.cjs'),str(root)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_codex_history_path_uses_existing_home_only_for_bug_fixes(self):
        with tempfile.TemporaryDirectory() as directory:
            store=engine.Store(Path(directory)/'data')
            with mock.patch.dict(os.environ,{'USERPROFILE':str(Path.home())},clear=True):
                self.assertEqual(store.codex_data_path({'features':{'bug_fixes':True}}),Path.home()/'.codex')
                self.assertEqual(store.codex_data_path({'features':{'bug_fixes':False}}),store.root/'codex-home')
            other=Path(directory)/'official-home'
            with mock.patch.dict(os.environ,{'CODEX_HOME':str(other)}):
                self.assertEqual(store.codex_data_path({'features':{'bug_fixes':True}}),other)
            with mock.patch.dict(os.environ,{'CODEX_HOME':str(store.root/'codex-home')}):
                self.assertEqual(store.codex_data_path({'features':{'bug_fixes':True}}),Path.home()/'.codex')
