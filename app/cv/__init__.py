"""The I/O side of the CV fact store.

This package is the ONLY place that reads ``cv.yaml`` — the machine-canonical CV
document — and it **never writes it**. A future importer writes a *draft* to a
separate path for human review; it does not edit this one.

``app/cv/factstore.py`` fails loudly and path-qualified, never default-fills and
never partially loads. A missing date quietly supplied by a default is invented CV
content, which is the one thing this project must not produce.
"""
