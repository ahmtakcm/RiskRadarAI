from pathlib import Path
import unittest

from parsers.centcom_parser import parse_centcom_listing
from parsers.iran_mfa_new_parser import parse_listing as parse_iran_mfa_listing
from parsers.presidency_app_parser import parse_truth_social_archive
from parsers.rss_parser import parse_rss_items

FIXTURES = Path(__file__).parent / 'fixtures'


class ParserFixtureTests(unittest.TestCase):
    def read_fixture(self, name: str) -> str:
        return (FIXTURES / name).read_text(encoding='utf-8')

    def test_truth_social_archive_fixture(self):
        items = parse_truth_social_archive(
            self.read_fixture('truth_social_archive.html'),
            'https://www.presidency.ucsb.edu/documents/app-attributes/truth-social',
        )
        self.assertEqual(items, [])

    def test_ukmto_relay_fixture(self):
        items = parse_rss_items(self.read_fixture('ukmto_relay.xml'))
        self.assertEqual(len(items), 1)
        self.assertIn('UKMTO WARNING', items[0]['title'])
        self.assertIn('ukmto.org', items[0]['description'])

    def test_centcom_fixture_filters_noise(self):
        items = parse_centcom_listing(self.read_fixture('centcom_listing.html'), 'https://www.centcom.mil/')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['title'], 'CENTCOM Statement on Maritime Security')

    def test_iran_mfa_fixture_filters_navigation(self):
        items = parse_iran_mfa_listing(self.read_fixture('iran_mfa_listing.html'))
        self.assertEqual(len(items), 1)
        self.assertIn('regional security', items[0]['title'].lower())
        self.assertIn('/en/newsview/752111/', items[0]['url'])


if __name__ == '__main__':
    unittest.main()
