from pathlib import Path
from unittest import TestCase
import hashlib
import selector_patch


FIXTURES = Path(__file__).parent / 'fixtures'


class SelectorTests(TestCase):
    def test_discovers_old_and_moved_new_component(self):
        for name, function, runtime in [('original-selector.js','R7c','i3'),('new-selector.js','DIn','_X')]:
            with self.subTest(name=name):
                result = selector_patch.analyze((FIXTURES/name).read_bytes())
                self.assertEqual(len(result),1)
                self.assertEqual((result[0]['function'],result[0]['runtime']),(function,runtime))

    def test_renamed_compiler_symbols_and_unicode_offsets(self):
        function = (FIXTURES/'original-selector.js').read_text().replace('function R7c(', 'function Next$Selector(').replace('i3.', 'Render$.')
        prefix = 'const unicode="שלום";const fake="codexAvailable";'.encode()
        source = prefix + function.encode() + b';const untouched=1;'
        plan = selector_patch.analyze(source)[0]
        self.assertEqual(plan['function'],'Next$Selector')
        self.assertEqual(plan['runtime'],'Render$')
        plan['uiHash']=hashlib.sha256(source).hexdigest()
        template=(FIXTURES.parent.parent/'patches/mode-tabs.js').read_text()
        result=selector_patch.rewrite(source,plan,template)
        self.assertTrue(result.startswith(prefix))
        self.assertTrue(result.endswith(b';const untouched=1;'))
        self.assertIn(b'function Next$Selector(props)',result)
        self.assertIn(b'Render$.jsx',result)
        self.assertNotIn(b'__JSX__',result)

    def test_rewrites_selector_inside_module_factory(self):
        component = (FIXTURES/'new-selector.js').read_bytes()
        prefix = b'export const modules = {moduleId(module, exports, load) {'
        suffix = b';exports.Selector = DIn;}};'
        source = prefix + component + suffix
        plan, = selector_patch.analyze(source)
        plan['uiHash'] = hashlib.sha256(source).hexdigest()
        template = (FIXTURES.parent.parent/'patches/mode-tabs.js').read_text()
        result = selector_patch.rewrite(source, plan, template)
        self.assertTrue(result.startswith(prefix))
        self.assertTrue(result.endswith(suffix))
        self.assertIn(b'_X.jsx', result)
        self.assertFalse(selector_patch.parser().parse(result).root_node.has_error)

    def test_missing_mode_callback_contract_is_not_guessed(self):
        source=(FIXTURES/'original-selector.js').read_bytes().replace(b'h(`codex`)',b'h(`agent`)')
        self.assertEqual(selector_patch.analyze(source),[])

    def test_localization_and_comments_are_not_components(self):
        source=b'// codexAvailable onModeSelect sidebarElectron.productMode.trigger\nconst x={codexAvailable:true,onModeSelect(){}};'
        self.assertEqual(selector_patch.analyze(source),[])

    def test_ambiguous_components_remain_ambiguous(self):
        source=(FIXTURES/'original-selector.js').read_bytes()
        source+=source.replace(b'function R7c(',b'function AnotherSelector(')
        self.assertEqual(len(selector_patch.analyze(source)),2)
