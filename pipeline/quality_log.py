"""Exclusion / quality log shared by every pipeline stage.

Nothing is dropped silently: every rule records how many rows it touched,
what it did with them, the threshold used, and a few raw row numbers so a
marker (or teammate) can look the original records up.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List

import pandas as pd

SAMPLE_SIZE = 5


@dataclass
class LogEntry:
    stage: str
    rule: str
    action: str            # dropped | flagged | mapped_unknown
    rows_affected: int
    threshold: str = ""
    detail: str = ""
    sample_ids: str = ""


@dataclass
class QualityLog:
    entries: List[LogEntry] = field(default_factory=list)

    def record(self, df: pd.DataFrame, mask: pd.Series, *, stage: str, rule: str,
               action: str, threshold: str = "", detail: str = "") -> int:
        """Log the rows selected by `mask` and return how many there were."""
        mask = mask.fillna(False).astype(bool)
        count = int(mask.sum())
        samples = df.loc[mask, "source_row"].head(SAMPLE_SIZE).astype(str).tolist()
        self.entries.append(LogEntry(stage, rule, action, count, threshold, detail, ",".join(samples)))
        return count

    @property
    def dropped_total(self) -> int:
        return sum(e.rows_affected for e in self.entries if e.action == "dropped")

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(e) for e in self.entries])
