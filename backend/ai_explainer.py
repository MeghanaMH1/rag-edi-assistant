import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"


def explain_facts(facts: str) -> str:
    """
    AI explanation layer (STRICT + SAFE MODE).

    GUARANTEES:
    - AI NEVER decides logic
    - AI NEVER adds facts
    - AI NEVER explains business meaning
    - AI NEVER blocks deterministic output
    """

    # 🚨 EARLY EXIT FOR SYSTEM MESSAGES (NO AI CALL)
    if not facts:
        return facts

    lower_facts = facts.lower().strip()
    if (
        lower_facts.startswith("no csv")
        or lower_facts.startswith("unsupported")
        or lower_facts.startswith("no edi data")
    ):
        return facts

    # -----------------------------
    # AI PROMPT (ONLY FOR REAL DATA)
    # -----------------------------
    prompt = f"""
You are a STRICT explanation engine for a deterministic EDI system.

NON-NEGOTIABLE RULES:
- Use ONLY the information explicitly present in the Facts section
- Do NOT add new facts, documents, or interpretations
- Do NOT explain what transaction types mean
- Do NOT describe business processes
- Do NOT explain causes, impacts, or reasons
- Do NOT infer relationships beyond what is stated
- Do NOT introduce domain knowledge
- Do NOT speculate or summarize beyond the facts
- Do NOT expand, rename, or interpret document IDs or transaction types
- Always use document IDs exactly as provided (e.g., PO1001, FA1001)


ALLOWED:
- Rephrase facts for clarity
- Group similar results
- State counts (none / one / multiple)
- Use short, neutral sentences

STYLE REQUIREMENTS:
- Professional
- Concise
- Neutral
- Maximum 3–5 sentences
- No bullet-point spam
- No field-label repetition unless necessary

Facts:
{facts}

Task:
Rewrite the above facts into a clear, neutral explanation.
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            },
            timeout=20
        )

        response.raise_for_status()
        data = response.json()
        explanation = data.get("response")

        if explanation and explanation.strip():
            return explanation.strip()

    except Exception:
        # 🔒 AI failure must NEVER block deterministic output
        pass

    # ✅ FINAL SAFETY FALLBACK
    return facts
