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

    def test_clean_telegram_text_removes_escaped_html_noise(self):
        from enrichers.text_hygiene import clean_telegram_text

        raw = (
            '&lt;p&gt;Fed update&lt;/p&gt;'
            '&lt;img src="x.png"&gt;'
            '&lt;a href="https://example.com/fed"&gt;Read&lt;/a&gt;'
        )

        cleaned = clean_telegram_text(raw)

        self.assertIn('Fed update', cleaned)
        self.assertIn('Read (https://example.com/fed)', cleaned)
        self.assertNotIn('<img', cleaned)
        self.assertNotIn('&lt;img', cleaned)
        self.assertNotIn('<a href', cleaned)

    def test_simple_tr_rewrite_does_not_create_hybrid_text(self):
        from enrichers.text_hygiene import simple_tr_rewrite

        text = simple_tr_rewrite('Iranian local region students killed in attacks on Israeli communities.')

        self.assertEqual(text, 'Iranian local region students killed in attacks on Israeli communities.')
        self.assertNotIn('İranlı local region', text)
        self.assertNotIn('students öldürüldü', text)

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

        self.assertIn('Fed, faiz kararı gündemine ilişkin resmi açıklama yaptı.', text)
        self.assertNotIn('FOMC rate decision published', text)
        self.assertNotIn('The Federal Reserve said', text)

    def test_signal_message_does_not_embed_raw_english_title_fallback(self):
        from services.assistant_output import build_signal_message

        text = build_signal_message(
            {
                'source_name': 'CENTCOM',
                'title': 'Iran attacks Hormuz blockade',
                'link': 'https://example.com/hormuz',
            },
            85,
            {
                'summary_tr': 'Iran attacks Hormuz blockade.',
                'alarm_score': 85,
            },
            origin_label='Resmi',
            verified=False,
        )

        self.assertIn('CENTCOM, Hürmüz hattı konusunda uyarı yaptı.', text)
        self.assertNotIn('Iran attacks Hormuz blockade', text)
        self.assertNotIn('Hürmüz blockade', text)

    def test_state_dept_title_gets_concise_event_fallback(self):
        from services.assistant_output import build_signal_message

        text = build_signal_message(
            {
                'source_name': 'StateDept X',
                'title': 'Secretary comments after Iran talks in Oman',
                'link': 'https://example.com/state',
            },
            80,
            {'summary_tr': 'Secretary comments after Iran talks in Oman.', 'alarm_score': 80},
            origin_label='Resmi',
            verified=False,
        )

        self.assertIn('ABD Dışişleri İran görüşmelerine ilişkin açıklama yaptı.', text)
        self.assertNotIn('gelişmeye ilişkin yeni bir kayıt aktardı', text)
        self.assertNotIn('Secretary comments after Iran talks', text)

    def test_idf_title_gets_concise_event_fallback(self):
        from services.assistant_output import build_signal_message

        text = build_signal_message(
            {
                'source_name': 'IDF X',
                'title': 'IDF releases footage of Hezbollah tunnel infrastructure in southern Lebanon',
                'link': 'https://example.com/idf',
            },
            88,
            {'summary_tr': 'IDF releases footage of Hezbollah tunnel infrastructure.', 'alarm_score': 88},
            origin_label='Resmi',
            verified=False,
        )

        self.assertIn('IDF Güney Lübnan’daki Hizbullah altyapısına ilişkin görüntü paylaştı.', text)
        self.assertNotIn('Hezbollah tunnel infrastructure', text)
        self.assertNotIn('gelişmeye ilişkin yeni bir kayıt aktardı', text)

    def test_nato_exercise_title_gets_concise_event_fallback(self):
        from services.assistant_output import build_signal_message

        text = build_signal_message(
            {
                'source_name': 'NATO',
                'title': 'NATO launches northern anti-submarine warfare exercise',
                'link': 'https://example.com/nato',
            },
            70,
            {'summary_tr': 'NATO launches northern anti-submarine warfare exercise.', 'alarm_score': 70},
            origin_label='Resmi',
            verified=False,
        )

        self.assertIn('NATO, kuzey bölgelerinde denizaltı savaşı tatbikatı başlattı.', text)
        self.assertNotIn('anti-submarine warfare exercise', text)
        self.assertNotIn('gelişmeye ilişkin yeni bir kayıt aktardı', text)

    def test_signal_message_fallback_strips_html_image_link_tokens(self):
        from services.assistant_output import build_signal_message

        text = build_signal_message(
            {
                'source_name': 'WhiteHouse X',
                'title': '<img src="https://pbs.twimg.com/media/x.jpg" style="width:250px">Iran update',
                'link': 'https://xcancel.com/WhiteHouse/status/1',
            },
            60,
            {
                'summary_tr': '<img src="https://pbs.twimg.com/media/x.jpg" style="width:250px">The update said attacks on Israeli communities continued.',
                'alarm_score': 60,
            },
            origin_label='Sosyal',
            verified=False,
        )

        self.assertIn('Beyaz Saray, İran gündemine ilişkin resmi açıklama yaptı.', text)
        self.assertNotIn('<img', text)
        self.assertNotIn('style', text)
        self.assertNotIn('twimg', text)
        self.assertNotIn('pbs', text)
        self.assertNotIn('jpg', text)
        self.assertNotIn('250px', text)

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
