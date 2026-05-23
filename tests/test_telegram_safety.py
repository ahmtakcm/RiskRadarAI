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

    def test_clean_telegram_text_removes_html_noise_and_preserves_links(self):
        from enrichers.text_hygiene import clean_telegram_text

        raw = (
            '<p><b>Fed</b> statement published</p>'
            '<blockquote>quoted social embed should not be in summary</blockquote>'
            '<img src="x.png"><hr>'
            '<a href="https://example.com/fomc">Read release</a>'
        )

        cleaned = clean_telegram_text(raw)

        self.assertIn('Fed statement published', cleaned)
        self.assertIn('Read release (https://example.com/fomc)', cleaned)
        self.assertNotIn('<', cleaned)
        self.assertNotIn('quoted social embed', cleaned)
        self.assertNotIn('x.png', cleaned)

    def test_signal_message_sanitizes_summary_html(self):
        from services.assistant_output import build_signal_message

        text = build_signal_message(
            {'source_name': 'Federal Reserve', 'title': 'FOMC', 'link': 'https://example.com/fomc'},
            55,
            {
                'summary_tr': '<p>Karar metni yayımlandı.</p><img src="x"><blockquote>embed</blockquote>',
                'alarm_score': 55,
            },
            origin_label='Resmi',
            verified=False,
        )

        self.assertIn('Karar metni yayımlandı.', text)
        self.assertIn('Kaynak/Referans: https://example.com/fomc', text)
        self.assertNotIn('<p>', text)
        self.assertNotIn('<img', text)
        self.assertNotIn('embed', text)

    def test_signal_message_replaces_english_summary_with_turkish_fallback(self):
        from services.assistant_output import build_signal_message

        text = build_signal_message(
            {
                'source_name': 'Federal Reserve',
                'title': 'FOMC rate decision published',
                'link': 'https://example.com/fomc',
            },
            60,
            {
                'summary_tr': 'The Federal Reserve said the committee will keep rates unchanged after the meeting.',
                'alarm_score': 60,
            },
            origin_label='Resmi',
            verified=False,
        )

        self.assertIn('Federal Reserve kaynağı', text)
        self.assertIn('FOMC rate decision published', text)
        self.assertNotIn('The Federal Reserve said', text)

    def test_signal_message_includes_score_reason(self):
        from services.assistant_output import build_signal_message

        text = build_signal_message(
            {'source_name': 'CENTCOM', 'title': 'Hormuz alert', 'link': 'https://example.com'},
            92,
            {
                'summary_tr': 'Hürmüz hattında güvenlik riski arttı.',
                'alarm_score': 92,
                'score_reasons': ['resmi kritik kaynak', 'guvenlik etkisi'],
            },
            origin_label='Resmi',
            verified=False,
        )

        self.assertIn('Risk Gerekcesi: resmi kritik kaynak, guvenlik etkisi', text)
        self.assertIn('Alarm Puanı: 92/100', text)


if __name__ == '__main__':
    unittest.main()
