"""Экспорт отчётов в CSV/XLSX."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from openpyxl import Workbook


def export_csv(rows: Iterable[Sequence], headers: Sequence[str], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        for row in rows:
            writer.writerow(list(row))
    return path


def export_xlsx(rows: Iterable[Sequence], headers: Sequence[str], path: Path, sheet: str = "Report") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = sheet[:31]
    ws.append(list(headers))
    for row in rows:
        out = []
        for v in row:
            if isinstance(v, datetime):
                out.append(v.replace(tzinfo=None))
            else:
                out.append(v)
        ws.append(out)
    wb.save(path)
    return path
