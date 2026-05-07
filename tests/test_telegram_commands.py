import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TelegramCommandRoutingTests(unittest.TestCase):
    def test_new_commands_route_through_handle_profile_command(self):
        import commands.profile_commands as pc
        cases = {
            '/audit': 'audit ok',
            '/audit_json': 'audit json ok',
            '/health': 'health ok',
            '/source_health': 'source health ok',
            '/kaynak_saglik': 'kaynak saglik ok',
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


if __name__ == '__main__':
    unittest.main()
