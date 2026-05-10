import unittest
from unittest.mock import Mock, patch
import requests


class TelegramSafetyTests(unittest.TestCase):
    def test_mask_token_text_redacts_bot_token_and_url(self):
        import clients.telegram_client as tc

        with patch.object(tc.settings, 'bot_token', '123:SECRET'):
            text = 'https://api.telegram.org/bot123:SECRET/sendMessage failed 123:SECRET'
            masked = tc.mask_token_text(text)
            self.assertNotIn('123:SECRET', masked)
            self.assertIn('bot<SECRET>/sendMessage', masked)

    def test_send_message_raises_chat_migrated(self):
        import clients.telegram_client as tc

        response = Mock()
        response.status_code = 400
        response.json.return_value = {'ok': False, 'parameters': {'migrate_to_chat_id': -100123}}
        error = requests.HTTPError('bad request')
        error.response = response

        with patch.object(tc.http_client, 'post_form', side_effect=error):
            with self.assertRaises(tc.TelegramChatMigrated) as ctx:
                tc.telegram_client.send_message('hello', chat_id='-1')
        self.assertEqual(ctx.exception.new_chat_id, '-100123')


if __name__ == '__main__':
    unittest.main()
