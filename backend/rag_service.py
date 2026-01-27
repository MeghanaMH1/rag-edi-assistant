from .ai_explainer import explain_facts
import re
from datetime import datetime


# =====================================================
# UTILITIES
# =====================================================

def clean_id(text: str) -> str:
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
    if not expected or actual:
        return False
    return expected < datetime.today().date()


# =====================================================
# MAIN ROUTER
# =====================================================

def answer_question(question: str, rows: list, row_embeddings=None) -> str:
    # 🔴 HARD STOP — NO CSV
    if not rows:
        return "No CSV file has been uploaded. Please upload EDI data first."

    q = question.lower().strip()

    # ----------------- NOT DELAYED -----------------
    if "not delayed" in q:
        date_not_delayed = [r["document_id"] for r in rows if not is_date_delayed(r)]
        status_not_delayed = [r["document_id"] for r in rows if r["status"] != "delayed"]

        facts = (
            "Delay check completed using two methods. "
            f"Based on dates, the following documents are not delayed: "
            f"{', '.join(date_not_delayed) or 'None'}. "
            f"Based on status, the following documents are not delayed: "
            f"{', '.join(status_not_delayed) or 'None'}."
        )
        return explain_facts(facts)

    # ----------------- DELAYED -----------------
    if "delayed" in q:
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

    # ----------------- NOT OVERDUE -----------------
    if "not overdue" in q:
        docs = [r["document_id"] for r in rows if not is_date_overdue(r)]
        return explain_facts(
            f"Overdue check completed. The following documents are not overdue: "
            f"{', '.join(docs) or 'None'}."
        )

    # ----------------- OVERDUE -----------------
    if "overdue" in q:
        docs = [r["document_id"] for r in rows if is_date_overdue(r)]
        return explain_facts(
            f"Overdue check completed. The following documents are overdue: "
            f"{', '.join(docs) or 'None'}."
        )

    # ----------------- STATUS OF DOCUMENT -----------------
    if "status of" in q:
        doc_id = clean_id(q.split("status of")[-1])
        match = next((r for r in rows if r["document_id"] == doc_id), None)

        if not match:
            return explain_facts(f"Document {doc_id} does not exist.")

        return explain_facts(
            f"Document {doc_id} has status '{match['status']}' "
            f"and is associated with partner {match['partner']}."
        )

    # ----------------- LIFECYCLE (FIXED) -----------------
    if "lifecycle" in q:
        po_id = clean_id(q.split("lifecycle of")[-1])

        # 1️⃣ PO must exist
        po_exists = any(
            r["transaction_type"] == 850 and r["document_id"] == po_id
            for r in rows
        )

        if not po_exists:
            return explain_facts(f"Purchase Order {po_id} does not exist.")

        # 2️⃣ First-hop: PO + directly related docs
        related = [
            r for r in rows
            if r["document_id"] == po_id
            or r.get("related_document_id") == po_id
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
            f"The lifecycle of {po_id} includes the following steps: "
            + "; ".join(steps) + "."
        )
        return explain_facts(facts)

    # ----------------- PARTNER QUERY -----------------
    if "from" in q or "for" in q:
        partner = clean_id(q.split()[-1])
        docs = [
            r["document_id"]
            for r in rows
            if r["partner"].upper() == partner
        ]

        if not docs:
            return explain_facts(f"Partner {partner} does not exist.")

        return explain_facts(
            f"{partner} is associated with {len(docs)} document(s): "
            f"{', '.join(docs)}."
        )

    # ----------------- STATUS QUERIES -----------------
    for status in ["pending", "accepted", "rejected", "received"]:
        if status in q:
            docs = [r["document_id"] for r in rows if r["status"] == status]
            return explain_facts(
                f"The following documents have status '{status}': "
                f"{', '.join(docs) or 'None'}."
            )

    # ----------------- PO COMPLETION -----------------
    if "complete" in q:
        po_ids = re.findall(r"PO\d+", q.upper())
        if not po_ids:
            return explain_facts(
                "Completion checks apply only to Purchase Orders."
            )

        po_id = po_ids[0]

        po_exists = any(
            r["transaction_type"] == 850 and r["document_id"] == po_id
            for r in rows
        )

        if not po_exists:
            return explain_facts(f"Purchase Order {po_id} does not exist.")

        related_invoice_ids = [
            r["document_id"]
            for r in rows
            if r["transaction_type"] == 810
            and r.get("related_document_id") == po_id
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
            f"Completion check for {po_id}. "
            f"Paid invoice present: {'Yes' if paid_invoice_present else 'No'}. "
            f"Functional acknowledgment received: "
            f"{'Yes' if fa_received else 'No'}."
        )

    # ----------------- FALLBACK -----------------
    return "Unsupported question."
