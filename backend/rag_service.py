from .ai_explainer import explain_facts
from .intent_router import classify_intent
import re
from datetime import datetime


# =====================================================
# UTILITIES
# =====================================================

def clean_id(text: str) -> str:
    if not text:
        return None
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def parse_date(date_str):
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


# =====================================================
# DATE LOGIC (DETERMINISTIC)
# =====================================================

def is_date_delayed(row):
    expected = parse_date(row.get("expected_date"))
    actual = parse_date(row.get("actual_date"))
    return bool(expected and actual and actual > expected)


def is_date_overdue(row):
    expected = parse_date(row.get("expected_date"))
    actual = parse_date(row.get("actual_date"))
    if row.get("transaction_type") != 810:
        return False
    if not expected or actual:
        return False
    if str(row.get("status", "")).lower() == "paid":
        return False
    return expected < datetime.today().date()


# =====================================================
# MAIN ROUTER
# =====================================================

def answer_question(question: str, rows: list, row_embeddings=None) -> str:
    # 🔴 HARD STOP — NO CSV
    if not rows:
        return "Please upload a CSV file before asking questions."

    # 1. CLASSIFY INTENT
    routing_result = classify_intent(question)
    print("DEBUG routing_result:", routing_result)

    intent = routing_result.get("intent", "UNKNOWN")
    entities = routing_result.get("entities", {})
    
    # Extract entities safely
    doc_id = clean_id(entities.get("document_id"))
    partner = entities.get("partner")
    doc_type = entities.get("document_type")
    
    # ----------------- GET_STATUS -----------------
    if intent == "GET_STATUS":
        if not doc_id:
             return explain_facts("Document ID was not provided.")
             
        match = next((r for r in rows if r["document_id"] == doc_id), None)

        if not match:
            return explain_facts(f"Document {doc_id} does not exist in the uploaded CSV.")

        return explain_facts(
            f"Document {doc_id} has status '{match['status']}' "
            f"and is associated with partner {match['partner']}."
        )

    # ----------------- CHECK_DELAY -----------------
    elif intent == "CHECK_DELAY":
        # If specific document requested
        if doc_id:
             match = next((r for r in rows if r["document_id"] == doc_id), None)
             if not match:
                 return explain_facts(f"Document {doc_id} does not exist in the uploaded CSV.")
                 
             is_delayed_date = is_date_delayed(match)
             is_delayed_status = match["status"] == "delayed"
             
             if is_delayed_date or is_delayed_status:
                 return explain_facts(f"Document {doc_id} is delayed.")
             else:
                 return explain_facts(f"Document {doc_id} is not delayed.")
        
        # General check
        date_delayed = [r["document_id"] for r in rows if is_date_delayed(r)]
        status_delayed = [r["document_id"] for r in rows if r["status"] == "delayed"]

        facts = (
            "Delay check completed using two methods. "
            f"Based on dates, delayed documents: "
            f"{', '.join(date_delayed) or 'None'}. "
            f"Based on status, delayed documents: "
            f"{', '.join(status_delayed) or 'None'}."
        )
        return explain_facts(facts)

    # ----------------- CHECK_OVERDUE -----------------
    elif intent == "CHECK_OVERDUE":
        # If specific document requested
        if doc_id:
            match = next((r for r in rows if r["document_id"] == doc_id), None)
            if not match:
                return explain_facts(f"Document {doc_id} does not exist in the uploaded CSV.")
            
            if match.get("transaction_type") != 810:
                return explain_facts("Overdue applies only to invoices.")
            is_overdue = is_date_overdue(match)
            if is_overdue:
                return explain_facts(f"Document {doc_id} is overdue.")
            else:
                return explain_facts(f"Document {doc_id} is not overdue.")

        # General check
        invoices_overdue = [r["document_id"] for r in rows if is_date_overdue(r)]
        return explain_facts(
            f"Overdue applies only to invoices. The following invoices are overdue: "
            f"{', '.join(invoices_overdue) or 'None'}."
        )

    # ----------------- GET_LIFECYCLE -----------------
    elif intent == "GET_LIFECYCLE":
        if not doc_id:
            return explain_facts("Document ID was not provided.")

        exists_any = any(r["document_id"] == doc_id for r in rows)
        if not exists_any:
            return explain_facts(f"Document {doc_id} does not exist in the uploaded CSV.")
        # PO-only lifecycle
        po_exists = any(r["transaction_type"] == 850 and r["document_id"] == doc_id for r in rows)

        if not po_exists:
            return explain_facts("Lifecycle applies only to Purchase Orders.")

        # 2️⃣ First-hop: PO + directly related docs
        related = [
            r for r in rows
            if r["document_id"] == doc_id
            or r.get("related_document_id") == doc_id
        ]

        # 3️⃣ Collect invoices linked to PO
        invoice_ids = [
            r["document_id"]
            for r in related
            if r["transaction_type"] == 810
        ]

        # 4️⃣ Second-hop: FA linked to invoices
        fa_docs = [
            r for r in rows
            if r["transaction_type"] == 997
            and r.get("related_document_id") in invoice_ids
        ]

        full_lifecycle = related + fa_docs
        full_lifecycle.sort(key=lambda r: r.get("created_date") or "")

        steps = [
            f"{r['document_id']} is {r['status']}"
            for r in full_lifecycle
        ]

        facts = (
            f"The lifecycle of {doc_id} includes the following steps: "
            + "; ".join(steps) + "."
        )
        return explain_facts(facts)

    # ----------------- FILTER_BY_PARTNER -----------------
    elif intent == "FILTER_BY_PARTNER":
        if not partner:
            return explain_facts("Partner was not provided.")
            
        # Case insensitive match
        target_partner = partner.strip().upper()
        partner_exists = any(str(r.get("partner", "")).upper() == target_partner for r in rows)
        if not partner_exists:
            return explain_facts(f"Partner {partner} does not exist in the uploaded CSV.")
        if doc_type:
            type_map = {"PO": 850, "INVOICE": 810, "ASN": 856, "ACK": 855, "FA": 997}
            target_type = type_map.get(doc_type)
        else:
            target_type = None
        filtered = [
            r["document_id"]
            for r in rows
            if str(r.get("partner", "")).upper() == target_partner
            and (target_type is None or r.get("transaction_type") == target_type)
        ]
        if not filtered and target_type is not None:
            return explain_facts(f"No {doc_type} found for partner {partner}.")
        count = len(filtered) if target_type is not None else sum(1 for r in rows if str(r.get("partner", "")).upper() == target_partner)
        display = filtered if target_type is not None else [r["document_id"] for r in rows if str(r.get("partner", "")).upper() == target_partner]
        return explain_facts(
            f"{partner} has {count} {'document(s)' if target_type is None else doc_type}: "
            f"{', '.join(display) or 'None'}."
        )

    # ----------------- CHECK_COMPLETION -----------------
    elif intent == "CHECK_COMPLETION":
        if not doc_id:
             return explain_facts("Document ID was not provided.")

        # PO-only completion
        if doc_id.startswith("INV"):
            return explain_facts("Completion checks apply only to Purchase Orders.")
        po_exists = any(
            r["transaction_type"] == 850 and r["document_id"] == doc_id
            for r in rows
        )

        if not po_exists:
            return explain_facts(f"Document {doc_id} does not exist in the uploaded CSV.")

        related_invoice_ids = [
            r["document_id"]
            for r in rows
            if r["transaction_type"] == 810
            and r.get("related_document_id") == doc_id
        ]

        paid_invoice_present = any(
            r["document_id"] in related_invoice_ids
            and r["status"] == "paid"
            for r in rows
        )

        fa_received = any(
            r["transaction_type"] == 997
            and r.get("related_document_id") in related_invoice_ids
            and r["status"] == "received"
            for r in rows
        )

        return explain_facts(
            f"Completion check for {doc_id}. "
            f"Paid invoice present: {'Yes' if paid_invoice_present else 'No'}. "
            f"Functional acknowledgment received: "
            f"{'Yes' if fa_received else 'No'}."
        )

    # ----------------- LIST_DOCUMENTS -----------------
    elif intent == "LIST_DOCUMENTS":
        # Map document type string to transaction type code
        type_map = {
            "PO": 850,
            "INVOICE": 810,
            "ASN": 856,
            "ACK": 855,
            "FA": 997
        }
        
        target_type = None
        if doc_type and doc_type in type_map:
            target_type = type_map[doc_type]
        
        # Optional status filter (e.g., "what is pending", "what is received")
        status_filter = None
        if isinstance(entities, dict):
            status_filter = str(entities.get("status", "")).strip().lower() or None
        
        # Build filtered list
        def doc_type_label(code):
            for k, v in type_map.items():
                if v == code:
                    return k
            return "UNKNOWN"
        
        filtered_rows = [
            r for r in rows
            if (target_type is None or r.get("transaction_type") == target_type)
            and (status_filter is None or str(r.get("status", "")).lower() == status_filter)
        ]
        
        # If status was requested but no matches
        if status_filter and not filtered_rows:
            return explain_facts(f"No documents with status '{status_filter}' exist in the uploaded CSV.")
        
        # Compose output: include IDs and document type
        items = [f"{r['document_id']} ({doc_type_label(r.get('transaction_type'))})" for r in filtered_rows] if filtered_rows else []
        
        if target_type is not None and not filtered_rows:
            return explain_facts(f"No {doc_type} documents found.")
        
        count = len(items) if items else (sum(1 for _ in rows) if target_type is None and status_filter is None else 0)
        display = items if items else [f"{rid} ({doc_type_label(rc)})" for rid, rc in sorted({(r['document_id'], r.get('transaction_type')) for r in rows})]
        
        # Limit output length
        display_docs = display[:20]
        more_suffix = f" and {len(display) - 20} more" if len(display) > 20 else ""
        
        label_parts = []
        if status_filter:
            label_parts.append(f"status '{status_filter}'")
        if doc_type:
            label_parts.append(doc_type)
        label = " ".join(label_parts) if label_parts else "documents"
        
        return explain_facts(
            f"Found {len(display)} {label}: "
            f"{', '.join(display_docs)}{more_suffix}."
        )

    # ----------------- FALLBACK -----------------
    # Deterministic explanations instead of generic unsupported
    q_lower = str(question).lower()
    if intent == "UNKNOWN":
        # Ambiguous numeric ID
        if doc_id and doc_id.isdigit():
            candidates = sorted(list(set(
                r["document_id"] for r in rows
                if str(r.get("document_id", "")).upper().endswith(doc_id.upper())
            )))
            if len(candidates) >= 2:
                return explain_facts(
                    f"The ID {doc_id} is ambiguous and matches multiple documents "
                    f"({', '.join(candidates)}). Please specify the document type."
                )
        # Explicit non-existent document
        if doc_id:
            exists = any(r["document_id"] == doc_id for r in rows)
            if not exists:
                return explain_facts(f"Document {doc_id} does not exist in the uploaded CSV.")
        # Explicit non-existent partner
        if partner:
            target_partner = partner.strip().upper()
            partner_exists = any(str(r.get("partner", "")).upper() == target_partner for r in rows)
            if not partner_exists:
                return explain_facts(f"Partner {partner} does not exist in the uploaded CSV.")
        # Out-of-scope knowledge questions
        if (("what is" in q_lower or "explain" in q_lower or "define" in q_lower)
            and ("edi" in q_lower or "rag" in q_lower or "asn" in q_lower or "ack" in q_lower or "invoice" in q_lower or "purchase order" in q_lower)):
            return explain_facts("I can answer questions only about the uploaded EDI CSV data. This question is outside my scope.")
        # Meaningless input
        return explain_facts("I couldn’t understand the question. Please ask about the uploaded EDI data.")
    # Missing required entities for known intents
    return explain_facts("I couldn’t understand the question. Please ask about the uploaded EDI data.")
