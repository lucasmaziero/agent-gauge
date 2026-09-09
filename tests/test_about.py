"""The about card: what it says after a check, and that a failed check is never
worded as a pass."""
from __future__ import annotations

import pytest

from agent_gauge import i18n, release
from agent_gauge.about import About, link


@pytest.fixture(autouse=True)
def _english():
    before = i18n.language()
    i18n.set_language("en")
    yield
    i18n.set_language(before)


@pytest.fixture
def about(qapp):
    card = About()
    yield card
    card.close()


def latest(tag="", problem=""):
    from agent_gauge.release import Latest

    return Latest(tag=tag, problem=problem)


def test_a_newer_tag_offers_the_release_page(about):
    about._checked(latest("v99.0.0"))
    text = about.status.text()
    assert "v99.0.0" in text
    assert release.DOWNLOAD_URL in text


def test_the_current_version_says_so(about):
    about._checked(latest(f"v{release.__version__}"))
    assert about.status.text() == i18n.t("about.current")
    assert release.DOWNLOAD_URL not in about.status.text()


def test_an_older_tag_is_not_an_update(about):
    about._checked(latest("v0.0.1"))
    assert about.status.text() == i18n.t("about.current")


def test_an_unreachable_github_is_not_reported_as_up_to_date(about):
    """The check did not happen. Saying "latest version" would be a claim the
    app has no basis for."""
    about._checked(latest(problem="offline"))
    assert about.status.text() == i18n.t("about.unreachable")
    assert about.status.text() != i18n.t("about.current")


@pytest.mark.parametrize("problem,key", [
    ("offline", "about.unreachable"),
    ("rate_limited", "about.rate_limited"),
    ("malformed", "about.unreadable"),
    ("untagged", "about.unreadable"),
    ("http:404", "about.unreachable"),      # unrecognised falls back to the vague one
])
def test_each_failure_says_which_one_it_was(about, problem, key):
    """They all used to read "could not reach GitHub", which is a wrong answer
    for four of these five, not a vague one."""
    about._checked(latest(problem=problem))
    assert about.status.text() == i18n.t(key)


def test_the_button_comes_back_after_a_check(about):
    about.button.setEnabled(False)
    about._checked(latest(problem="offline"))
    assert about.button.isEnabled()


def test_links_carry_the_interactive_colour(about):
    """A QSS rule for `QLabel a` is ignored by Qt, so the colour has to be on
    the tag; without it every link here renders in the default blue. It is the
    interactive colour, shared with the panel's hover states - the brand accent
    put an agent's colour on a link that has nothing to do with an agent."""
    from agent_gauge import theme

    markup = link("https://example.com", "text")
    assert theme.INTERACTIVE.name() in markup
    assert theme.ACCENT.name() not in markup
    assert "text-decoration:none" in markup


def test_the_version_is_shown(about, qapp):
    labels = about.findChildren(type(about.status))
    assert any(f"v{release.__version__}" == label.text() for label in labels)


def test_the_card_wears_the_app_s_own_name(about):
    """The rename missed this one: the title was the literal "CLAUDE USAGE",
    upper case with a space, which matched none of the patterns the rename
    substituted. It stayed wrong through two releases."""
    from agent_gauge import about as about_module

    labels = about.findChildren(type(about.status))
    titles = [label.text() for label in labels]
    assert about_module.APP_NAME.upper() in titles
    assert not any("CLAUDE USAGE" in text for text in titles)


def test_the_card_wears_the_app_s_own_mark_not_an_agent_s(about):
    """It wore Clawd - Claude Code's mascot - on a card about Agent Gauge, so
    someone watching Codex read their numbers under the other agent's face.
    The app's mark is the gauge, which is what the icon on their taskbar is."""
    from agent_gauge import brand, theme

    marks = [label.pixmap() for label in about.findChildren(type(about.status))
             if not label.pixmap().isNull()]
    assert len(marks) == 1
    worn = marks[0].toImage()

    dpr = marks[0].devicePixelRatio()
    assert worn == brand.gauge(14, theme.ACCENT, dpr).toImage()
    for key in ("claude", "codex"):
        assert worn != brand.mark(key, 14, theme.ACCENT, dpr).toImage()


def test_the_card_says_what_the_program_is(about):
    """A bare repository URL asks the reader to already know."""
    labels = [label.text() for label in about.findChildren(type(about.status))]
    assert i18n.t("about.tagline") in labels


@pytest.mark.parametrize("code", ["en", "pt_BR"])
def test_both_ways_out_are_offered(about, code):
    """The site and the source, not just the source: the page names the file
    for each platform, which is what someone arriving here actually wants."""
    i18n.set_language(code)
    card = About()
    try:
        body = "".join(label.text()
                       for label in card.findChildren(type(card.status)))
        assert release.SITE_URL in body
        assert release.SOURCE_URL in body
        assert i18n.t("about.site") in body
        assert i18n.t("about.source") in body
    finally:
        card.close()


def test_the_site_and_the_download_page_agree():
    """The download link is the site plus an anchor; if they ever drift apart
    the card offers two different homes for one project."""
    assert release.DOWNLOAD_URL.startswith(release.SITE_URL)
    assert release.SOURCE_URL.endswith(release.REPO)
