"""Computes perspective-specific readings of a formalized case.
Consumes case records and solver frameworks; supplies the adjudication
structures rendered by `interface.perspective_view`.
"""

"""Readings of a case beyond its unified argumentation framework.

`perspectives` constructs one framework per procedural perspective
(parties and opinions) and reads votes as adjudication moves, following
Prakken's two-phase model of judicial dialogue.

The computations live here; their HTML rendering lives in
`interface.perspective_view`.
"""
