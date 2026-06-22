import os
import sys

# Ensure project root is on sys.path when running as a script
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from enrichers.text_hygiene import normalize_content_item, clean_telegram_text
from filters.ai_parse import choose_best_summary


EXAMPLES = [
    # Truth Social index (should be treated as non-event index)
    {
        'title': 'Truth Social Posts of June 5 2026',
        'article_text': '',
        'description': '',
        'source_name': 'Truth Social'
    },
    # Crisis Group index (example index title)
    {
        'title': 'Tehran 5 June 2026 #1',
        'article_text': '',
        'description': '',
        'source_name': 'Crisis Group'
    },
    # Normal article with messy HTML and media fragments
    {
        'title': '<b>Country X</b> launches strikes near Y',
        'article_text': '<div>For immediate release: <p>Country X carried out <i>limited strikes</i> near Y. See video_thumb: https://thumb.example/video.jpg</p></div>',
        'description': '<p>Details: multiple sites hit. amplify_video: 12345</p>',
        'source_name': 'Example News'
    }
]


def run():
    for i, item in enumerate(EXAMPLES, 1):
        print('=' * 60)
        print(f'Example #{i}: raw title: {item.get("title")!r}')
        print('Raw article_text:', item.get('article_text') or '<EMPTY>')
        # Copy item so normalize modifies it in-place for display
        working = dict(item)
        normalize_content_item(working)
        print('Normalized title:', repr(working.get('title')))
        print('Non-event index flag:', bool(working.get('_non_event_index')))
        summary = choose_best_summary(working, {})
        print('Chosen summary:', summary or '<EMPTY>')
        telegram_ready = clean_telegram_text(summary) if summary else clean_telegram_text((working.get('title') or '') + '\n' + (working.get('article_text') or ''))
        print('Telegram-ready text:\n' + telegram_ready)


if __name__ == '__main__':
    run()
