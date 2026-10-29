"""Regression tests for conservative web source filtering."""
import unittest
import app


class WebSourceTrustTests(unittest.TestCase):
    def test_trusted_https_government_domain_is_allowed(self):
        self.assertTrue(app.source_is_trusted("https://www.cdc.gov/example"))

    def test_academic_domain_is_allowed(self):
        self.assertTrue(app.source_is_trusted("https://research.university.edu/paper"))

    def test_known_publisher_is_allowed(self):
        self.assertTrue(app.source_is_trusted("https://www.reuters.com/world/example"))

    def test_unknown_domain_is_rejected(self):
        self.assertFalse(app.source_is_trusted("https://random-blog.example/article"))

    def test_user_generated_social_sources_are_rejected(self):
        self.assertFalse(app.source_is_trusted("https://www.reddit.com/r/example"))

    def test_http_sources_are_rejected(self):
        self.assertFalse(app.source_is_trusted("http://www.cdc.gov/example"))

    def test_lookalike_domains_are_not_allowed(self):
        self.assertFalse(app.source_is_trusted("https://cdc.gov.example.com/page"))

    def test_malformed_url_is_rejected(self):
        self.assertFalse(app.source_is_trusted("not a URL"))

    def test_official_sources_rank_ahead_of_news(self):
        self.assertLess(app.source_priority("cdc.gov"), app.source_priority("reuters.com"))

    def test_scholarly_publishers_rank_ahead_of_general_news(self):
        self.assertLess(app.source_priority("nature.com"), app.source_priority("bbc.com"))

    def test_unknown_domains_do_not_get_primary_source_priority(self):
        self.assertEqual(app.source_priority("random-blog.example"), 2)


if __name__ == "__main__":
    unittest.main()
