from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple, List
from types import MappingProxyType


def _as_readonly_row(row: Dict[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(row)


def _safe_str(row: Dict[str, Any], key: str) -> Optional[str]:
    val = row.get(key)
    return val if isinstance(val, str) else None


@dataclass(frozen=True)
class LifecycleIndexes:
    po_by_id: Mapping[str, Mapping[str, Any]]
    ack_by_related: Mapping[str, Tuple[Mapping[str, Any], ...]]
    asn_by_related: Mapping[str, Tuple[Mapping[str, Any], ...]]
    inv_by_related: Mapping[str, Tuple[Mapping[str, Any], ...]]
    fa_by_related: Mapping[str, Tuple[Mapping[str, Any], ...]]


def build_lifecycle_indexes(rows: List[Dict[str, Any]]) -> LifecycleIndexes:
    if not rows:
        return LifecycleIndexes(
            po_by_id=MappingProxyType({}),
            ack_by_related=MappingProxyType({}),
            asn_by_related=MappingProxyType({}),
            inv_by_related=MappingProxyType({}),
            fa_by_related=MappingProxyType({}),
        )

    po_by_id_mut: Dict[str, Mapping[str, Any]] = {}
    ack_by_related_mut: Dict[str, List[Mapping[str, Any]]] = {}
    asn_by_related_mut: Dict[str, List[Mapping[str, Any]]] = {}
    inv_by_related_mut: Dict[str, List[Mapping[str, Any]]] = {}
    fa_by_related_mut: Dict[str, List[Mapping[str, Any]]] = {}

    for row in rows:
        t = row.get("transaction_type")
        doc_id = _safe_str(row, "document_id")
        rel_id = _safe_str(row, "related_document_id")

        if t is None:
            continue

        if t == 850:
            if doc_id:
                po_by_id_mut[doc_id] = _as_readonly_row(row)

        elif t == 855:
            if rel_id:
                ack_by_related_mut.setdefault(rel_id, []).append(_as_readonly_row(row))

        elif t == 856:
            if rel_id:
                asn_by_related_mut.setdefault(rel_id, []).append(_as_readonly_row(row))

        elif t == 810:
            if rel_id:
                inv_by_related_mut.setdefault(rel_id, []).append(_as_readonly_row(row))

        elif t == 997:
            if rel_id:
                fa_by_related_mut.setdefault(rel_id, []).append(_as_readonly_row(row))

    ack_by_related_ro = {k: tuple(v) for k, v in ack_by_related_mut.items()}
    asn_by_related_ro = {k: tuple(v) for k, v in asn_by_related_mut.items()}
    inv_by_related_ro = {k: tuple(v) for k, v in inv_by_related_mut.items()}
    fa_by_related_ro = {k: tuple(v) for k, v in fa_by_related_mut.items()}

    return LifecycleIndexes(
        po_by_id=MappingProxyType(po_by_id_mut),
        ack_by_related=MappingProxyType(ack_by_related_ro),
        asn_by_related=MappingProxyType(asn_by_related_ro),
        inv_by_related=MappingProxyType(inv_by_related_ro),
        fa_by_related=MappingProxyType(fa_by_related_ro),
    )
