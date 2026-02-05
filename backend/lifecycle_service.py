from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Tuple, List

from .lifecycle_models import (
    EventType,
    Evidence,
    LifecycleEvent,
    CompletenessFlags,
    LifecycleResponse,
)
from .lifecycle_index import LifecycleIndexes

# Deterministic date parser (YYYY-MM-DD only)
def _parse_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except Exception:
        return None

# Extract optional csv_row_index if present
def _get_csv_index(row: Mapping[str, Any]) -> Optional[int]:
    idx = row.get("csv_row_index")
    return idx if isinstance(idx, int) else None

# Deterministic selection:
# a) prefer rows with actual_date (earliest)
# b) else expected_date (earliest)
# c) else lowest csv_row_index
# d) if all csv_row_index missing → pick first per original CSV parse order
#    NOTE: tuples in indexes retain append order from CSV rows iteration
def _choose_row(rows: Tuple[Mapping[str, Any], ...]) -> Optional[Mapping[str, Any]]:
    if not rows:
        return None

    actuals: List[Tuple[Mapping[str, Any], datetime.date]] = []
    for r in rows:
        d = _parse_date(r.get("actual_date"))
        if d:
            actuals.append((r, d))
    if actuals:
        actuals.sort(
            key=lambda x: (
                x[1],
                _get_csv_index(x[0]) if _get_csv_index(x[0]) is not None else float("inf"),
            )
        )
        return actuals[0][0]

    expecteds: List[Tuple[Mapping[str, Any], datetime.date]] = []
    for r in rows:
        d = _parse_date(r.get("expected_date"))
        if d:
            expecteds.append((r, d))
    if expecteds:
        expecteds.sort(
            key=lambda x: (
                x[1],
                _get_csv_index(x[0]) if _get_csv_index(x[0]) is not None else float("inf"),
            )
        )
        return expecteds[0][0]

    rows_with_idx = [(r, _get_csv_index(r)) for r in rows]
    valid_idx = [pair for pair in rows_with_idx if pair[1] is not None]
    if valid_idx:
        valid_idx.sort(key=lambda x: x[1])
        return valid_idx[0][0]

    # Deterministic final fallback: first in tuple order which mirrors CSV parse order
    return rows[0]

# Choose event_date string respecting deterministic rule
def _pick_event_date(row: Mapping[str, Any]) -> Optional[str]:
    a = row.get("actual_date")
    if isinstance(a, str) and _parse_date(a):
        return a
    e = row.get("expected_date")
    if isinstance(e, str) and _parse_date(e):
        return e
    return None

# Build LifecycleEvent from a row, or missing-step placeholder
def _event_from_row(event_type: EventType, row: Optional[Mapping[str, Any]]) -> LifecycleEvent:
    if row is None:
        return LifecycleEvent(event_type=event_type)
    return LifecycleEvent(
        event_type=event_type,
        document_id=row.get("document_id") if isinstance(row.get("document_id"), str) else None,
        related_document_id=row.get("related_document_id") if isinstance(row.get("related_document_id"), str) else None,
        status=row.get("status") if isinstance(row.get("status"), str) else None,
        event_date=_pick_event_date(row),
        partner=row.get("partner") if isinstance(row.get("partner"), str) else None,
        evidence=Evidence(
            csv_row_index=_get_csv_index(row),
            source_fields=dict(row),
        ),
    )

# Assemble lifecycle strictly: PO → ACK → ASN → INV → FA
def build_lifecycle_response(indexes: LifecycleIndexes, po_id: str) -> LifecycleResponse:
    po_row = indexes.po_by_id.get(po_id)
    if po_row is None:
        raise ValueError("PO not found or invalid")
    if po_row.get("transaction_type") != 850:
        raise ValueError("PO must have transaction_type=850")

    ack_rows = indexes.ack_by_related.get(po_id, tuple())
    asn_rows = indexes.asn_by_related.get(po_id, tuple())
    inv_rows = indexes.inv_by_related.get(po_id, tuple())

    selected_po = po_row
    selected_ack = _choose_row(ack_rows)
    selected_asn = _choose_row(asn_rows)
    selected_inv = _choose_row(inv_rows)

    fa_rows_all: List[Mapping[str, Any]] = []
    if inv_rows:
        for inv in inv_rows:
            inv_id = inv.get("document_id")
            if isinstance(inv_id, str):
                fa_candidates = indexes.fa_by_related.get(inv_id, tuple())
                if fa_candidates:
                    fa_rows_all.extend(list(fa_candidates))
    selected_fa = _choose_row(tuple(fa_rows_all))

    events = [
        _event_from_row(EventType.PO, selected_po),
        _event_from_row(EventType.ACK, selected_ack),
        _event_from_row(EventType.ASN, selected_asn),
        _event_from_row(EventType.INV, selected_inv),
        _event_from_row(EventType.FA, selected_fa),
    ]

    completeness = CompletenessFlags(
        has_po=True,
        has_ack=bool(ack_rows),
        has_asn=bool(asn_rows),
        has_inv=bool(inv_rows),
        has_fa=bool(fa_rows_all),
    )

    return LifecycleResponse(
        po_id=po_id,
        events=events,
        completeness=completeness,
    )
