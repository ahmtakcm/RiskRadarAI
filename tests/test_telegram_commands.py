import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json


class RegistryTests(unittest.TestCase):
    """Tests for commands/registry.py — the single source of truth."""

    def _import_registry(self):
        import commands.registry as reg
        return reg

    def test_registry_no_duplicate_commands(self):
        reg = self._import_registry()
        names = [c.command for c in reg.REGISTRY]
        self.assertEqual(len(names), len(set(names)))

    def test_registry_no_duplicate_aliases(self):
        reg = self._import_registry()
        seen: set[str] = set()
        for cmd in reg.REGISTRY:
            for alias in cmd.aliases:
                self.assertNotIn(
                    alias, seen,
                    f"Duplicate alias '{alias}' in command '{cmd.command}'"
                )
                seen.add(alias)

    def test_registry_no_duplicate_legacy_redirects(self):
        reg = self._import_registry()
        seen: set[str] = set()
        for cmd in reg.REGISTRY:
            for legacy in cmd.legacy_redirects:
                self.assertNotIn(
                    legacy, seen,
                    f"Duplicate legacy redirect '{legacy}' in command '{cmd.command}'"
                )
                seen.add(legacy)

    def test_alias_map_covers_all_aliases(self):
        reg = self._import_registry()
        for cmd in reg.REGISTRY:
            for alias in cmd.aliases:
                self.assertIn(alias, reg.ALIAS_MAP,
                              f"Alias '{alias}' not in ALIAS_MAP")
                self.assertEqual(reg.ALIAS_MAP[alias], cmd.command)

    def test_legacy_redirect_map_covers_all_legacy_entries(self):
        reg = self._import_registry()
        for cmd in reg.REGISTRY:
            for legacy in cmd.legacy_redirects:
                self.assertIn(legacy, reg.LEGACY_REDIRECT_MAP,
                              f"Legacy '{legacy}' not in LEGACY_REDIRECT_MAP")
                self.assertEqual(reg.LEGACY_REDIRECT_MAP[legacy], cmd.command)

    def test_admin_commands_not_in_public_payload(self):
        reg = self._import_registry()
        payload = reg.public_payload()
        payload_names = {c["command"] for c in payload}
        for cmd in reg.REGISTRY:
            if cmd.admin_only:
                self.assertNotIn(cmd.command, payload_names,
                                 f"Admin command '{cmd.command}' in public payload")

    def test_admin_payload_includes_all_commands(self):
        reg = self._import_registry()
        payload = reg.admin_payload()
        payload_names = {c["command"] for c in payload}
        for cmd in reg.REGISTRY:
            self.assertIn(cmd.command, payload_names,
                          f"Command '{cmd.command}' missing from admin payload")

    def test_admin_commands_not_in_menu_commands(self):
        reg = self._import_registry()
        menu_names = {cmd for cmd, _ in reg.MENU_COMMANDS}
        for cmd in reg.REGISTRY:
            if cmd.admin_only:
                self.assertNotIn(f"/{cmd.command}", menu_names,
                                 f"Admin command '{cmd.command}' in MENU_COMMANDS")

    def test_build_menu_text_includes_all_public_commands(self):
        reg = self._import_registry()
        text = reg.build_menu_text()
        for cmd in reg.REGISTRY:
            if cmd.visible_in_menu and not cmd.admin_only:
                self.assertIn(f"/{cmd.command}", text,
                              f"Command '/{cmd.command}' missing from menu text")


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

    def test_komutlar_maps_to_menu(self):
        """/komutlar routes to menu, not unknown command."""
        import commands.profile_commands as pc
        reply = pc.handle_profile_command("/komutlar")
        self.assertIn("RiskRadarAI", reply)
        self.assertNotIn("Bilinmeyen", reply)

    def test_yardim_maps_to_menu(self):
        """/yardim routes to menu."""
        import commands.profile_commands as pc
        reply = pc.handle_profile_command("/yardim")
        self.assertIn("RiskRadarAI", reply)

    def test_keyboard_kaynaklar_routes(self):
        """Keyboard button 📡 Kaynaklar routes."""
        import commands.profile_commands as pc
        reply = pc.handle_profile_command("📡 Kaynaklar")
        self.assertIsNotNone(reply)
        self.assertIn("Kaynak", reply)

    def test_keyboard_watch_routes(self):
        """Keyboard button 👁 Watch routes."""
        import commands.profile_commands as pc
        reply = pc.handle_profile_command("👁 Watch")
        self.assertIsNotNone(reply)
        self.assertNotIn("Bilinmeyen", reply)

    def test_keyboard_menu_routes(self):
        """Keyboard button 📋 Menü routes to /menu."""
        import commands.profile_commands as pc
        reply = pc.handle_profile_command("📋 Menü")
        self.assertIn("RiskRadarAI", reply)

    def test_profil_liste_routes_to_profiles(self):
        """Legacy /profil_liste routes."""
        import commands.profile_commands as pc
        reply = pc.handle_profile_command("/profil_liste")
        self.assertNotIn("Bilinmeyen", reply)

    def test_profil_durum_routes_to_profile_status(self):
        """Legacy /profil_durum routes."""
        import commands.profile_commands as pc
        reply = pc.handle_profile_command("/profil_durum")
        self.assertNotIn("Bilinmeyen", reply)

    def test_legacy_turkish_profil_commands_redirect(self):
        """Legacy Turkish profil commands redirect with warning."""
        import commands.profile_commands as pc
        for legacy in ["/profil_resmi", "/profil_haber", "/profil_ekonomi",
                       "/profil_osint", "/profil_saglik"]:
            with self.subTest(command=legacy):
                reply = pc.handle_profile_command(legacy)
                self.assertIsNotNone(reply)
                self.assertNotIn("Bilinmeyen", reply)
                self.assertIn("kaldırıldı", reply)

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

    def test_admin_only_command_rejected_in_group_with_bot_username(self):
        """Admin-only /digest_now@BotUsername rejected in group for non-admin."""
        import commands.telegram_command_worker as worker

        class FakeTelegram:
            def get_updates(self, offset=None):
                return {'ok': True, 'result': [{'update_id': 400, 'message': {'chat': {'id': '42'}, 'from': {'id': '7'}, 'text': '/digest_now@ChatGbt33_bot'}}]}

        sent = []
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(worker, 'STATE_PATH', Path(tmp) / 'telegram_command_state.json'), \
             patch.object(worker, 'telegram_client', FakeTelegram()), \
             patch.object(worker.settings, 'chat_id', '42'), \
             patch.dict('os.environ', {'TELEGRAM_ADMIN_USER_IDS': '99'}), \
             patch.object(worker, 'handle_profile_command', lambda text: 'digest text'), \
             patch.object(worker, '_send_to_chat', lambda chat_id, text: sent.append((chat_id, text))):
            self.assertTrue(worker.poll_once())
            self.assertEqual(worker._load_offset(), 401)
            self.assertIn('sadece admin', sent[0][1])

    def test_admin_only_command_allowed_in_admin_private(self):
        """Admin-only /digest_now allowed when admin in private chat."""
        import commands.telegram_command_worker as worker

        class FakeTelegram:
            def get_updates(self, offset=None):
                return {'ok': True, 'result': [{'update_id': 500, 'message': {'chat': {'id': '99', 'type': 'private'}, 'from': {'id': '1'}, 'text': '/digest_now'}}]}

        sent = []
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(worker, 'STATE_PATH', Path(tmp) / 'telegram_command_state.json'), \
             patch.object(worker, 'telegram_client', FakeTelegram()), \
             patch.dict('os.environ', {'TELEGRAM_ADMIN_USER_IDS': '1'}), \
             patch.object(worker, 'handle_profile_command', lambda text: 'digest_ok'), \
             patch.object(worker, '_send_to_chat', lambda chat_id, text: sent.append((chat_id, text))):
            self.assertTrue(worker.poll_once())
            self.assertEqual(worker._load_offset(), 501)
            self.assertEqual(sent[0][1], 'digest_ok')


class NormalizationAndDisplayTests(unittest.TestCase):
    """Tests for @BotUsername normalization, UTF-8, and profile display."""

    def test_bot_username_suffix_normalization(self):
        """/menu@ChatGbt33_bot normalizes to /menu and returns menu text."""
        import commands.profile_commands as pc
        reply = pc.handle_profile_command("/menu@ChatGbt33_bot")
        self.assertIsNotNone(reply)
        self.assertIn("RiskRadarAI", reply)
        self.assertNotIn("Bilinmeyen", reply)

    def test_bot_username_suffix_profiles_normalizes(self):
        """/profiles@ChatGbt33_bot normalizes to /profiles."""
        import commands.profile_commands as pc
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "profile_state.json"
            with patch.object(pc, "STATE_PATH", state):
                reply = pc.handle_profile_command("/profiles@ChatGbt33_bot")
                self.assertIsNotNone(reply)
                self.assertIn("Profil", reply)
                self.assertNotIn("Bilinmeyen", reply)

    def test_digest_error_message_utf8(self):
        """Digest error message contains valid Turkish UTF-8, not mojibake."""
        import commands.profile_commands as pc
        import workflows.runner
        with patch.object(workflows.runner, 'build_digest_now_reply', side_effect=Exception("timeout")):
            reply = pc.handle_digest_command("/digest_now")
            self.assertIsNotNone(reply)
            self.assertIn("çalıştırılamadı", reply)
            self.assertNotIn("?", reply)

    def test_profiles_shows_all_active_when_master_on(self):
        """/profiles shows all profiles active when tum_profiller is the only active profile."""
        import commands.profile_commands as pc
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "profile_state.json"
            state.write_text('{"active_profiles": ["tum_profiller"], "disabled_profiles": []}', encoding="utf-8")
            with patch.object(pc, "STATE_PATH", state):
                reply = pc.handle_profile_command("/profiles")
                self.assertIsNotNone(reply)
                # tum_profiller should be active
                self.assertIn("✅ 🧭 Tüm profiller", reply)
                # Other individual profiles should also show as active
                self.assertIn("✅ 🏛 Resmî", reply)
                self.assertIn("✅ 🌍 Dünya", reply)
                self.assertIn("✅ 📈 Ekonomi", reply)


if __name__ == '__main__':
    unittest.main()
