"""
Root-level conftest.py — ensures the backend package is importable during pytest runs.

Placing this file at backend/ makes pytest use backend/ as its rootdir, which
is inserted into sys.path so that `import app.*` resolves correctly without
requiring a separate install step.
"""
