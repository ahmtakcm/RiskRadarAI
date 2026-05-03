import xml.etree.ElementTree as ET


def parse_rss_items(xml_text: str):
    items = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return items

    for item in root.findall('.//item'):
        title = (item.findtext('title') or '').strip()
        if not title:
            continue
        items.append({
            'title': title,
            'link': (item.findtext('link') or '').strip(),
            'pub_date': (item.findtext('pubDate') or '').strip(),
            'description': (item.findtext('description') or '').strip(),
        })

    if items:
        return items

    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    for entry in root.findall('.//atom:entry', ns):
        title = (entry.findtext('atom:title', default='', namespaces=ns) or '').strip()
        if not title:
            continue
        link_el = entry.find('atom:link', ns)
        link = link_el.attrib.get('href', '').strip() if link_el is not None else ''
        items.append({
            'title': title,
            'link': link,
            'pub_date': (entry.findtext('atom:updated', default='', namespaces=ns) or '').strip(),
            'description': (entry.findtext('atom:summary', default='', namespaces=ns) or '').strip(),
        })
    return items
