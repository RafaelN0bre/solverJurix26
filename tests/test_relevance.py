"""Validation against the paper's own adversarial examples for relevance
(Section 3), not just the legal case studies. These are the examples the
authors use to show why their notion of a support set/explanation
(Definition 3.3) is *stricter* than the broader notions of Borg & Bex [9]
and Fan & Toni [12] -- so they're exactly the right stress test for
`support_set_for_argument`.

Both examples are given as *abstract* Dung argumentation frameworks
(arguments + defeat edges), not ASPIC+ theories, so they're encoded here as
a small ASPIC+ theory that reproduces the same defeat graph: each abstract
node X gets an "identity" premise trigX (always true) and rule
"rX: trigX => X", and each abstract edge X -> Y becomes an undercutting
rule "uXY: X => ¬rY" -- X's own conclusion attacks Y's derivation rule.
Undercutting always succeeds regardless of the basic ordering, so this
reproduces an unconditional Dung-style defeat edge; and because uXY
inherits rX in its cumulative rule set, defeating X also disables X's
attack on Y, which is exactly the reinstatement behaviour the abstract
semantics requires.

Because each node is encoded across two ASPIC+ arguments (its identity and
its outgoing attacks), a winning-strategy move that "is" abstract node D is
realized by the argument that attacks using D (e.g. "D => ¬rB"), not by D's
bare identity argument. Both arguments share the same underlying premise
(trigD), so support sets are compared by the *premises they trace back to*
rather than by raw argument ids -- an encoding-independent way to check
"the explanation only depends on trigA and trigD, not trigC".
"""
from aspic.solver import ArgumentationFramework


def _encode_abstract_af(nodes, edges):
    premises = [f"trig{n}" for n in nodes]
    rules = [f"r{n}: trig{n} => {n}" for n in nodes]
    for x, y in edges:
        rules.append(f"u{x}{y}: {x} => ¬r{y}")
    kb = {"premises": premises, "axioms": []}
    model = {"strict_rules": [], "defeasible_rules": rules}
    return ArgumentationFramework(kb, model)


def _traced_premises(af, support_arg_ids):
    traced = set()
    for arg_id in support_arg_ids:
        traced |= af.arguments[arg_id].premises
    return traced


def test_example_3_1_figure_1_relevance():
    """Example 3.1 (Figure 1): grounded extension {A,D,F,G}. C and G are
    (in)direct defenders of A in the broader Borg & Bex sense, but
    defeating C doesn't change A's status -- only A or D being defeated
    would. The paper's own text: 'C and G should not be regarded as
    relevant to A.'
    """
    nodes = ["A", "B", "C", "D", "E", "F", "G"]
    edges = [("B", "A"), ("C", "B"), ("D", "B"), ("F", "C"), ("E", "F"), ("G", "E")]
    af = _encode_abstract_af(nodes, edges)

    extension, _ = af.compute_grounded_extension()
    justified_nodes = {af.arguments[a].conclusion for a in extension} & set(nodes)
    assert justified_nodes == {"A", "D", "F", "G"}

    a_arg = next(a for a in extension if af.arguments[a].conclusion == "A")
    support = af.support_set_for_argument(a_arg, extension)
    assert _traced_premises(af, support) == {"trigA", "trigD"}


def test_example_3_2_figure_4_relevance():
    """Example 3.2 (Figure 4): grounded extension {A,C,D}. {A,C} is a
    'compact explanation' of A under Fan & Toni's related-admissible-set
    notion, and a subset of the grounded extension -- but the paper argues
    C should NOT be in the support set of A, since A is justified because
    of D specifically: deleting D (not C) would drop A from the grounded
    extension. Definition 3.3's own restated fact: '{A, D} is the only
    subset-minimal strongly admissible subset of E containing A.'
    """
    nodes = ["A", "B", "C", "D"]
    edges = [("B", "A"), ("C", "B"), ("D", "B"), ("B", "C")]
    af = _encode_abstract_af(nodes, edges)

    extension, _ = af.compute_grounded_extension()
    justified_nodes = {af.arguments[a].conclusion for a in extension} & set(nodes)
    assert justified_nodes == {"A", "C", "D"}

    a_arg = next(a for a in extension if af.arguments[a].conclusion == "A")
    support = af.support_set_for_argument(a_arg, extension)
    assert _traced_premises(af, support) == {"trigA", "trigD"}  # not trigC
