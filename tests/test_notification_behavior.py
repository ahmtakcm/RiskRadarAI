import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from core.notification_policy import notification_policy_for_source


class FakeTelegram:
    def __init__(self):
        self.messages = []
    def send_message(self, text):
        self.messages.append(text)


class FakeAI:
    def __init__(self, should_notify=True, category='watch', priority_hits=None):
        self.should_notify = should_notify
        self.category = category
        self.priority_hits = priority_hits or []
    def analyze_item(self, item, verification_rules=None, verified=False):
        return {
            'category': self.category,
            'should_notify': self.should_notify,
            'summary_tr': 'Meaningful operational summary with enough detail for alerting.',
            'alarm_score': 80 if self.should_notify else 10,
            'priority_hits': self.priority_hits,
        }
    def is_matching_enabled(self):
        return False


class FakeTranslationAI(FakeAI):
    def analyze_item(self, item, verification_rules=None, verified=False):
        result = super().analyze_item(item, verification_rules, verified)
        result['summary_tr'] = 'Iran attacks Hormuz blockade.'
        return result

    def translate_official_item(self, item):
        return 'Hürmüz ablukası uyarısı', 'CENTCOM, Hürmüz hattında güvenlik riskinin arttığını bildirdi.'


def candidate(source_name='Source', kind='rss', official_class='', source_class='', source_family='', **item_overrides):
    item = {
        'source_name': source_name,
        'source_kind': kind,
        'title': 'Missile strike affects Hormuz maritime traffic and oil routes',
        'description': 'A detailed enough description about maritime risk and security impact.',
        'link': f'https://example.com/{source_name.replace(" ", "_")}',
        'pub_date': 'Thu, 07 May 2026 00:00:00 GMT',
        'official_class': official_class,
        'source_class': source_class,
        'source_family': source_family,
        'notify_policy': item_overrides.pop('notify_policy', ''),
        'confirmation_required': item_overrides.pop('confirmation_required', False),
        'relay_label': item_overrides.pop('relay_label', 'direct'),
        'scan_mode': item_overrides.pop('scan_mode', ''),
        'matched_profile': item_overrides.pop('matched_profile', 'dunya'),
        'triggered_profiles': item_overrides.pop('triggered_profiles', ['dunya']),
    }
    item.update(item_overrides)
    return {
        'hash': f'hash-{source_name}',
        'story_key': f'story-{source_name}',
        'score': 90,
        'pattern_hits': 2,
        'topic_tokens': ['hormuz', 'missile'],
        'item': item,
    }


class NotificationBehaviorTests(unittest.TestCase):
    def run_process(self, official=None, social=None, osint=None, analysis=None, ai=None, active_config=None):
        import workflows.process_candidates as pc
        fake_telegram = FakeTelegram()
        cfg = active_config or {'verification_rules': {}, 'overrides': {}}
        with patch.object(pc, 'telegram_client', fake_telegram), \
             patch.object(pc, 'ai_client', ai or FakeAI()), \
             patch.object(pc, '_ensure_article_text', lambda item: None), \
             patch.object(pc, 'choose_best_summary', lambda item, result: (result or {}).get('summary_tr') or 'stub summary'), \
             patch.object(pc, '_send_cluster_alerts', lambda state, buckets, seen, sent, metrics=None: (sent, set())), \
             patch.object(pc, 'load_active_config', lambda: cfg):
            state = {}
            pc.process_candidates(state, official or [], social or [], osint or [], analysis or [])
            return fake_telegram, state

    def test_strict_official_source_sends_when_candidate_passes(self):
        off = candidate('CENTCOM', official_class='official_military', official_red_alert=True)
        tg, _ = self.run_process(official=[off], ai=FakeAI(should_notify=True))
        self.assertEqual(len(tg.messages), 1)

    def test_official_translation_fallback_uses_provider_text(self):
        off = candidate(
            'CENTCOM',
            official_class='official_military',
            official_red_alert=True,
            title='Iran attacks Hormuz blockade',
            description='Iran attacks Hormuz blockade.',
        )

        tg, _ = self.run_process(official=[off], ai=FakeTranslationAI(should_notify=True))

        self.assertEqual(len(tg.messages), 1)
        self.assertIn('CENTCOM, Hürmüz hattında güvenlik riskinin arttığını bildirdi.', tg.messages[0])
        self.assertNotIn('Iran attacks Hormuz blockade', tg.messages[0])

    def test_routine_official_content_is_suppressed(self):
        off = candidate('Official Routine', official_class='official_government', is_official_routine=True)
        tg, state = self.run_process(official=[off], ai=FakeAI(should_notify=True))
        self.assertEqual(len(tg.messages), 0)
        self.assertEqual(state['news_log'][-1]['drop_reason'], 'routine_suppressed')

    def test_social_source_below_threshold_does_not_alert(self):
        soc = candidate('WhiteHouse X', kind='rss_social', scan_mode='social_only', matched_profile='', triggered_profiles=[])
        tg, state = self.run_process(social=[soc], ai=FakeAI(should_notify=False))
        self.assertEqual(len(tg.messages), 0)
        self.assertEqual(state['news_log'][-1]['drop_reason'], 'profile_mismatch')

    def test_matched_profile_alerts_even_when_ai_rejects_score(self):
        soc = candidate(
            'WhiteHouse X',
            kind='rss_social',
            scan_mode='social_only',
            matched_profile='dunya',
            triggered_profiles=['dunya'],
        )

        tg, _ = self.run_process(social=[soc], ai=FakeAI(should_notify=False, category='ignore'))

        self.assertEqual(len(tg.messages), 1)
        self.assertNotIn('Alarm Puanı:', tg.messages[0])

    def test_process_candidates_emits_observability_counts(self):
        soc = candidate('WhiteHouse X', kind='rss_social', scan_mode='social_only', matched_profile='', triggered_profiles=[])

        with self.assertLogs('process_candidates', level='INFO') as logs:
            tg, state = self.run_process(social=[soc], ai=FakeAI(should_notify=False))

        output = '\n'.join(logs.output)
        self.assertEqual(len(tg.messages), 0)
        self.assertEqual(state['news_log'][-1]['drop_reason'], 'profile_mismatch')
        self.assertIn('candidate_count | stage=process_candidates', output)
        self.assertIn('alert_sent_count | count=0', output)
        self.assertIn('skip_reason_count | stage=process_candidates', output)

    def test_matched_social_is_sent_even_when_unverified_flag_is_false(self):
        soc = candidate('POTUS X', kind='rss_social', scan_mode='social_only')
        cfg = {'verification_rules': {}, 'overrides': {'send_unverified_social_alerts': False}}
        tg, state = self.run_process(social=[soc], ai=FakeAI(should_notify=True), active_config=cfg)
        self.assertEqual(len(tg.messages), 1)

    def test_osint_can_alert_when_should_notify_true(self):
        osint = candidate('Intel Sky', kind='rss_social', scan_mode='osint_only')
        tg, _ = self.run_process(osint=[osint], ai=FakeAI(should_notify=True))
        self.assertEqual(len(tg.messages), 1)

    def test_same_social_status_alerts_once_across_social_and_osint(self):
        social = candidate(
            'WhiteHouse X',
            kind='rss_social',
            scan_mode='social_only',
            link='https://xcancel.com/WhiteHouse/status/123',
        )
        osint = candidate(
            'WhiteHouse OSINT Mirror',
            kind='rss_social',
            scan_mode='osint_only',
            link='https://rss.xcancel.com/WhiteHouse/status/123#m',
        )
        social['hash'] = 'hash-social'
        osint['hash'] = 'hash-osint'
        social['story_key'] = 'social-status:123'
        osint['story_key'] = 'social-status:123'

        tg, _ = self.run_process(social=[social], osint=[osint], ai=FakeAI(should_notify=True))

        self.assertEqual(len(tg.messages), 1)

    def test_analysis_sends_only_with_profile_match(self):
        analysis = candidate('Crisis Group', kind='listing_html', scan_mode='analysis_only', matched_profile='', triggered_profiles=[])
        tg, state = self.run_process(analysis=[analysis], ai=FakeAI(should_notify=False, priority_hits=[]))
        self.assertEqual(len(tg.messages), 0)
        self.assertEqual(state['news_log'][-1]['drop_reason'], 'profile_mismatch')
        matched = candidate('Crisis Group Matched', kind='listing_html', scan_mode='analysis_only')
        tg, _ = self.run_process(analysis=[matched], ai=FakeAI(should_notify=False, priority_hits=[]))
        self.assertEqual(len(tg.messages), 1)

    def test_disabled_ukmto_html_sources_never_selected(self):
        from source_selectors.feed_selector import select_feeds
        active = {
            'profile': {'enabled_feeds': ['UKMTO Warnings', 'UKMTO Advisories', 'UKMTO X Relay']},
            'blocked_sources': set(),
            'feeds': [
                {'name': 'UKMTO Warnings', 'enabled': False, 'kind': 'listing_html'},
                {'name': 'UKMTO Advisories', 'enabled': False, 'kind': 'listing_html'},
                {'name': 'UKMTO X Relay', 'enabled': True, 'kind': 'rss_social', 'official_class': 'official_security_relay', 'applies_to_all_profiles': True},
            ],
        }
        names = [x['name'] for x in select_feeds(active, mode='official_only')]
        self.assertNotIn('UKMTO Warnings', names)
        self.assertNotIn('UKMTO Advisories', names)
        self.assertIn('UKMTO X Relay', names)

    def test_ukmto_x_relay_policy_label_and_alert_capable(self):
        src = {'name': 'UKMTO X Relay', 'kind': 'rss_social', 'source_class': 'official_social_relay', 'relay_label': 'official_social_relay'}
        policy = notification_policy_for_source(src, scan_mode='official_only', source_file='rules/feeds.json')
        self.assertEqual(policy.relay_label, 'official_social_relay')
        self.assertTrue(policy.can_notify_direct)

    def test_truth_social_archive_relay_policy_label(self):
        src = {'name': 'Trump Truth Social', 'kind': 'listing_html', 'source_class': 'relay_archive', 'source_family': 'truth_social_archive'}
        policy = notification_policy_for_source(src, scan_mode='official_only', source_file='rules/feeds.json')
        self.assertEqual(policy.relay_label, 'relay_archive')
        self.assertTrue(policy.relay_archive)


    def test_official_sources_are_shared_across_profiles(self):
        from source_selectors.feed_selector import select_feeds
        active = {
            'profile': {'name': 'saglik', 'enabled_feeds': []},
            'active_profile_names': ['saglik'],
            'blocked_sources': set(),
            'feeds': [
                {'name': 'Federal Reserve FOMC', 'enabled': True, 'kind': 'rss', 'official_class': 'official_central_bank', 'applies_to_all_profiles': True},
                {'name': 'WHO Newsroom', 'enabled': True, 'kind': 'rss', 'official_class': 'official_health_org', 'applies_to_all_profiles': True},
                {'name': 'BBC World', 'enabled': True, 'kind': 'news'},
            ],
            'social_feeds': [],
        }
        names = [x['name'] for x in select_feeds(active, mode='official_only')]
        self.assertIn('Federal Reserve FOMC', names)
        self.assertIn('WHO Newsroom', names)
        self.assertNotIn('BBC World', names)

    def test_shared_official_candidate_records_triggered_profiles(self):
        from source_selectors.profile_policy import evaluate_item_across_active_profiles
        active = {
            'active_profile_names': ['tum_profiller'],
            'profile_policies': {
                'tum_profiller': {'topic_profiles': ['ekonomi', 'saglik']},
                'ekonomi': {'name': 'ekonomi', 'notify_policy': 'market_sensitive', 'min_score': 25, 'include_shared_official_sources': True, 'keyword_set': 'ekonomi', 'keywords_include': ['fomc', 'rate'], 'topic_tags': ['central_bank']},
                'saglik': {'name': 'saglik', 'notify_policy': 'health_risk', 'min_score': 25, 'include_shared_official_sources': True, 'keyword_set': 'saglik', 'keywords_include': ['who'], 'topic_tags': ['health_org']},
            },
            'filters': {'keyword_sets': {'ekonomi': {'primary_terms': ['fomc', 'rate'], 'secondary_terms': [], 'high_risk_patterns': []}, 'saglik': {'primary_terms': ['who'], 'secondary_terms': [], 'high_risk_patterns': []}}},
        }
        item = {'title': 'FOMC policy rate decision', 'description': 'Federal Reserve rate statement', 'applies_to_all_profiles': True, 'source_tags': ['official', 'central_bank']}
        matches = evaluate_item_across_active_profiles(item, active)
        self.assertEqual([m['profile'] for m in matches], ['ekonomi'])

    def test_osint_policy_defaults_to_unverified_allowed_without_confirmation_gate(self):
        src = {'name': 'Intel Sky', 'kind': 'rss_social'}
        policy = notification_policy_for_source(src, scan_mode='osint_only', source_file='rules/osint_feeds.json')
        self.assertEqual(policy.notify_policy, 'keyword_or_score')
        self.assertTrue(policy.can_notify_direct)
        self.assertFalse(policy.requires_official_confirmation)

    def test_osint_unverified_message_is_labeled(self):
        from services.assistant_output import build_signal_message
        text = build_signal_message(
            {'source_name': 'Intel Sky', 'title': 'Missile movement', 'description': 'A detailed field signal.', 'link': 'https://example.com'},
            70,
            {'summary_tr': 'A detailed field signal summary.', 'alarm_score': 70},
            origin_label='OSINT',
            verified=False,
        )
        self.assertIn('Teyit: OSINT / teyitsiz sinyal', text)

    def test_manual_scan_command_uses_scan_without_alerting(self):
        import commands.manual_scan_commands as manual
        calls = []
        def fake_scan(state, mode='all', manual_query=None, max_feeds=None, **kwargs):
            calls.append((mode, manual_query))
            return [candidate('Federal Reserve FOMC', official_class='official_central_bank')] if mode == 'official_only' else []
        with patch.object(manual, 'scan_news', fake_scan):
            reply = manual.handle_manual_scan_command('/ara fomc')
        self.assertIn('Federal Reserve FOMC', reply)
        self.assertEqual(calls, [('official_only', 'fomc')])

    def test_fallback_summary_does_not_show_technical_reason(self):
        import workflows.process_candidates as pc

        item = {
            'title': 'Short',
            'description': 'Russia MFA reported details about Starobelsk and regional security developments with enough detail for fallback.',
            'source_name': 'Russia MFA',
        }
        analysis = {}

        self.assertTrue(pc._ensure_usable_summary(item, analysis, 'Resmi'))
        self.assertIn('summary_tr', analysis)
        self.assertNotIn('reason_short', analysis)

    def test_starobelsk_cluster_cooldown_suppresses_individual_duplicates(self):
        import workflows.process_candidates as pc

        candidates = [
            candidate(
                'Russia MFA',
                title='Russia MFA comments on Starobelsk security incident',
                description='Starobelsk regional security incident update.',
                link='https://example.com/one',
            ),
            candidate(
                'News Wire',
                title='Starobelsk incident draws Russian MFA response',
                description='Russian MFA statement references Starobelsk.',
                link='https://example.com/two',
            ),
        ]
        seen = set()

        with patch.object(pc, 'should_send_cluster', lambda cluster, items: False), \
             patch.object(pc.telegram_client, 'send_message', lambda text: None):
            sent_count, sent_hashes = pc._send_cluster_alerts({}, [('Haber', candidates)], seen, 0)

        self.assertEqual(sent_count, 0)
        self.assertEqual(sent_hashes, {candidates[0]['hash'], candidates[1]['hash']})
        self.assertEqual(seen, sent_hashes)

    def test_starobelsk_individual_alerts_share_event_cooldown_key(self):
        import workflows.process_candidates as pc

        first = candidate(
            'Russia MFA',
            title='Russia MFA comments on Starobelsk security incident',
            description='Starobelsk regional security incident update.',
            link='https://example.com/one',
        )
        second = candidate(
            'News Wire',
            title='Another report on Starobelsk regional security incident',
            description='Russia and Ukraine references around Starobelsk.',
            link='https://example.com/two',
        )

        self.assertEqual(pc._alert_identity(first), 'event:russia-ukraine-starobelsk')
        self.assertEqual(pc._alert_identity(second), 'event:russia-ukraine-starobelsk')

    def test_calendar_sent_alerts_prevents_duplicate_notifications(self):
        import workflows.process_calendar_events as cal
        sent = FakeTelegram()
        now = datetime.now(timezone.utc)
        base_event = {
            'id': 'event1',
            'title': 'FOMC Test',
            'source_name': 'Federal Reserve',
            'category': 'economy',
            'datetime': (now + timedelta(minutes=20)).isoformat(),
            'post_window_minutes': 120,
            'watch_urls': [],
            'publish_signals': ['statement'],
            'sent_alerts': ['24h', '3h', '60m', '30m'],
        }
        with patch.object(cal, 'telegram_client', sent), \
             patch.object(cal, 'analyze_event', lambda event: {}), \
             patch.object(cal, 'export_macro_signal', lambda signal, event: None), \
             patch.object(cal, 'activate_high_alert', lambda event, mode, hours: None):
            changed = cal._handle_event(dict(base_event), now)
        self.assertFalse(changed)
        self.assertEqual(sent.messages, [])

        published_event = dict(base_event)
        published_event['datetime'] = (now - timedelta(minutes=5)).isoformat()
        published_event['sent_alerts'] = ['published']
        with patch.object(cal, 'telegram_client', sent), \
             patch.object(cal, 'analyze_event', lambda event: {}), \
             patch.object(cal, 'export_macro_signal', lambda signal, event: None), \
             patch.object(cal, '_check_publish_signals', lambda event: True), \
             patch.object(cal, 'activate_high_alert', lambda event, mode, hours: None):
            changed = cal._handle_event(published_event, now)
        self.assertFalse(changed)
        self.assertEqual(sent.messages, [])

    def test_calendar_default_thresholds_preserve_existing_long_term_events(self):
        import workflows.process_calendar_events as cal

        event = {
            'id': 'fomc-default',
            'title': 'FOMC Meeting June 16-17 2026',
            'source_name': 'Federal Reserve FOMC',
            'category': 'rate_decision',
            'event_type': 'scheduled_decision',
        }

        self.assertEqual(
            cal._thresholds_for_event(event),
            [('24h', 1440), ('3h', 180), ('60m', 60), ('30m', 30)],
        )

    def test_calendar_high_macro_data_can_skip_last_minute_countdown(self):
        import workflows.process_calendar_events as cal
        sent = FakeTelegram()
        now = datetime.now(timezone.utc)
        event = {
            'id': 'gdp-high',
            'title': 'BEA GDP second estimate',
            'source_name': 'BEA',
            'category': 'macro_data',
            'event_type': 'macro_data_release',
            'datetime': (now + timedelta(minutes=20)).isoformat(),
            'post_window_minutes': 120,
            'watch_urls': [],
            'publish_signals': ['gdp'],
            'sent_alerts': ['24h', '3h'],
        }

        with patch.object(cal, 'telegram_client', sent), \
             patch.object(cal, 'analyze_event', lambda event: {}), \
             patch.object(cal, 'export_macro_signal', lambda signal, event: None), \
             patch.object(cal, 'activate_high_alert', lambda event, mode, hours: None):
            changed = cal._handle_event(event, now)

        self.assertFalse(changed)
        self.assertEqual(sent.messages, [])

    def test_calendar_critical_macro_data_keeps_full_countdown(self):
        from workflows.macro_event_importance import classify_macro_event

        metadata = classify_macro_event({
            'title': 'BLS CPI Consumer Price Index',
            'source_name': 'BLS',
            'category': 'macro_data',
            'event_type': 'macro_data_release',
        })

        self.assertEqual(metadata['importance_level'], 1)
        self.assertEqual(metadata['recommended_pre_alerts_minutes'], [1440, 180, 60, 30])

    def test_calendar_personnel_change_is_critical_macro_event(self):
        from workflows.macro_event_importance import classify_macro_event

        metadata = classify_macro_event({
            'title': 'Federal Reserve Chair nomination announced',
            'source_name': 'Federal Reserve',
            'category': 'central_bank',
            'event_type': 'personnel',
        })

        self.assertEqual(metadata['importance_level'], 1)
        self.assertGreaterEqual(metadata['importance_score'], 90)

    def test_calendar_large_macro_surprise_becomes_critical(self):
        from workflows.macro_event_importance import enrich_macro_event

        event = enrich_macro_event({
            'title': 'BLS CPI Consumer Price Index',
            'source_name': 'BLS',
            'category': 'macro_data',
            'event_type': 'macro_data_release',
            'actual': '3.7',
            'forecast': '3.4',
        })

        self.assertEqual(event['importance_level'], 1)
        self.assertGreaterEqual(event['importance_score'], 95)
        self.assertGreaterEqual(event['surprise_score'], 75)

    def test_calendar_small_macro_surprise_stays_low_noise(self):
        from workflows.macro_event_importance import enrich_macro_event

        event = enrich_macro_event({
            'title': 'Regional retail indicator',
            'source_name': 'Example Source',
            'category': 'macro_data',
            'event_type': 'macro_data_release',
            'actual': '3.41',
            'forecast': '3.40',
        })

        self.assertEqual(event['importance_level'], 3)
        self.assertLess(event['surprise_score'], 30)
        self.assertEqual(event['pre_alerts_minutes'], [])

    def test_calendar_cached_watch_event_upgrades_on_late_surprise(self):
        from workflows.macro_event_importance import enrich_macro_event

        event = {
            'title': 'BLS CPI Consumer Price Index',
            'source_name': 'BLS',
            'category': 'macro_data',
            'event_type': 'macro_data_release',
            'importance_level': 3,
            'importance_score': 50,
            'importance_reason': 'izleme düzeyi makro olay',
            'notification_strategy': 'digest_or_published',
            'pre_alerts_minutes': [],
            'surprise_score': 0,
            'actual': '3.7',
            'forecast': '3.4',
        }

        enriched = enrich_macro_event(event)

        self.assertEqual(enriched['importance_level'], 1)
        self.assertGreaterEqual(enriched['importance_score'], 95)
        self.assertEqual(enriched['pre_alerts_minutes'], [1440, 180, 60, 30])
        self.assertGreaterEqual(enriched['surprise_score'], 75)

    def test_calendar_message_includes_importance_and_surprise_context(self):
        import workflows.process_calendar_events as cal

        event = {
            'title': 'BLS CPI Consumer Price Index',
            'source_name': 'BLS',
            'category': 'macro_data',
            'datetime': '2026-06-10T12:30:00+00:00',
            'importance_score': 95,
            'importance_reason': 'kritik makro sapma',
            'actual': '3.7',
            'forecast': '3.4',
            'surprise_score': 88,
        }

        text = cal._calendar_message(event, 'published')

        self.assertIn('Önem: kritik makro sapma', text)
        self.assertIn('actual=3.7 forecast=3.4', text)
        self.assertNotIn('sapma_skoru=', text)


if __name__ == '__main__':
    unittest.main()
