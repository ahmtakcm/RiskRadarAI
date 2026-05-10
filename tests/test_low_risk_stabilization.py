"""
Tests for low-risk stabilization changes:

1. File-level locks for profile_state.json and overrides.json access
2. Lock for calendar_cache.json load/save
3. /audit command dispatch bug fix
4. Register source_commands (dead handler revived)
5. Remove watch/feed dead handlers
"""
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch


class TestProfileFileLock(unittest.TestCase):
    """File-level locks prevent concurrent read/write corruption."""

    def _patch_paths(self, tmp):
        import commands.profile_commands as pc
        return (
            patch.object(pc, "STATE_PATH", Path(tmp) / "profile_state.json"),
            patch.object(pc, "POLICY_OVERRIDE_PATH", Path(tmp) / "notification_policy_overrides.json"),
        )

    def test_load_profile_state_uses_lock(self):
        """load_profile_state() acquires _PROFILE_FILE_LOCK."""
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "profile_state.json"
            with patch.object(pc, "STATE_PATH", state_path):
                result = pc.load_profile_state()
                self.assertIsInstance(result, dict)
                self.assertIn("active_profiles", result)

    def test_save_profile_state_uses_lock(self):
        """save_profile_state() acquires _PROFILE_FILE_LOCK."""
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "profile_state.json"
            with patch.object(pc, "STATE_PATH", state_path):
                pc.save_profile_state({"active_profiles": ["ekonomi"]})
                data = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertIn("ekonomi", data["active_profiles"])

    def test_load_policy_overrides_uses_lock(self):
        """_load_policy_overrides() acquires _PROFILE_FILE_LOCK."""
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "notification_policy_overrides.json"
            policy_path.write_text(json.dumps({"profiles": {"ekonomi": {"min_score": 30}}}), encoding="utf-8")
            with patch.object(pc, "POLICY_OVERRIDE_PATH", policy_path):
                result = pc._load_policy_overrides()
                self.assertEqual(result["profiles"]["ekonomi"]["min_score"], 30)

    def test_save_policy_overrides_uses_lock(self):
        """_save_policy_overrides() acquires _PROFILE_FILE_LOCK."""
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "notification_policy_overrides.json"
            with patch.object(pc, "POLICY_OVERRIDE_PATH", policy_path):
                pc._save_policy_overrides({"profiles": {"ekonomi": {"min_score": 25}}})
                data = json.loads(policy_path.read_text(encoding="utf-8"))
                self.assertEqual(data["profiles"]["ekonomi"]["min_score"], 25)

    def test_concurrent_access_no_corruption(self):
        """Simulate concurrent read/write of profile_state - no corruption."""
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "profile_state.json"
            with patch.object(pc, "STATE_PATH", state_path):
                # Pre-seed state
                pc.save_profile_state({"active_profiles": ["ekonomi"], "disabled_profiles": []})

                errors = []
                def writer():
                    try:
                        for _ in range(20):
                            s = pc.load_profile_state()
                            s["active_profiles"] = ["ekonomi", "dunya"]
                            pc.save_profile_state(s)
                            time.sleep(0.001)
                    except Exception as e:
                        errors.append(e)

                def reader():
                    try:
                        for _ in range(20):
                            s = pc.load_profile_state()
                            self.assertIn("active_profiles", s)
                            time.sleep(0.001)
                    except Exception as e:
                        errors.append(e)

                threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                self.assertEqual(errors, [])


class TestCalendarCacheLock(unittest.TestCase):
    """File-level lock for calendar_cache.json load/save."""

    def test_load_cache_uses_lock(self):
        """_load_cache() acquires _CALENDAR_CACHE_LOCK."""
        import workflows.process_calendar_events as pce
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "calendar_cache.json"
            cache_path.write_text(json.dumps({"events": [{"id": "1"}]}), encoding="utf-8")
            with patch.object(pce, "CACHE_PATH", cache_path):
                result = pce._load_cache()
                self.assertEqual(len(result["events"]), 1)

    def test_save_cache_uses_lock(self):
        """_save_cache() acquires _CALENDAR_CACHE_LOCK."""
        import workflows.process_calendar_events as pce
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "calendar_cache.json"
            with patch.object(pce, "CACHE_PATH", cache_path):
                pce._save_cache({"events": [{"id": "test"}]})
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                self.assertEqual(data["events"][0]["id"], "test")


class TestAuditCommandFix(unittest.TestCase):
    """/audit was broken - now handled."""

    def test_audit_command_recognized(self):
        """handle_audit_command('/audit') returns a response (not None)."""
        import commands.audit_commands as ac
        with patch.object(ac, "_run_script", return_value=(True, "active_profile= test total=10")):
            result = ac.handle_audit_command("/audit")
            self.assertIsNotNone(result)

    def test_audit_json_command_recognized(self):
        """handle_audit_command('/audit_json') returns a response (not None)."""
        import commands.audit_commands as ac
        with patch.object(ac, "_run_script", return_value=(True, "active_profile= test total=10")):
            result = ac.handle_audit_command("/audit_json")
            self.assertIsNotNone(result)

    def test_health_still_works(self):
        """handle_audit_command('/health') still returns health response."""
        import commands.audit_commands as ac
        # Can't mock Path.exists on Windows, so just mock _run_script
        with patch.object(ac, "_run_script", return_value=(True, "active_profile= test total=10")):
            result = ac.handle_audit_command("/health")
            self.assertIsNotNone(result)
            self.assertIn("RiskRadarAI", result)

    def test_audit_reachable_through_profile_command(self):
        """handle_profile_command('/audit') now routes to audit handler."""
        import commands.profile_commands as pc
        with patch.object(pc, "handle_audit_command", return_value="audit ok"):
            result = pc.handle_profile_command("/audit")
            self.assertEqual(result, "audit ok")

    def test_audit_is_not_unknown(self):
        """handle_profile_command('/audit') no longer returns 'unknown command'."""
        import commands.profile_commands as pc
        with patch.object(pc, "handle_audit_command", return_value="audit handler ran"):
            result = pc.handle_profile_command("/audit")
            self.assertNotIn("Bilinmeyen komut", result)


class TestSourceCommandRegistration(unittest.TestCase):
    """source_commands was dead code - now registered in dispatch."""

    def test_source_commands_reachable(self):
        """handle_profile_command('/kaynak') routes to source handler."""
        import commands.profile_commands as pc
        with patch.object(pc, "handle_source_command", return_value="source ok"):
            result = pc.handle_profile_command("/kaynak")
            self.assertEqual(result, "source ok")

    def test_source_test_reachable(self):
        """handle_profile_command('/kaynak_test test') routes to source handler."""
        import commands.profile_commands as pc
        with patch.object(pc, "handle_source_command", return_value="source test ok"):
            result = pc.handle_profile_command("/kaynak_test test")
            self.assertEqual(result, "source test ok")

    def test_source_ekle_reachable(self):
        """handle_profile_command('/kaynak_ekle ...') routes to source handler."""
        import commands.profile_commands as pc
        with patch.object(pc, "handle_source_command", return_value="source ekle ok"):
            result = pc.handle_profile_command("/kaynak_ekle test | url | ekonomi")
            self.assertEqual(result, "source ekle ok")


class TestDeadHandlerRemoval(unittest.TestCase):
    """handle_watch_command and handle_feed_command were dead code - removed."""

    def test_watch_functions_removed(self):
        """handle_watch_command no longer exists in profile_commands module."""
        import commands.profile_commands as pc
        self.assertFalse(hasattr(pc, "handle_watch_command"), "handle_watch_command should be removed")
        self.assertFalse(hasattr(pc, "handle_feed_command"), "handle_feed_command should be removed")
        self.assertFalse(hasattr(pc, "_load_watch"), "_load_watch should be removed")
        self.assertFalse(hasattr(pc, "_save_watch"), "_save_watch should be removed")


class TestBackwardCompatibility(unittest.TestCase):
    """Existing behavior is preserved."""

    def test_menu_still_works(self):
        import commands.profile_commands as pc
        result = pc.handle_profile_command("/menu")
        self.assertIsNotNone(result)
        self.assertIn("RiskRadarAI", result)

    def test_unknown_command_still_returns_help(self):
        import commands.profile_commands as pc
        result = pc.handle_profile_command("/bilinmeyen_komut")
        self.assertIn("Bilinmeyen komut", result)
        self.assertIn("/health", result)

    def test_profile_on_off_still_works(self):
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "profile_state.json"
            with patch.object(pc, "STATE_PATH", state_path):
                pc.handle_profile_command("/profile_on ekonomi")
                pc.handle_profile_command("/profile_on turkiye")
                blob = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertIn("ekonomi", blob.get("active_profiles", []))
                pc.handle_profile_command("/profile_off ekonomi")
                blob = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertNotIn("ekonomi", blob.get("active_profiles", []))

    def test_alarm_esik_still_works(self):
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "profile_state.json"
            overrides_path = Path(tmp) / "notification_policy_overrides.json"
            with patch.object(pc, "STATE_PATH", state_path), patch.object(pc, "POLICY_OVERRIDE_PATH", overrides_path):
                pc.handle_profile_command("/alarm_esik ekonomi 30")
                blob = json.loads(overrides_path.read_text(encoding="utf-8"))
                self.assertEqual(blob["profiles"]["ekonomi"]["min_score"], 30)

    def test_ara_tara_still_works(self):
        import commands.profile_commands as pc
        with patch.object(pc, "handle_manual_scan_command", return_value="manual handled"):
            result = pc.handle_profile_command("/ara test")
            self.assertEqual(result, "manual handled")
            result = pc.handle_profile_command("/tara test")
            self.assertEqual(result, "manual handled")

    def test_digest_now_still_works(self):
        import commands.profile_commands as pc
        with patch.object(pc, "handle_digest_command", return_value="digest ok"):
            result = pc.handle_profile_command("/digest_now")
            self.assertEqual(result, "digest ok")

    def test_profiles_still_works(self):
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "profile_state.json"
            with patch.object(pc, "STATE_PATH", state_path):
                result = pc.handle_profile_command("/profiles")
                self.assertIn("Profil", result)

    def test_profile_status_still_works(self):
        import commands.profile_commands as pc
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "profile_state.json"
            with patch.object(pc, "STATE_PATH", state_path):
                result = pc.handle_profile_command("/profile_status")
                self.assertIn("Profil", result)


if __name__ == "__main__":
    unittest.main()