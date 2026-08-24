"""Tests for aspic.didactic: the Portuguese, didactic HTML rendering used
by the live API for legal-professional audiences."""
import re
import shutil

import pytest

from aspic.didactic import render_case_didactic
from aspic.examples import LEGAL_CASES
from aspic.explain import gloss
from aspic.solver import ArgumentationFramework

pytestmark = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz 'dot' not installed")


@pytest.mark.parametrize("case", LEGAL_CASES, ids=[c.id for c in LEGAL_CASES])
def test_render_case_didactic_produces_expected_sections(case):
    html_out = render_case_didactic(case)
    assert f'<section class="case" id="{case.id}">' in html_out
    assert 'class="argument-cards"' in html_out
    assert 'class="conclusion-main"' in html_out
    assert "Ver representação técnica" in html_out
    assert "<svg" in html_out  # the embedded technical graph


@pytest.mark.parametrize("case", LEGAL_CASES, ids=[c.id for c in LEGAL_CASES])
def test_glossary_covers_every_literal_and_rule_in_the_base_framework(case):
    """Regression guard for the hand-authored `atom_glosses`/`rule_glosses`
    content: every literal that can appear as an argument's conclusion (or
    an immediate premise) in the *base* framework, and every rule id, must
    have a real gloss -- not the `` `SYMBOL` `` fallback -- since the
    didactic view never shows counterfactual/axiom-expanded arguments as
    cards."""
    af = ArgumentationFramework(case.knowledge_base, case.causal_model)
    for arg in af.arguments.values():
        text = gloss(case.atom_glosses, arg.conclusion)
        assert not text.startswith("`"), (
            f"case {case.id!r}: missing atom gloss for {arg.conclusion!r}"
        )
    for rule_id in af.rules:
        assert rule_id in case.rule_glosses, (
            f"case {case.id!r}: missing rule gloss for {rule_id!r}"
        )


@pytest.mark.parametrize("case", LEGAL_CASES, ids=[c.id for c in LEGAL_CASES])
def test_no_duplicate_attack_explanation_within_a_single_card(case):
    """Regression test: each argument's `<details>` card must list each
    attack against it exactly once, not once per larger argument built on
    top of it (see the target_id vs target_subargument_id fix)."""
    html_out = render_case_didactic(case)
    for block in re.findall(r'<details class="arg-card[^"]*">.*?</details>', html_out, re.S):
        items = re.findall(r"<li>(.*?)</li>", block, re.S)
        assert len(items) == len(set(items)), f"duplicate attack explanation in case {case.id!r}"


def test_causal_table_uses_plain_language_headers():
    case = LEGAL_CASES[0]
    html_out = render_case_didactic(case)
    assert "Foi indispensável, junto com outros?" in html_out
    assert "É reconhecido como causa?" in html_out
    assert "não ocorreria de jeito nenhum sem ele" in html_out
