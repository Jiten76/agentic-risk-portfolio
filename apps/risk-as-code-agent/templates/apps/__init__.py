"""
templates/apps — thin role-specific apps consuming the projection.

Each app exports `render(projection: Dict) -> str` returning the HTML
fragment for that app's panel. The thin renderer assembles them.

Apps in v2.0a:
  ai_gov.py            — AI Governance Lead app (built end-to-end in step 7)
  generic_register.py  — fallback for the other 15 collapsed roles (step 8)

Per `reviews/v2_0a_spec.md` + `reviews/v2_0a_spec_amendments.md` A4 / A6 / A12.
"""

from . import ai_gov, generic_register  # noqa: F401
