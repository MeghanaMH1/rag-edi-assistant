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
# FACT FORMATTER (STRICT & SAFE)
# =====================================================

def format_documents(rows):
    if not rows:
        return "None"

    lines = []
    for r in rows:
        lines.append(
            f"- Document ID: {r['document_id']} | "
            f"Transaction Type: {r['transaction_type']} | "
            f"Status: {r['status']} | "
            f"Partner: {r['partner']}"
        )
    return "\n".join(lines)


# =====================================================
# MAIN ROUTER
# =====================================================

def answer_question(question: str, rows: list, row_embeddings=None) -> str:
    if not rows:
        return explain_facts("No EDI data available.")

    q = question.lower().strip()

    # =================================================
    # 1️⃣ NOT DELAYED (CHECK FIRST)
    # =================================================
    if "not delayed" in q:
        date_not_delayed = [r for r in rows if not is_date_delayed(r)]
        status_not_delayed = [r for r in rows if r.get("status") != "delayed"]

        facts = f"""
Not delayed analysis.

DATE-BASED not delayed documents:
{format_documents(date_not_delayed)}

STATUS-BASED not delayed documents:
{format_documents(status_not_delayed)}
"""
        return explain_facts(facts.strip())

    # =================================================
    # 2️⃣ DELAYED
    # =================================================
    if "delayed" in q:
        date_delayed = [r for r in rows if is_date_delayed(r)]
        status_delayed = [r for r in rows if r.get("status") == "delayed"]

        facts = f"""
Delayed analysis.

DATE-BASED delayed documents:
{format_documents(date_delayed)}

STATUS-BASED delayed documents:
{format_documents(status_delayed)}
"""
        return explain_facts(facts.strip())

    # =================================================
    # 3️⃣ NOT OVERDUE (CHECK FIRST)
    # =================================================
    if "not overdue" in q:
        not_overdue = [r for r in rows if not is_date_overdue(r)]

        facts = f"""
Not overdue analysis.

Documents that are not overdue:
{format_documents(not_overdue)}
"""
        return explain_facts(facts.strip())

    # =================================================
    # 4️⃣ OVERDUE
    # =================================================
    if "overdue" in q:
        overdue = [r for r in rows if is_date_overdue(r)]

        facts = f"""
Overdue analysis.

Overdue documents:
{format_documents(overdue)}
"""
        return explain_facts(facts.strip())

    # =================================================
    # 5️⃣ DOCUMENT STATUS
    # =================================================
    if "status of" in q:
        doc_id = clean_id(q.split("status of")[-1])
        match = next((r for r in rows if r.get("document_id") == doc_id), None)

        if not match:
            return explain_facts(f"Document {doc_id} does not exist.")

        facts = f"""
Document details.

Document ID: {match['document_id']}
Transaction Type: {match['transaction_type']}
Status: {match['status']}
Partner: {match['partner']}
Remarks: {match.get('remarks', 'N/A')}
"""
        return explain_facts(facts.strip())

    # =================================================
    # 6️⃣ LIFECYCLE (PO ONLY)
    # =================================================
    if "lifecycle" in q:
        po_id = clean_id(q.split("lifecycle of")[-1])

        po_exists = any(
            r.get("transaction_type") == 850 and r.get("document_id") == po_id
            for r in rows
        )

        if not po_exists:
            return explain_facts(f"Purchase Order {po_id} does not exist.")

        related = [
            r for r in rows
            if r.get("document_id") == po_id or r.get("related_document_id") == po_id
        ]

        related.sort(key=lambda r: r.get("created_date") or "")

        facts = f"""
Lifecycle for Purchase Order {po_id}.

{format_documents(related)}
"""
        return explain_facts(facts.strip())

    # =================================================
    # 7️⃣ PARTNER QUERY
    # =================================================
    if "from" in q or "for" in q:
        partner = clean_id(q.split()[-1])
        matches = [r for r in rows if r.get("partner", "").upper() == partner]

        if not matches:
            return explain_facts(f"Partner {partner} does not exist.")

        facts = f"""
Partner query result.

Partner: {partner}
Associated documents:
{format_documents(matches)}
"""
        return explain_facts(facts.strip())

    # =================================================
    # 8️⃣ STATUS-BASED QUERIES
    # =================================================
    for status in ["pending", "accepted", "rejected", "received"]:
        if status in q:
            matches = [r for r in rows if r.get("status") == status]

            facts = f"""
Status query result.

Status: {status}
Matching documents:
{format_documents(matches)}
"""
            return explain_facts(facts.strip())

    # =================================================
    # 9️⃣ PO COMPLETION
    # =================================================
    if "complete" in q:
        po_ids = re.findall(r"PO\d+", q.upper())
        if not po_ids:
            return explain_facts("Completion checks apply only to Purchase Orders.")

        po_id = po_ids[0]

        po_exists = any(
            r.get("transaction_type") == 850 and r.get("document_id") == po_id
            for r in rows
        )

        if not po_exists:
            return explain_facts(f"Purchase Order {po_id} does not exist.")

        invoices = [
            r for r in rows
            if r.get("transaction_type") == 810
            and r.get("related_document_id") == po_id
            and r.get("status") == "paid"
        ]

        fa_received = any(
            r.get("transaction_type") == 997
            and r.get("related_document_id") in [i["document_id"] for i in invoices]
            and r.get("status") == "received"
            for r in rows
        )

        facts = f"""
Completion check for Purchase Order {po_id}.

Paid invoices present: {"Yes" if invoices else "No"}
Functional acknowledgment received: {"Yes" if fa_received else "No"}
"""
        return explain_facts(facts.strip())

    return explain_facts("Unsupported question.")
