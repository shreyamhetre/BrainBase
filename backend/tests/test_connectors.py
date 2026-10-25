"""Fast checks for connector parsing and access rules. No database, no model.

Run from the project root: python -m unittest discover -s backend/tests
"""

import unittest
from datetime import datetime, timezone

from app.auth import User, search_roles
from app.connectors.fetch import hidden_note, parse_date, slack_text
from app.ingestion.store import ADMINS_ONLY, SourceDoc


def doc(**kw) -> SourceDoc:
    base = dict(source="slack", external_id="C1:1", title="t", url="u", body="b", allowed_roles=["hr"])
    return SourceDoc(**(base | kw))


class HiddenNote(unittest.TestCase):
    def test_reads_author_and_date_and_strips_note(self):
        handle, date, text = hidden_note("<!-- gitmore: author=priya.sharma, date=2026-05-12T09:30:00Z -->\n\nHello")
        self.assertEqual(handle, "priya.sharma")
        self.assertEqual(date, datetime(2026, 5, 12, 9, 30, tzinfo=timezone.utc))
        self.assertEqual(text, "Hello")

    def test_text_without_note_is_unchanged(self):
        self.assertEqual(hidden_note("Plain text"), (None, None, "Plain text"))

    def test_bad_date_is_none(self):
        self.assertIsNone(parse_date("not a date"))


class SlackText(unittest.TestCase):
    def test_links_and_mentions(self):
        text = "See <https://handbook.gitlab.com/x|the page> and <https://a.b> cc <@U123> &amp; team"
        self.assertEqual(slack_text(text), "See the page (https://handbook.gitlab.com/x) and https://a.b cc  & team")


class AccessRules(unittest.TestCase):
    def test_unmapped_content_is_admins_only(self):
        self.assertEqual(doc(allowed_roles=[]).allowed_roles, [ADMINS_ONLY])

    def test_roles_are_sorted_and_unique(self):
        self.assertEqual(doc(allowed_roles=["sales", "manager", "sales"]).allowed_roles, ["manager", "sales"])

    def test_role_changes_do_not_change_the_hash(self):
        # An access change updates chunks in place; it must not force a re-embed
        self.assertEqual(doc(allowed_roles=["hr"]).content_hash, doc(allowed_roles=["engineer"]).content_hash)

    def test_body_changes_change_the_hash(self):
        self.assertNotEqual(doc(body="a").content_hash, doc(body="b").content_hash)

    def test_only_admins_search_admin_only_content(self):
        admin = User("1", "a@x", "A", ["engineer", "hr"], True, None, None)
        person = User("2", "b@x", "B", ["engineer"], False, None, None)
        self.assertIn(ADMINS_ONLY, search_roles(admin))
        self.assertNotIn(ADMINS_ONLY, search_roles(person))


class SlackChannelRule(unittest.TestCase):
    def setUp(self):
        from app.actions import Channel, Scope, UsableTool
        self.user = User("2", "b@x", "Aiko Tanaka", ["engineer"], False, None, None)
        self.scope = Scope(tools=[UsableTool("t", "slack", "Slack", "u", "a", "slack_send_message", "", {})],
                           channels=[Channel("C1", "#engineering"), Channel("C2", "#general")])

    def check(self, target):
        from app.actions import check
        args = {"channel_id": target, "message": "hi"}
        check(self.scope, self.user, "slack_send_message", args)
        return args["channel_id"]

    def test_readable_channel_by_name_or_id(self):
        self.assertEqual(self.check("#engineering"), "C1")
        self.assertEqual(self.check("general"), "C2")
        self.assertEqual(self.check("C2"), "C2")

    def test_other_channels_and_direct_messages_refused(self):
        from app.actions import ActionRefused
        for target in ("#hr-private", "U0CAYHGT0KZ", ""):
            with self.assertRaises(ActionRefused):
                self.check(target)

    def test_slack_posts_are_signed_as_sent(self):
        from app.actions import sign
        self.assertTrue(sign({"message": "Release done"}, self.user, "slack")["message"].endswith(
            "_Sent with GitMore on behalf of Aiko Tanaka_"))


if __name__ == "__main__":
    unittest.main()
