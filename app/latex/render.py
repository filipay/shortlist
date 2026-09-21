"""The deterministic ``RenderPlan`` to ``.tex`` renderer.

Rendering is byte-deterministic. The enemies, each with a rule already enforced:

- **Clock** — no ``datetime``/``time``/``now()`` on this path. Any date in a
  rendered CV comes from the fact store, never from the machine.
- **Randomness / hashing order** — no ``random``, no ``uuid``, no iteration over
  a ``set`` or ``dict`` for ordered output. Section order comes from the plan,
  which comes from the fact store's explicit ``order`` field.
- **Template cache / reload** — the environment pins ``auto_reload=False`` and
  ``cache_size=0`` (``app/latex/env.py``).
- **Newlines** — :func:`write_rendered` writes encoded bytes, so no platform
  newline translation can alter the output.

A determinism scan in the test suite (``tests/test_render_determinism.py``)
covers this module and the environment module, so a future edit that adds a clock
import fails the build.
"""

from __future__ import annotations

from pathlib import Path

import jinja2

from app.domain.cv import RenderPlan
from app.latex.env import make_latex_env

#: The committed application template (D-71).
TEMPLATE_NAME = "cv.tex.jinja"
#: The templates directory that ships beside this module.
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def render_plan_to_tex(
    plan: RenderPlan, *, env: jinja2.Environment | None = None
) -> str:
    """Render ``plan`` to ``.tex`` text through the escaping choke point.

    Building the environment per call is cheap (``cache_size=0`` anyway); callers
    that render repeatedly may pass a shared ``env``. Identical input always
    produces identical output.
    """
    if env is None:
        env = make_latex_env(TEMPLATES_DIR)
    template = env.get_template(TEMPLATE_NAME)
    return template.render(plan=plan)


def write_rendered(text: str, destination: Path) -> Path:
    """Write rendered ``text`` to ``destination`` as encoded bytes.

    Bytes, not text: ``Path.write_text`` would apply platform newline
    translation, which is exactly what the golden comparison exists to prevent.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(text.encode("utf-8"))
    return destination


__all__ = ["TEMPLATES_DIR", "TEMPLATE_NAME", "render_plan_to_tex", "write_rendered"]
