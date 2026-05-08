import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json


class TelegramCommandRoutingTests(unittest.TestCase):
    def test_new_commands_route_through_handle_profile_command(self):
        import commands.profile_commands as pc
        cases = {
            '/audit': 'audit ok',
            '/audit_json': 'audit json ok',
            '/health': 'health ok',
            '/source_health': 'source health ok',
            '/kaynak_saglik': 'kaynak saglik ok',
            '/digest_now': 'digest ok',
        }
        for command, expected in cases.items():
            with self.subTest(command=command), patch.object(pc, 'handle_audit_command', lambda text, expected=expected: expected):
                self.assertEqual(pc.handle_profile_command(command), expected)

    def test_manual_commands_route_through_handle_profile_command(self):
        import commands.profile_commands as pc
        for command in ['/ara hürmüz', '/tara hürmüz']:
            with self.subTest(command=command), patch.object(pc, 'handle_manual_scan_command', lambda text: f'manual {text}'):
                reply = pc.handle_profile_command(command)
                self.assertTrue(reply)
                self.assertIn(command, reply)

    def test_unknown_command_returns_help(self):
        import commands.profile_commands as pc
        reply = pc.handle_profile_command('/bilinmeyen_komut')
        self.assertTrue(reply)
        self.assertIn('Bilinmeyen komut', reply)
        self.assertIn('/audit', reply)

    def test_profiles_and_status_commands_return_non_empty(self):
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "profile_state.json"
            with patch.object(pc, "STATE_PATH", state):
                self.assertIn("Profil", pc.handle_profile_command("/profiles"))
                self.assertIn("Profil", pc.handle_profile_command("/profile_status"))

    def test_profile_on_off_updates_runtime_state(self):
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "profile_state.json"
            with patch.object(pc, "STATE_PATH", state):
                pc.handle_profile_command("/profile_on ekonomi")
                pc.handle_profile_command("/profile_on turkiye")
                blob = json.loads(state.read_text(encoding="utf-8"))
                self.assertIn("ekonomi", blob.get("active_profiles", []))
                pc.handle_profile_command("/profile_off ekonomi")
                blob = json.loads(state.read_text(encoding="utf-8"))
                self.assertNotIn("ekonomi", blob.get("active_profiles", []))

    def test_alarm_esik_writes_policy_override(self):
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "profile_state.json"
            overrides = Path(tmp) / "notification_policy_overrides.json"
            with patch.object(pc, "STATE_PATH", state), patch.object(pc, "POLICY_OVERRIDE_PATH", overrides):
                pc.handle_profile_command("/alarm_esik ekonomi 30")
                blob = json.loads(overrides.read_text(encoding="utf-8"))
                self.assertEqual(blob["profiles"]["ekonomi"]["min_score"], 30)

    def test_scoped_ara_uses_profile_id_and_preserves_legacy(self):
        import commands.manual_scan_commands as manual

        calls = []

        def fake_scan(state, mode="all", manual_query=None, max_feeds=None, **kwargs):
            calls.append((mode, manual_query, (kwargs.get("active_config") or {}).get("profile_name")))
            return []

        with patch.object(manual, "scan_news", fake_scan):
            reply = manual.handle_manual_scan_command("/ara ekonomi faiz")
            self.assertTrue(reply)
            self.assertEqual(calls[0][0], "official_only")
            self.assertEqual(calls[0][1], "faiz")
            self.assertEqual(calls[0][2], "ekonomi")

            calls.clear()
            manual.handle_manual_scan_command("/ara osint h?rm?z")
            self.assertEqual(calls[0][0], "osint_only")
            self.assertEqual(calls[0][1], "h?rm?z")

            calls.clear()
            manual.handle_manual_scan_command("/ara h?rm?z")
            self.assertEqual(calls[0][1], "h?rm?z")

    def test_tara_duration_parses_24s_as_24_hours(self):
        import commands.manual_scan_commands as manual

        seen = []

        def fake_scan(state, mode="all", manual_query=None, max_feeds=None, **kwargs):
            s = kwargs.get("settings_override")
            if s is not None:
                seen.append(getattr(s, "news_max_age_minutes", None))
            return []

        with patch.object(manual, "scan_news", fake_scan):
            manual.handle_manual_scan_command("/tara tum_profiller 24s")
        self.assertTrue(seen)
        self.assertIn(24 * 60, seen)


class TelegramCommandWorkerTests(unittest.TestCase):
    def test_worker_advances_offset_after_processing(self):
        import commands.telegram_command_worker as worker

        class FakeTelegram:
            def get_updates(self, offset=None):
                return {'ok': True, 'result': [{'update_id': 123, 'message': {'chat': {'id': '42'}, 'text': '/audit'}}]}

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(worker, 'STATE_PATH', Path(tmp) / 'telegram_command_state.json'), \
             patch.object(worker, 'telegram_client', FakeTelegram()), \
             patch.object(worker.settings, 'chat_id', '42'), \
             patch.object(worker, 'handle_profile_command', lambda text: 'ok'), \
             patch.object(worker, '_send_to_chat', lambda chat_id, text: 200):
            self.assertTrue(worker.poll_once())
            self.assertEqual(worker._load_offset(), 124)

    def test_worker_skips_wrong_chat_and_advances_offset(self):
        import commands.telegram_command_worker as worker

        class FakeTelegram:
            def get_updates(self, offset=None):
                return {'ok': True, 'result': [{'update_id': 200, 'message': {'chat': {'id': '99'}, 'text': '/audit'}}]}

        sent = []
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(worker, 'STATE_PATH', Path(tmp) / 'telegram_command_state.json'), \
             patch.object(worker, 'telegram_client', FakeTelegram()), \
             patch.object(worker.settings, 'chat_id', '42'), \
             patch.object(worker, '_send_to_chat', lambda chat_id, text: sent.append((chat_id, text))):
            self.assertFalse(worker.poll_once())
            self.assertEqual(worker._load_offset(), 201)
            self.assertEqual(sent, [])

    def test_digest_now_is_admin_only_in_group(self):
        import commands.telegram_command_worker as worker

        class FakeTelegram:
            def get_updates(self, offset=None):
                return {'ok': True, 'result': [{'update_id': 300, 'message': {'chat': {'id': '42'}, 'from': {'id': '7'}, 'text': '/digest_now'}}]}

        sent = []
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(worker, 'STATE_PATH', Path(tmp) / 'telegram_command_state.json'), \
             patch.object(worker, 'telegram_client', FakeTelegram()), \
             patch.object(worker.settings, 'chat_id', '42'), \
             patch.dict('os.environ', {'TELEGRAM_ADMIN_USER_IDS': '99'}), \
             patch.object(worker, 'handle_profile_command', lambda text: 'digest text'), \
             patch.object(worker, '_send_to_chat', lambda chat_id, text: sent.append((chat_id, text))):
            self.assertTrue(worker.poll_once())
            self.assertEqual(worker._load_offset(), 301)
            self.assertIn('sadece admin', sent[0][1])


if __name__ == '__main__':
    unittest.main()
