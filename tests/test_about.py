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


def test_links_carry_the_brand_colour(about):
    """A QSS rule for `QLabel a` is ignored by Qt, so the colour has to be on
    the tag; without it every link here renders in the default blue."""
    from agent_gauge import theme

    markup = link("https://example.com", "text")
    assert theme.ACCENT.name() in markup
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
