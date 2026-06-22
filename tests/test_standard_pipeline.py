from enrichers.text_hygiene import clean_telegram_text, is_non_event_index_title
from enrichers.standard_pipeline import translate_official_item


def test_clean_telegram_text_removes_html():
    raw = '<div>Breaking <b>news</b> – see <a href="https://example.com">link</a></div>'
    out = clean_telegram_text(raw)
    assert 'Breaking' in out
    assert '<' not in out and '>' not in out


def test_truth_social_index_detection():
    t = 'Truth Social Posts of June 5 2026'
    assert is_non_event_index_title(t)


def test_translate_official_item_fallback():
    item = {'title': '<b>Title</b>', 'article_text': '<p>Some <i>content</i></p>'}
    title_tr, text_tr = translate_official_item(item)
    assert 'Title' in title_tr
    assert 'Some content' in text_tr
