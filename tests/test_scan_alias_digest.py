import unittest
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
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

    def test_scan_news_emits_observability_counts(self):
        import workflows.scan_news as scan

        active = {
            'profile': {'social_rule_set': 'strict_geopolitics', 'min_score': 9},
            'social_rules': {'strict_geopolitics': {}},
            'verification_rules': {},
            'official_entities': {},
        }
        feed = {'name': 'Test Feed', 'url': 'https://example.com/rss', 'kind': 'rss'}
        items = [
            {
                'title': 'Hormuz maritime alert',
                'link': 'https://example.com/a',
                'pub_date': 'Thu, 07 May 2026 00:00:00 GMT',
                'description': 'Security impact around maritime traffic.',
                'source_name': 'Test Feed',
                'source_kind': 'rss',
            },
            {
                'title': 'Hormuz maritime alert',
                'link': 'https://example.com/a',
                'pub_date': 'Thu, 07 May 2026 00:00:00 GMT',
                'description': 'Security impact around maritime traffic.',
                'source_name': 'Test Feed',
                'source_kind': 'rss',
            },
        ]

        with patch.object(scan, 'select_feeds', lambda cfg, mode='all': [feed]), \
             patch.object(scan, 'select_keywords', lambda cfg: {'primary_terms': [], 'secondary_terms': [], 'high_risk_patterns': []}), \
             patch.object(scan, 'fetch_feed_items', lambda src: items), \
             patch.object(scan, 'evaluate_item_freshness', lambda item, mode, settings: {'is_stale': False}), \
             patch.object(scan, 'classify_content_type', lambda item: 'news'), \
             patch.object(scan, 'annotate_official_context', lambda item, cfg: {}), \
             patch.object(scan, 'should_drop_from_alerting', lambda item: False), \
             patch.object(scan, 'get_risk_score', lambda item, keywords: (30, [], [], 1)), \
             patch.object(scan, 'is_relevant_news', lambda item, keywords, social_rule, min_score: True), \
             self.assertLogs('scan_news', level='INFO') as logs:
            candidates = scan.scan_news({}, mode='social_only', active_config=active)

        output = '\n'.join(logs.output)
        self.assertEqual(len(candidates), 1)
        self.assertIn('scan_started | mode=social_only', output)
        self.assertIn('source_fetch_count | mode=social_only | source=Test Feed | count=2', output)
        self.assertIn('parsed_item_count | mode=social_only | count=2', output)
        self.assertIn('candidate_count | mode=social_only | count=1', output)
        self.assertIn('duplicate_drop_count | mode=social_only | count=1', output)
        self.assertIn('scan_finished | mode=social_only', output)

    def test_rss_xcancel_status_key_matches_xcancel(self):
        from workflows.scan_news import _canonical_story_key

        first = _canonical_story_key({
            'title': 'UKMTO update',
            'link': 'https://rss.xcancel.com/UK_MTO/status/2051749762538389668#m',
        })
        second = _canonical_story_key({
            'title': 'UKMTO update',
            'link': 'https://xcancel.com/UK_MTO/status/2051749762538389668',
        })

        self.assertEqual(first, 'social-status:2051749762538389668')
        self.assertEqual(second, first)

    def test_social_source_owner_mismatch_uses_link_owner_fallback(self):
        from fetchers.feed_fetcher import _apply_social_source_attribution

        item = {
            'source_name': 'WhiteHouse X',
            'link': 'https://xcancel.com/TreyYingst/status/123',
            'official_class': 'official_executive',
            'official_country': 'US',
            'official_red_alert': True,
            'applies_to_all_profiles': True,
        }

        _apply_social_source_attribution(item, {'name': 'WhiteHouse X', 'url': 'https://xcancel.com/WhiteHouse/rss'})

        self.assertEqual(item['source_name'], 'TreyYingst X')
        self.assertTrue(item['source_attribution_mismatch'])
        self.assertEqual(item['official_class'], '')
        self.assertFalse(item['official_red_alert'])

    def test_topic_tokens_ignore_html_image_noise(self):
        from core.matching import build_topic_tokens

        tokens = build_topic_tokens({
            'title': 'Bila Tserkva strike update',
            'description': '<img src="https://pbs.twimg.com/media/x.jpg" style="width:250px"> Russia Ukraine update',
        })

        self.assertIn('bila', tokens)
        self.assertIn('tserkva', tokens)
        self.assertNotIn('img', tokens)
        self.assertNotIn('style', tokens)
        self.assertNotIn('twimg', tokens)
        self.assertNotIn('pbs', tokens)
        self.assertNotIn('jpg', tokens)

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

    def test_generated_fomc_events_keep_full_countdown_strategy(self):
        from scripts.generate_macro_calendar_events import parse_fomc

        events = parse_fomc()

        self.assertTrue(events)
        self.assertTrue(all(event['pre_alerts_minutes'] == [1440, 180, 60, 30] for event in events))
        self.assertTrue(all(event['importance_level'] == 1 for event in events))

    def test_generated_tcmb_events_keep_full_countdown_strategy(self):
        from scripts.generate_macro_calendar_events import parse_tcmb_calendar

        events = parse_tcmb_calendar()

        self.assertTrue(events)
        self.assertTrue(all(event['pre_alerts_minutes'] == [1440, 180, 60, 30] for event in events))
        self.assertTrue(all(event['importance_level'] == 1 for event in events))

    def _official_scan_config(self):
        return {
            'profile': {'social_rule_set': 'strict_geopolitics', 'min_score': 9},
            'social_rules': {'strict_geopolitics': {}},
            'verification_rules': {},
            'official_entities': {
                'official_keyword_override_terms': ['strike', 'operation', 'sanctions', 'advisory'],
                'official_sources_red_alert': [],
                'iran_official_entities': [],
                'trusted_secondary_sources': [],
                'official_routine_terms': ['ceremony', 'memorial day', 'holiday message', 'visit'],
            },
            'profile_policies': {},
        }

    def _scan_one_item(self, feed, item, *, freshness=None, relevant=False, profile_matches=None):
        import workflows.scan_news as scan

        active = self._official_scan_config()
        state = {}
        freshness = freshness or {'is_stale': False, 'age_minutes': 10, 'max_age_minutes': 180}
        profile_matches = [] if profile_matches is None else profile_matches

        with patch.object(scan, 'select_feeds', lambda cfg, mode='all': [feed]), \
             patch.object(scan, 'select_keywords', lambda cfg: {'primary_terms': [], 'secondary_terms': [], 'high_risk_patterns': []}), \
             patch.object(scan, 'fetch_feed_items', lambda src: [item]), \
             patch.object(scan, 'evaluate_item_freshness', lambda item, mode, settings: freshness), \
             patch.object(scan, 'classify_content_type', lambda item: 'news'), \
             patch.object(scan, 'should_drop_from_alerting', lambda item: False), \
             patch.object(scan, 'evaluate_item_across_active_profiles', lambda item, cfg: profile_matches), \
             patch.object(scan, 'is_relevant_news', lambda item, keywords, social_rule, min_score: relevant), \
             self.assertLogs('scan_news', level='INFO') as logs:
            candidates = scan.scan_news(state, mode='official_only', active_config=active)

        return candidates, state, '\n'.join(logs.output)

    def test_official_state_dept_iran_talks_survives_not_relevant(self):
        feed = {
            'name': 'StateDept X',
            'kind': 'rss_social',
            'official_class': 'official_diplomacy',
            'applies_to_all_profiles': True,
        }
        item = {
            'title': 'Secretary comments after Iran talks',
            'description': 'Diplomatic talks update.',
            'link': 'https://example.com/state',
            'source_name': 'StateDept X',
            'source_kind': 'rss_social',
            'official_class': 'official_diplomacy',
            'applies_to_all_profiles': True,
        }

        candidates, _, output = self._scan_one_item(feed, item, relevant=False)

        self.assertEqual(len(candidates), 1)
        self.assertIn('official_critical_relevance_kept', output)

    def test_official_centcom_operation_survives_not_relevant(self):
        feed = {
            'name': 'CENTCOM X',
            'kind': 'rss_social',
            'official_class': 'official_military',
            'official_red_alert': True,
            'applies_to_all_profiles': True,
        }
        item = {
            'title': 'CENTCOM operation follows missile strike warning',
            'description': 'Operational update.',
            'link': 'https://example.com/centcom',
            'source_name': 'CENTCOM X',
            'source_kind': 'rss_social',
            'official_class': 'official_military',
            'official_red_alert': True,
            'applies_to_all_profiles': True,
        }

        candidates, _, output = self._scan_one_item(feed, item, relevant=False)

        self.assertEqual(len(candidates), 1)
        self.assertIn('official_critical_relevance_kept', output)

    def test_official_treasury_sanctions_survives_not_relevant(self):
        feed = {
            'name': 'USTreasury X',
            'kind': 'rss_social',
            'official_class': 'official_finance',
            'applies_to_all_profiles': True,
        }
        item = {
            'title': 'Treasury announces new sanctions',
            'description': 'Sanctions action published.',
            'link': 'https://example.com/treasury',
            'source_name': 'USTreasury X',
            'source_kind': 'rss_social',
            'official_class': 'official_finance',
            'applies_to_all_profiles': True,
        }

        candidates, _, output = self._scan_one_item(feed, item, relevant=False)

        self.assertEqual(len(candidates), 1)
        self.assertIn('official_critical_relevance_kept', output)

    def test_stale_official_ukmto_advisory_is_kept_for_digest(self):
        feed = {
            'name': 'UKMTO X Relay',
            'kind': 'rss_social',
            'official_class': 'official_security_relay',
            'applies_to_all_profiles': True,
        }
        item = {
            'title': 'UKMTO advisory reports maritime security incident',
            'description': 'Security incident advisory.',
            'link': 'https://example.com/ukmto',
            'source_name': 'UKMTO X Relay',
            'source_kind': 'rss_social',
            'official_class': 'official_security_relay',
            'applies_to_all_profiles': True,
        }

        candidates, state, output = self._scan_one_item(
            feed,
            item,
            freshness={'is_stale': True, 'age_minutes': 900, 'max_age_minutes': 180},
        )

        self.assertEqual(candidates, [])
        self.assertEqual(state['news_log'][-1]['drop_reason'], 'official_critical_digest_kept')
        self.assertIn('official_critical_digest_kept', output)

    def test_official_memorial_ceremony_still_suppressed(self):
        feed = {
            'name': 'WhiteHouse X',
            'kind': 'rss_social',
            'official_class': 'official_executive',
            'applies_to_all_profiles': True,
        }
        item = {
            'title': 'Memorial Day ceremony message',
            'description': 'Holiday message and ceremony.',
            'link': 'https://example.com/ceremony',
            'source_name': 'WhiteHouse X',
            'source_kind': 'rss_social',
            'official_class': 'official_executive',
            'applies_to_all_profiles': True,
        }

        candidates, _, output = self._scan_one_item(
            feed,
            item,
            relevant=True,
            profile_matches=[{'profile': 'resmi_kritik', 'score': 30}],
        )

        self.assertEqual(candidates, [])
        self.assertIn('routine_suppressed', output)

    def test_social_not_relevant_behavior_is_unchanged(self):
        feed = {'name': 'SentDefender', 'kind': 'rss_social'}
        item = {
            'title': 'Iran missile warning',
            'description': 'Unofficial social report.',
            'link': 'https://example.com/social',
            'source_name': 'SentDefender',
            'source_kind': 'rss_social',
        }

        candidates, _, output = self._scan_one_item(feed, item, relevant=False)

        self.assertEqual(candidates, [])
        self.assertIn('reason=not_relevant', output)
        self.assertNotIn('official_critical_relevance_kept', output)


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

    def test_digest_result_emits_candidate_and_final_counts(self):
        import workflows.runner as runner

        state = self._state_with_item()
        state['news_log'].append({
            'id': 'x2',
            'timestamp': datetime(2026, 5, 8, 4, 5, tzinfo=timezone.utc).isoformat(),
            'source_name': 'Intel Sky',
            'title': 'Second digest item',
            'text': '',
            'url': 'https://example.com/second',
            'translated_text': '',
            'delivery_mode': 'digest',
            'alert_sent': False,
        })

        with patch.object(runner.ai_client, 'build_digest_paragraph', lambda items: ''), \
             self.assertLogs('runner', level='INFO') as logs:
            result = runner.build_digest_result(state, now=datetime(2026, 5, 8, 5, 0, tzinfo=timezone.utc), force=True, send=False)

        output = '\n'.join(logs.output)
        self.assertEqual(result['status'], 'ready')
        self.assertIn('digest_candidate_count | count=2 | usable_count=2', output)
        self.assertIn('digest_final_count | count=2', output)

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

    def test_stale_recent_scan_item_enters_digest_pool_without_candidate(self):
        import workflows.scan_news as scan

        state = {'news_log': []}
        active_config = {
            'profile': {'social_rule_set': 'strict_geopolitics', 'min_score': 9},
            'social_rules': {'strict_geopolitics': {}},
            'verification_rules': {},
            'official_entities': {},
        }
        runtime_settings = SimpleNamespace(
            drop_stale_items=True,
            social_max_age_minutes=120,
            osint_max_age_minutes=240,
            official_max_age_minutes=360,
            news_max_age_minutes=720,
            analysis_max_age_minutes=20160,
            digest_max_age_minutes=720,
        )
        pub_date = (datetime.now(timezone.utc) - timedelta(minutes=180)).isoformat()
        item = {
            'title': 'Fed liquidity facility update',
            'link': 'https://xcancel.com/federalreserve/status/987654321',
            'pub_date': pub_date,
            'description': 'Federal Reserve liquidity facility mention from social mirror.',
            'source_name': 'Fed mirror',
            'source_kind': 'rss_social',
        }

        with patch.object(scan, 'select_feeds', lambda cfg, mode='all': [{'name': 'Fed mirror'}]), \
             patch.object(scan, 'select_keywords', lambda cfg: {'primary_terms': [], 'secondary_terms': [], 'high_risk_patterns': []}), \
             patch.object(scan, 'fetch_feed_items', lambda feed: [item]):
            candidates = scan.scan_news(
                state,
                mode='social_only',
                active_config=active_config,
                settings_override=runtime_settings,
            )

        self.assertEqual(candidates, [])
        self.assertEqual(len(state['news_log']), 1)
        entry = state['news_log'][0]
        self.assertEqual(entry['id'], 'DIGEST_social-status:987654321')
        self.assertEqual(entry['delivery_mode'], 'digest')
        self.assertEqual(entry['drop_reason'], 'stale')
        self.assertFalse(entry['alert_sent'])

    def test_very_old_stale_scan_item_stays_out_of_digest_pool(self):
        import workflows.scan_news as scan

        state = {'news_log': []}
        active_config = {
            'profile': {'social_rule_set': 'strict_geopolitics', 'min_score': 9},
            'social_rules': {'strict_geopolitics': {}},
            'verification_rules': {},
            'official_entities': {},
        }
        runtime_settings = SimpleNamespace(
            drop_stale_items=True,
            social_max_age_minutes=120,
            osint_max_age_minutes=240,
            official_max_age_minutes=360,
            news_max_age_minutes=720,
            analysis_max_age_minutes=20160,
            digest_max_age_minutes=720,
        )
        pub_date = (datetime.now(timezone.utc) - timedelta(minutes=900)).isoformat()
        item = {
            'title': 'Old social mirror item',
            'link': 'https://xcancel.com/example/status/111',
            'pub_date': pub_date,
            'description': 'Old backlog item.',
            'source_name': 'Example mirror',
            'source_kind': 'rss_social',
        }

        with patch.object(scan, 'select_feeds', lambda cfg, mode='all': [{'name': 'Example mirror'}]), \
             patch.object(scan, 'select_keywords', lambda cfg: {'primary_terms': [], 'secondary_terms': [], 'high_risk_patterns': []}), \
             patch.object(scan, 'fetch_feed_items', lambda feed: [item]):
            candidates = scan.scan_news(
                state,
                mode='social_only',
                active_config=active_config,
                settings_override=runtime_settings,
            )

        self.assertEqual(candidates, [])
        self.assertEqual(state['news_log'], [])


if __name__ == '__main__':
    unittest.main()
