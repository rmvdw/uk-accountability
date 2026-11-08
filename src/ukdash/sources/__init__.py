"""Source adapters. Each publisher gets one adapter; indicators choose it by name.

To add an adapter: create `sources/<name>.py`, subclass `Adapter`, decorate it
with `@register`, and import the module below. Adapters must keep `fetch`
(network) separate from `parse` (offline), so tests can run `parse` against
saved responses.
"""

from __future__ import annotations

# Import adapter modules here so they register themselves.
from . import oecd  # noqa: E402, F401  (registers the adapter)
from .base import ADAPTERS, Adapter, Fetched, register

__all__ = ["ADAPTERS", "Adapter", "Fetched", "register"]
