"""Shared desktop/web domain layer for aka-semi-utils.

This package must stay UI-framework agnostic: no PyQt, FastAPI, or browser-specific
imports. Desktop and Web surfaces may depend on it; it must not depend on them.
"""
