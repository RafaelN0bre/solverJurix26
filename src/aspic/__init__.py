"""ASPIC+ argumentation solver with cause-in-fact detection."""
from .solver import (
    ArgumentationFramework,
    Argument,
    Attack,
    Defeat,
    Literal,
    Rule,
    negate_literal,
)
from .ness import (
    SufficientSet,
    deductive_closure,
    is_ness_cause,
    is_sufficient,
    necessary_elements,
    ness_report,
    sufficient_sets,
)
from .examples import CaseSpec, CausalQuery, LEGAL_CASES, case_by_id
from .graph_export import argument_status, render_to_file, render_to_string, to_dot
from .causal_report import causal_comparison_section, ness_html_table

__all__ = [
    "ArgumentationFramework",
    "Argument",
    "Attack",
    "Defeat",
    "Literal",
    "Rule",
    "negate_literal",
    "SufficientSet",
    "deductive_closure",
    "is_ness_cause",
    "is_sufficient",
    "necessary_elements",
    "ness_report",
    "sufficient_sets",
    "CaseSpec",
    "CausalQuery",
    "LEGAL_CASES",
    "case_by_id",
    "argument_status",
    "render_to_file",
    "render_to_string",
    "to_dot",
    "causal_comparison_section",
    "ness_html_table",
]
