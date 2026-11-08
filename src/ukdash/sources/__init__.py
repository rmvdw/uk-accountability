"""Source adapters. Each publisher gets one adapter; indicators choose it by name.

To add an adapter: create `sources/<name>.py`, subclass `Adapter`, decorate it
with `@register`, and import the module below. Adapters must keep `fetch`
(network) separate from `parse` (offline), so tests can run `parse` against
saved responses.
"""

from __future__ import annotations

from .base import ADAPTERS, Adapter, Fetched, register

# Import adapter modules here so they register themselves, e.g.:
# from . import oecd  # noqa: F401

__all__ = ["ADAPTERS", "Adapter", "Fetched", "register"]
