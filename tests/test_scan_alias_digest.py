import unittest
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


class ScanAliasAndScoringTests(unittest.TestCase):
    def test_osint_hormuz_item_scores_positive(self):
        from filters.scoring import get_risk_score

        item = {
            'scan_mode': 'osint_only',
            'title': 'CENTCOM monitors Iranian tanker near Strait of Hormuz',
            'description': 'Iran naval activity around Gulf of Oman raises blockade concerns.',
        }
        score, primary_hits, secondary_hits, pattern_hits = get_risk_score(item, {'primary_terms': [], 'secondary_terms': [], 'high_risk_patterns': []})
        self.assertGreater(score, 0)
        self.assertGreaterEqual(score, 35)

    def test_ara_ekonomi_faiz_expands_aliases(self):
        from filters.query_aliases import expand_query_terms

        terms = expand_query_terms('faiz')
        self.assertIn('interest rate', terms)
        self.assertIn('policy rate', terms)
        self.assertIn('central bank rate', terms)

    def test_ara_osint_hurmuz_expands_hormuz_aliases(self):
        from filters.query_aliases import expand_query_terms

        terms = expand_query_terms('h?rm?z')
        self.assertIn('hormuz', terms)
        self.assertIn('strait of hormuz', terms)

    def test_legacy_tara_hurmuz_still_routes(self):
        import commands.manual_scan_commands as manual

        calls = []
        def fake_scan(state, mode='all', manual_query=None, max_feeds=None, **kwargs):
            calls.append((mode, manual_query))
            return []

        with patch.object(manual, 'scan_news', fake_scan):
            reply = manual.handle_manual_scan_command('/tara h?rm?z')
        self.assertTrue(reply)
        self.assertTrue(calls)
        self.assertEqual(calls[0][1], 'h?rm?z')

    def test_social_status_story_key_is_mirror_independent(self):
        from workflows.scan_news import _canonical_story_key

        first = _canonical_story_key({
            'title': 'Fed decision',
            'link': 'https://xcancel.com/federalreserve/status/123456789',
        })
        second = _canonical_story_key({
            'title': 'Fed decision',
            'link': 'https://twitt.re/federalreserve/status/123456789',
        })

        self.assertEqual(first, 'social-status:123456789')
        self.assertEqual(second, first)

    def test_single_official_red_alert_does_not_auto_score_100(self):
        from filters.ai_agent import analyze_signal

        result = analyze_signal({
            'title': 'CENTCOM missile strike causes Hormuz oil shipping disruption',
            'description': 'Attack, sanctions, closure and maritime traffic risk remain elevated.',
            'is_official_source': True,
            'official_red_alert_source': True,
            'official_keyword_hits': ['hormuz', 'strike', 'sanctions', 'closure'],
        })

        self.assertEqual(result['confirmation_class'], 'official_confirmed')
        self.assertLess(result['alarm_score'], 100)
        self.assertIn('resmi kritik kaynak', result['score_reasons'])

    def test_multiple_sources_can_raise_official_red_alert_to_100(self):
        from filters.ai_agent import analyze_signal

        result = analyze_signal({
            'title': 'CENTCOM missile strike causes Hormuz oil shipping disruption',
            'description': 'Attack, sanctions, closure and maritime traffic risk remain elevated.',
            'is_official_source': True,
            'official_red_alert_source': True,
            'official_keyword_hits': ['hormuz', 'strike', 'sanctions', 'closure'],
            'source_count': 2,
        })

        self.assertEqual(result['alarm_score'], 100)
        self.assertIn('2 bagimsiz kaynak', result['score_reasons'])

    def test_global_macro_source_coverage_includes_core_institutions(self):
        data = json.loads(Path('rules/calendar_sources.json').read_text(encoding='utf-8'))
        names = {str(src.get('source_name', '')).lower() for src in data.get('sources', []) if src.get('enabled')}
        ids = {str(src.get('id', '')).lower() for src in data.get('sources', []) if src.get('enabled')}

        self.assertIn('federal reserve', names)
        self.assertIn('fed_fomc', ids)
        self.assertIn('ecb monetary policy', names)
        self.assertIn('bank of england', names)
        self.assertIn('bank of japan', names)
        self.assertIn('imf', names)
        self.assertIn('world bank', names)
        self.assertIn('u.s. treasury', names)


class DigestReliabilityTests(unittest.TestCase):
    def _state_with_item(self, **overrides):
        item = {
            'id': 'x1',
            'timestamp': datetime(2026, 5, 8, 4, 0, tzinfo=timezone.utc).isoformat(),
            'source_name': 'SentDefender',
            'title': 'Hormuz tanker risk rises',
            'text': '',
            'url': 'https://example.com/hormuz',
            'translated_text': '',
            'delivery_mode': 'digest',
            'alert_sent': False,
        }
        item.update(overrides)
        return {'news_log': [item]}

    def test_digest_no_candidates_returns_no_candidates(self):
        import workflows.runner as runner

        state = {'news_log': []}
        result = runner.build_digest_result(state, now=datetime(2026, 5, 8, 5, 0, tzinfo=timezone.utc), force=True, send=False)
        self.assertEqual(result['status'], 'no_candidates')

    def test_digest_fallback_uses_title_source_link_without_translation(self):
        import workflows.runner as runner

        state = self._state_with_item()
        with patch.object(runner.ai_client, 'build_digest_paragraph', lambda items: ''):
            result = runner.build_digest_result(state, now=datetime(2026, 5, 8, 5, 0, tzinfo=timezone.utc), force=True, send=False)
        self.assertEqual(result['status'], 'ready')
        self.assertIn('SentDefender', result['message'])
        self.assertIn('Hormuz tanker risk rises', result['message'])
        self.assertIn('https://example.com/hormuz', result['message'])

    def test_weak_ai_paragraph_falls_back_to_bullets(self):
        import workflows.runner as runner

        state = self._state_with_item(title='Gulf of Oman tanker alert')
        with patch.object(runner.ai_client, 'build_digest_paragraph', lambda items: 'weak'):
            result = runner.build_digest_result(state, now=datetime(2026, 5, 8, 5, 0, tzinfo=timezone.utc), force=True, send=False)
        self.assertEqual(result['status'], 'ready')
        self.assertIn('Gulf of Oman tanker alert', result['message'])

    def test_send_failure_does_not_mark_digest_slot(self):
        import workflows.runner as runner

        state = self._state_with_item()
        def fail_send(text):
            raise RuntimeError('telegram down')

        with patch.object(runner.ai_client, 'build_digest_paragraph', lambda items: ''), \
             patch.object(runner.telegram_client, 'send_message', fail_send):
            result = runner.build_digest_result(state, now=datetime(2026, 5, 8, 5, 0, tzinfo=timezone.utc), force=True, send=True)
        self.assertEqual(result['status'], 'send_failed')
        self.assertNotIn('last_digest_slot', state)

    def test_successful_digest_send_marks_slot(self):
        import workflows.runner as runner

        state = self._state_with_item()
        sent = []
        with patch.object(runner.ai_client, 'build_digest_paragraph', lambda items: ''), \
             patch.object(runner.telegram_client, 'send_message', lambda text: sent.append(text)):
            result = runner.build_digest_result(state, now=datetime(2026, 5, 8, 5, 0, tzinfo=timezone.utc), force=True, send=True)
        self.assertEqual(result['status'], 'sent')
        self.assertTrue(sent)
        self.assertEqual(state.get('last_digest_slot'), '2026-05-08 08:00')


if __name__ == '__main__':
    unittest.main()
