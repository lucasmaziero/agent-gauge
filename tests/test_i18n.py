"""Language coverage and the locale-dependent formatters."""
from __future__ import annotations

import string

import pytest

from agent_gauge import api, i18n, theme


@pytest.fixture(autouse=True)
def _restore_language():
    """Every test here moves the global language; put it back."""
    before = i18n.language()
    yield
    i18n.set_language(before)


@pytest.mark.parametrize("code", [c for c in i18n.STRINGS if c != i18n.DEFAULT])
def test_languages_carry_the_same_keys(code):
    """A missing key falls back to English silently, which is how half a
    translation ships without anyone noticing."""
    assert set(i18n.STRINGS[code]) == set(i18n.STRINGS[i18n.DEFAULT])


@pytest.mark.parametrize("code", list(i18n.STRINGS))
def test_placeholders_match_across_languages(code):
    """`{clock}` renamed in one language raises KeyError in front of the user."""
    for key, text in i18n.STRINGS[code].items():
        fields = {f for _, f, _, _ in string.Formatter().parse(text) if f}
        english = {f for _, f, _, _ in
                   string.Formatter().parse(i18n.STRINGS[i18n.DEFAULT][key]) if f}
        assert fields == english, key


def test_every_language_is_listed():
    assert set(i18n.LANGUAGES) == set(i18n.STRINGS)
    assert set(i18n.WEEKDAYS) == set(i18n.STRINGS)
    assert set(i18n.DECIMAL) == set(i18n.STRINGS)


def test_unknown_language_falls_back_to_the_system():
    assert i18n.set_language("klingon") in i18n.STRINGS
    assert i18n.set_language(None) in i18n.STRINGS


def test_translation_and_plural():
    i18n.set_language("en")
    assert i18n.t("panel.window_5h") == "5-hour window"
    assert "1 session" in i18n.tn(1, "panel.tokens_one", "panel.tokens_other",
                                  total="1k", cache="2k")
    assert "2 sessions" in i18n.tn(2, "panel.tokens_one", "panel.tokens_other",
                                   total="1k", cache="2k")

    i18n.set_language("pt_BR")
    assert i18n.t("panel.window_5h") == "Janela de 5 horas"
    assert "1 sessão" in i18n.tn(1, "panel.tokens_one", "panel.tokens_other",
                                 total="1k", cache="2k")
    assert "2 sessões" in i18n.tn(2, "panel.tokens_one", "panel.tokens_other",
                                  total="1k", cache="2k")


def test_formatters_follow_the_language():
    """Translating labels while the numbers stay in one locale is worse than not
    translating: the result reads half converted."""
    now = 1_800_000_000                     # a Friday, in local time
    i18n.set_language("en")
    assert theme.fmt_tokens(6_029_281) == "6.0M"
    assert theme.fmt_weekday(now) == "Fri"
    assert theme.fmt_countdown(now, now) == "now"
    assert theme.status_label(api.Usage(ok=True, status_overall="allowed_warning"))[0] == "WARNING"

    i18n.set_language("pt_BR")
    assert theme.fmt_tokens(6_029_281) == "6,0M"
    assert theme.fmt_weekday(now) == "sex"
    assert theme.fmt_countdown(now, now) == "agora"
    assert theme.status_label(api.Usage(ok=True, status_overall="allowed_warning"))[0] == "ATENÇÃO"


def test_no_string_still_carries_the_old_product_name():
    """Six of them did after the rename, because "Claude Usage" with a space
    matched none of the patterns that were substituted."""
    for code, table in i18n.STRINGS.items():
        for key, text in table.items():
            assert "Claude Usage" not in text, f"{code}/{key}"
            assert "ClaudeUsage" not in text, f"{code}/{key}"
