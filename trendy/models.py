from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PaperSignals:
    """Topic hits for one submission. The title and abstract are not kept."""

    submitted: datetime
    topics: frozenset[str]
