from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from .lifecycle_models import POListItem, LifecycleResponse
from .lifecycle_index import LifecycleIndexes, build_lifecycle_indexes
from .lifecycle_service import build_lifecycle_response
from . import main

router = APIRouter()

_indexes: Optional[LifecycleIndexes] = None
_rows_ref: Optional[List[Dict[str, Any]]] = None


def _ensure_indexes() -> Optional[LifecycleIndexes]:
    global _indexes, _rows_ref
    # Always read from main.edi_rows to reflect latest CSV upload
    if not main.edi_rows:
        _indexes = None
        _rows_ref = None
        return None
    if _rows_ref is not main.edi_rows:
        _indexes = build_lifecycle_indexes(main.edi_rows)
        _rows_ref = main.edi_rows
    return _indexes


@router.get("/lifecycle/po-list")
def get_po_list():
    if not main.edi_rows:
        return {"csv_loaded": False, "pos": []}
    pos: List[POListItem] = []
    for row in main.edi_rows:
        t = row.get("transaction_type")
        if t == "850" or t == 850:
            doc_id = row.get("document_id")
            if not isinstance(doc_id, str):
                continue
            partner = row.get("partner")
            status = row.get("status")
            po_date = row.get("expected_date")
            pos.append({
                "document_id": doc_id,
                "partner": partner if isinstance(partner, str) else None,
                "status": status if isinstance(status, str) else None,
                "po_date": po_date if isinstance(po_date, str) else None,
            })
    return {"csv_loaded": True, "pos": pos}


@router.get("/lifecycle/po/{po_id}")
def get_lifecycle(po_id: str) -> LifecycleResponse:
    if not main.edi_rows:
        raise HTTPException(status_code=400, detail="No CSV uploaded")
    idx = _ensure_indexes()
    if not idx:
        raise HTTPException(status_code=400, detail="Indexes not available")
    po_row = idx.po_by_id.get(po_id)
    if po_row is None:
        raise HTTPException(status_code=404, detail="PO not found")
    if po_row.get("transaction_type") != 850:
        raise HTTPException(status_code=400, detail="PO must have transaction_type=850")
    return build_lifecycle_response(idx, po_id)


try:
    from .main import app
    app.include_router(router)
except Exception:
    pass
