"""Pure domain schemas — the types the LLM is constrained to produce.

§6.2's split lives here: **schemas in `app/domain/schemas/`, validation in
`app/llm/`**. A schema is a pure Pydantic model with no I/O, so it is also the
source of the JSON Schema sent to the model (`schema.model_json_schema()`), and
the domain never sees an unvalidated dict.

This package imports no I/O, enforced by `tests/test_import_discipline.py`
(D-24) which scans all of `app/domain`.
"""

from __future__ import annotations

__all__: list[str] = []
