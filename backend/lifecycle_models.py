from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel

# ------------------------------------------------------------
# Lifecycle Trace Visualizer — Data Models (Schemas only)
# Deterministic, CSV-only sourcing. No business logic here.
# ------------------------------------------------------------


class EventType(str, Enum):
    # Event type labels used across the lifecycle diagram
    PO = "PO"     # transaction_type = 850
    ACK = "ACK"   # transaction_type = 855
    ASN = "ASN"   # transaction_type = 856
    INV = "INV"   # transaction_type = 810
    FA = "FA"     # transaction_type = 997


class Evidence(BaseModel):
    # Traceability to the exact CSV source for a node
    csv_row_index: Optional[int] = None
    source_fields: Optional[Dict[str, Any]] = None  # raw fields from the CSV row (as-is)


class LifecycleEvent(BaseModel):
    # One node in the lifecycle diagram
    event_type: EventType
    document_id: Optional[str] = None
    related_document_id: Optional[str] = None
    status: Optional[str] = None
    event_date: Optional[str] = None      # ISO string or original CSV date string
    partner: Optional[str] = None
    evidence: Optional[Evidence] = None   # None when the step is missing


class CompletenessFlags(BaseModel):
    # Presence/absence of each lifecycle step for the selected PO
    has_po: bool = False
    has_ack: bool = False
    has_asn: bool = False
    has_inv: bool = False
    has_fa: bool = False


class POListItem(BaseModel):
    # Minimal fields used to populate the PO dropdown
    document_id: str               # PO ID (transaction_type=850)
    partner: Optional[str] = None
    status: Optional[str] = None
    po_date: Optional[str] = None  # expected_date presented as PO date


class LifecycleResponse(BaseModel):
    # Response payload for lifecycle/po/:po_id
    po_id: str
    events: list[LifecycleEvent]
    completeness: CompletenessFlags
