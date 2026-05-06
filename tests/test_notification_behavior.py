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
             patch.object(pc, '_send_cluster_alerts', lambda state, buckets, seen, sent: (sent, set())), \
             patch.object(pc, 'load_active_config', lambda: cfg):
            state = {}
            pc.process_candidates(state, official or [], social or [], osint or [], analysis or [])
            return fake_telegram, state

    def test_strict_official_source_sends_when_candidate_passes(self):
        off = candidate('CENTCOM', official_class='official_military', official_red_alert=True)
        tg, _ = self.run_process(official=[off], ai=FakeAI(should_notify=True))
        self.assertEqual(len(tg.messages), 1)

    def test_routine_official_content_is_suppressed(self):
        off = candidate('Official Routine', official_class='official_government', is_official_routine=True)
        tg, state = self.run_process(official=[off], ai=FakeAI(should_notify=True))
        self.assertEqual(len(tg.messages), 0)
        self.assertEqual(state['news_log'][-1]['drop_reason'], 'routine_suppressed')

    def test_social_source_below_threshold_does_not_alert(self):
        soc = candidate('WhiteHouse X', kind='rss_social', scan_mode='social_only')
        tg, state = self.run_process(social=[soc], ai=FakeAI(should_notify=False))
        self.assertEqual(len(tg.messages), 0)
        self.assertEqual(state['news_log'][-1]['drop_reason'], 'below_alert_threshold')

    def test_social_unverified_false_is_held_unless_verified(self):
        soc = candidate('POTUS X', kind='rss_social', scan_mode='social_only')
        cfg = {'verification_rules': {}, 'overrides': {'send_unverified_social_alerts': False}}
        tg, state = self.run_process(social=[soc], ai=FakeAI(should_notify=True), active_config=cfg)
        self.assertEqual(len(tg.messages), 0)
        self.assertEqual(state['news_log'][-1]['drop_reason'], 'unverified_hold')

    def test_osint_can_alert_when_should_notify_true(self):
        osint = candidate('Intel Sky', kind='rss_social', scan_mode='osint_only')
        tg, _ = self.run_process(osint=[osint], ai=FakeAI(should_notify=True))
        self.assertEqual(len(tg.messages), 1)

    def test_analysis_sends_only_with_should_notify_or_priority_hits(self):
        analysis = candidate('Crisis Group', kind='listing_html', scan_mode='analysis_only')
        tg, state = self.run_process(analysis=[analysis], ai=FakeAI(should_notify=False, priority_hits=[]))
        self.assertEqual(len(tg.messages), 0)
        self.assertEqual(state['news_log'][-1]['drop_reason'], 'below_alert_threshold')
        tg, _ = self.run_process(analysis=[analysis], ai=FakeAI(should_notify=False, priority_hits=['hormuz']))
        self.assertEqual(len(tg.messages), 1)

    def test_disabled_ukmto_html_sources_never_selected(self):
        from source_selectors.feed_selector import select_feeds
        active = {
            'profile': {'enabled_feeds': ['UKMTO Warnings', 'UKMTO Advisories', 'UKMTO X Relay']},
            'blocked_sources': set(),
            'feeds': [
                {'name': 'UKMTO Warnings', 'enabled': False, 'kind': 'listing_html'},
                {'name': 'UKMTO Advisories', 'enabled': False, 'kind': 'listing_html'},
                {'name': 'UKMTO X Relay', 'enabled': True, 'kind': 'rss_social'},
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


if __name__ == '__main__':
    unittest.main()
