from unittest import TestCase, mock
import tkinter as tk
import time
import tempfile
import gc
from pathlib import Path
import engine
import patcher


class StartupTests(TestCase):
    def setUp(self):
        self.args=mock.patch('sys.argv',['patcher','--self-test']);self.args.start()
        self.root=tk.Tk();self.root.withdraw()
        self.app=patcher.App(self.root)
        self.package={'Name':'OpenAI.Codex','Version':'9999.12.31.0'}

    def tearDown(self):
        for timer in self.root.tk.call('after','info'): self.root.after_cancel(timer)
        self.root.destroy();self.args.stop()
        # Tk objects form callback cycles. Release them on the GUI thread before
        # a later worker's allocations can trigger their Tcl finalizers.
        self.app=None;self.root=None
        gc.collect()

    def drain(self):
        limit=time.monotonic()+5
        while self.app.busy and time.monotonic()<limit:
            self.root.update();time.sleep(.01)
        self.assertFalse(self.app.busy)

    def test_unseen_version_is_ready_at_startup_without_validation_or_popup(self):
        self.assertFalse(self.app.feature_vars['floating_chat'].get())
        with mock.patch.object(engine,'detect',return_value=[self.package]), mock.patch.object(engine,'verify_source') as verify, mock.patch.object(patcher.messagebox,'showerror') as popup:
            self.app.detect();self.drain()
            verify.assert_not_called();popup.assert_not_called()
        self.assertTrue(self.app.apply.instate(['!disabled']))
        self.assertTrue(self.app.check.instate(['!disabled']))
        self.assertIn('9999.12.31.0',self.app.summary.get())
        self.assertNotIn('not supported',self.app.log.get('1.0','end'))

    def test_detection_error_is_non_modal(self):
        with mock.patch.object(engine,'detect',side_effect=RuntimeError('inspection unavailable')), mock.patch.object(patcher.messagebox,'showerror') as popup:
            self.app.detect();self.drain();popup.assert_not_called()
        self.assertIn('Click Refresh',self.app.log.get('1.0','end'))

    def test_folder_buttons_use_detected_source_and_existing_legacy_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'installed'/'app';original.mkdir(parents=True)
            copy=Path(directory)/'data'/'releases'/('a'*32);copy.mkdir(parents=True)
            package=dict(self.package,InstallLocation=str(original.parent))
            with mock.patch.object(engine,'detect',return_value=[package]), mock.patch.object(self.app.store,'current',return_value={'layout':'single-app'}), mock.patch.object(self.app.store,'app_path',return_value=copy), mock.patch.object(patcher.os,'startfile') as open_folder:
                self.app.show_folder(False);self.app.show_folder(True)
                self.assertEqual(open_folder.call_args_list,
                                 [mock.call(str(original.resolve())), mock.call(str(copy.resolve()))])

    def test_missing_copy_does_not_create_or_open_a_folder(self):
        with mock.patch.object(self.app.store,'current',return_value=None), mock.patch.object(patcher.os,'startfile') as open_folder:
            with self.assertRaisesRegex(RuntimeError,'Create ChatGPT first'):
                self.app.show_folder(True)
            open_folder.assert_not_called()

    def test_only_creation_attempt_reports_unsupported_without_popup(self):
        self.app.package=self.package;self.app.compatible=True
        with mock.patch.object(engine,'detect',return_value=[self.package]), mock.patch.object(self.app.store,'build',side_effect=engine.UnsupportedPatch('internal selector details')), mock.patch.object(patcher.messagebox,'showerror') as popup:
            self.app.build();self.drain();popup.assert_not_called()
        text=self.app.log.get('1.0','end')
        self.assertIn('Could not prepare the custom app.',text)
        self.assertNotIn('internal selector details',text)

    def test_creation_names_the_option_that_blocked_the_build(self):
        self.app.package=self.package;self.app.compatible=True
        error=engine.UnsupportedPatch('Unexpected project grouping contract','hide_gpt_projects')
        with mock.patch.object(engine,'detect',return_value=[self.package]), mock.patch.object(self.app.store,'build',side_effect=error):
            self.app.build();self.drain()
        self.assertIn('Could not apply Hide projects in ChatGPT. Uncheck it and try again.',
                      self.app.log.get('1.0','end'))
        self.assertTrue(self.app.feature_vars['hide_gpt_projects'].get())

    def test_start_menu_requires_existing_custom_app(self):
        with mock.patch.object(self.app.store,'current',return_value=None), mock.patch.object(patcher,'make_shortcut') as shortcut:
            self.app.run(self.app.add_to_start_menu);self.drain()
            shortcut.assert_not_called()
        self.assertIn('Create ChatGPT first',self.app.log.get('1.0','end'))

    def test_start_menu_adds_existing_copy_and_reports_success(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(self.app.store,'current',return_value={'layout':'single-app'}), mock.patch.object(self.app.store,'app_path',return_value=Path(directory)), mock.patch.object(patcher,'make_shortcut') as shortcut:
                self.app.start_menu.invoke();self.drain()
                shortcut.assert_called_once_with(self.app.base,start_menu=True)
        self.assertIn('Added ChatGPT C',self.app.log.get('1.0','end'))

    def test_start_menu_failure_is_reported_without_success(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(self.app.store,'current',return_value={'layout':'single-app'}), mock.patch.object(self.app.store,'app_path',return_value=Path(directory)), mock.patch.object(patcher,'make_shortcut',side_effect=RuntimeError('Shortcut creation failed')):
                self.app.start_menu.invoke();self.drain()
        text=self.app.log.get('1.0','end')
        self.assertIn('Shortcut creation failed',text)
        self.assertNotIn('Added ChatGPT C',text)
