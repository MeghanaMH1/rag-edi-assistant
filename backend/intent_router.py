import json
import re
import numpy as np
from collections import OrderedDict
from threading import Lock
from sentence_transformers import SentenceTransformer

CACHE_SIZE = 500
_intent_cache = OrderedDict()
_cache_lock = Lock()

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.75
_embed_model = None
_model_lock = Lock()
_partner_whitelist = set()
_partner_lock = Lock()
_exemplars_lock = Lock()
_exemplars_ready = False

_exemplars = {
    "GET_STATUS": [
        "what's the status of PO1001",
        "how is invoice 245 doing",
        "status update for order 500",
        "current state of PO2003",
        "invoice 88 status",
    ],
    "CHECK_DELAY": [
        "is PO1001 delayed",
        "any late purchase orders",
        "are there delays for Target orders",
        "is invoice 245 running late",
        "show delayed items",
    ],
    "CHECK_OVERDUE": [
        "is invoice 555 overdue",
        "which invoices are past due",
        "overdue documents please",
        "any overdue payments",
        "list overdue items",
    ],
    "GET_LIFECYCLE": [
        "lifecycle of PO1001",
        "show history for order 500",
        "document timeline for invoice 245",
        "what happened to PO2003",
        "full activity for PO1001",
    ],
    "FILTER_BY_PARTNER": [
        "show documents from Amazon",
        "list Target orders",
        "Walmart invoices only",
        "any ASNs from Costco",
        "documents for Home Depot",
    ],
    "CHECK_COMPLETION": [
        "is PO1001 complete",
        "has order 500 finished",
        "is invoice 245 fully processed",
        "did PO2003 close",
        "is the order done",
    ],
    "LIST_DOCUMENTS": [
        "show all POs",
        "list all invoices",
        "all documents",
        "display ASNs",
        "what documents exist",
    ],
}

_exemplar_embeddings = {}

def _load_model():
    global _embed_model
    with _model_lock:
        if _embed_model is None:
            _embed_model = SentenceTransformer(MODEL_NAME)

def _ensure_exemplar_embeddings():
    global _exemplars_ready
    with _exemplars_lock:
        if _exemplars_ready:
            return
        _load_model()
        for intent, samples in _exemplars.items():
            vecs = _embed_model.encode(samples, convert_to_numpy=True, normalize_embeddings=True)
            _exemplar_embeddings[intent] = vecs
        _exemplars_ready = True

def _cosine_max(intent_vectors, query_vec):
    if intent_vectors is None or len(intent_vectors) == 0:
        return 0.0
    scores = intent_vectors @ query_vec
    return float(np.max(scores))

def _extract_document_id(text):
    m = re.search(r"\b(?:PO|INV|ASN)\d+\b", text, flags=re.IGNORECASE)
    if m:
        return re.sub(r"[^A-Za-z0-9]", "", m.group(0)).upper()
    m2 = re.search(r"\b\d{3,}\b", text)
    if m2:
        return m2.group(0).upper()
    return None

def _extract_document_type(text):
    t = None
    s = text.lower()
    if "purchase order" in s or "purchase orders" in s or "pos" in s or " po " in s or s.startswith("po ") or s.endswith(" po"):
        t = "PO"
    elif "invoices" in s or "invoice" in s:
        t = "INVOICE"
    elif "asns" in s or "asn" in s or " asn " in s or s.startswith("asn ") or s.endswith(" asn"):
        t = "ASN"
    elif "acks" in s or "ack" in s or " ack " in s or s.startswith("ack ") or s.endswith(" ack"):
        t = "ACK"
    elif "fas" in s or " fa " in s or s.startswith("fa ") or s.endswith(" fa"):
        t = "FA"
    return t

def _extract_partner(text):
    m = re.search(r"\bfrom\s+([A-Za-z][A-Za-z&\-\s]+)\b", text)
    if not m:
        return None
    # Return the verbatim extracted partner string; existence will be validated downstream
    return m.group(1).strip()

def _ensure_partner_whitelist():
    with _partner_lock:
        if _partner_whitelist:
            return
    try:
        # Import inside the function to avoid circular import at module load
        from .main import edi_rows
        candidates = set()
        for r in edi_rows or []:
            val = str(r.get("partner", "")).strip()
            if val:
                candidates.add(val.lower())
        with _partner_lock:
            _partner_whitelist.update(candidates)
    except Exception:
        pass

def _is_csv_loaded():
    try:
        from .main import edi_rows
        return bool(edi_rows)
    except Exception:
        return False

def classify_intent(question: str) -> dict:
    try:
        normalized_key = question.strip().lower()
        with _cache_lock:
            if normalized_key in _intent_cache:
                _intent_cache.move_to_end(normalized_key)
                return _intent_cache[normalized_key]

        if not _is_csv_loaded():
            return {
                "intent": "UNKNOWN",
                "entities": {
                    "document_id": None,
                    "partner": None,
                    "document_type": None,
                },
            }

        _ensure_exemplar_embeddings()
        if not _exemplars_ready:
            return {
                "intent": "UNKNOWN",
                "entities": {
                    "document_id": None,
                    "partner": None,
                    "document_type": None,
                },
            }

        q_vec = _embed_model.encode([question], convert_to_numpy=True, normalize_embeddings=True)[0]
        best_intent = "UNKNOWN"
        best_score = -1.0
        for intent, vecs in _exemplar_embeddings.items():
            score = _cosine_max(vecs, q_vec)
            if score > best_score:
                best_score = score
                best_intent = intent
        if best_score < SIMILARITY_THRESHOLD:
            best_intent = "UNKNOWN"

        entities = {
            "document_id": _extract_document_id(question),
            "partner": _extract_partner(question),
            "document_type": _extract_document_type(question),
        }

        # Deterministic status-based listing: "what is pending", "what is received"
        s_lower = question.lower()
        if best_intent == "UNKNOWN" and entities["document_id"] is None:
            if re.search(r"\bpending\b", s_lower):
                best_intent = "LIST_DOCUMENTS"
                entities["status"] = "pending"
            elif re.search(r"\breceived\b", s_lower):
                best_intent = "LIST_DOCUMENTS"
                entities["status"] = "received"

        # Deterministic override for purchase orders listing
        if best_intent == "UNKNOWN" and entities["document_type"] == "PO":
            s = question.lower()
            if ("purchase order" in s) or ("purchase orders" in s) or (" pos" in s) or (" po" in s) or s.startswith("po ") or s.endswith(" po"):
                best_intent = "LIST_DOCUMENTS"
        # Deterministic overrides for ASN / ACK / FA listing
        if best_intent == "UNKNOWN" and entities["document_type"] in {"ASN", "ACK", "FA"}:
            best_intent = "LIST_DOCUMENTS"
        # Deterministic override for lifecycle/history synonyms
        if best_intent == "UNKNOWN":
            s = question.lower()
            has_lifecycle_phrase = any(p in s for p in ["lifecycle", "life cycle", "history", "timeline", "full activity"])
            if has_lifecycle_phrase and entities["document_id"]:
                best_intent = "GET_LIFECYCLE"
        # Deterministic override for generic delay queries
        if best_intent == "UNKNOWN":
            s = question.lower()
            if any(p in s for p in ["delay", "delays", "delayed"]):
                best_intent = "CHECK_DELAY"
        # Ambiguous numeric-only ID: require explicit type clarification
        try:
            if best_intent == "GET_STATUS" and entities["document_id"] and entities["document_id"].isdigit():
                from .main import edi_rows
                base = entities["document_id"]
                candidates = [f"{p}{base}" for p in ["PO", "INV", "ASN", "ACK", "FA"]]
                exist = {c for c in candidates if any(r.get("document_id") == c for r in (edi_rows or []))}
                if len(exist) >= 2:
                    best_intent = "UNKNOWN"
        except Exception:
            pass

        allowed_intents = {
            "GET_STATUS",
            "CHECK_DELAY",
            "CHECK_OVERDUE",
            "GET_LIFECYCLE",
            "FILTER_BY_PARTNER",
            "CHECK_COMPLETION",
            "LIST_DOCUMENTS",
            "UNKNOWN",
        }
        if best_intent not in allowed_intents:
            best_intent = "UNKNOWN"

        allowed_types = {"PO", "INVOICE", "ASN", "ACK", "FA"}
        dt = entities["document_type"]
        if isinstance(dt, str):
            dt = dt.upper()
            if dt not in allowed_types:
                dt = None
        else:
            dt = None
        entities["document_type"] = dt

        parsed = {"intent": best_intent, "entities": entities}
        with _cache_lock:
            if len(_intent_cache) >= CACHE_SIZE:
                _intent_cache.popitem(last=False)
            _intent_cache[normalized_key] = parsed
        return parsed
    except Exception:
        return {
            "intent": "UNKNOWN",
            "entities": {
                "document_id": None,
                "partner": None,
                "document_type": None,
            },
        }

if __name__ == "__main__":
    import time
    qs = [
        "What is the status of PO1001?",
        "show all POs",
        "documents from Amazon",
    ]
    for q in qs:
        t0 = time.time()
        r = classify_intent(q)
        print(q, f"{time.time()-t0:.4f}s", r)
    for q in qs:
        t0 = time.time()
        r = classify_intent(q)
        print("cache", q, f"{time.time()-t0:.4f}s")
