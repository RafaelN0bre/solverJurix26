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
from .sufficiency import (
    SufficientSet,
    deductive_closure,
    is_sufficient,
    necessary_elements,
    sufficiency_report,
    sufficient_sets,
)
from .examples import CaseSpec, CausalQuery, LRCLayer, LEGAL_CASES, case_by_id
from .preferences import Dimension, PreferenceModel, RuleProfile, resolved_conflicts
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
    "is_sufficient",
    "necessary_elements",
    "sufficiency_report",
    "sufficient_sets",
    "CaseSpec",
    "CausalQuery",
    "LRCLayer",
    "LEGAL_CASES",
    "case_by_id",
    "Dimension",
    "PreferenceModel",
    "RuleProfile",
    "resolved_conflicts",
    "argument_status",
    "render_to_file",
    "render_to_string",
    "to_dot",
    "causal_comparison_section",
    "ness_html_table",
]
