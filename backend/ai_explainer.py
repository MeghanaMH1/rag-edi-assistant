import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"


def explain_facts(facts: str) -> str:
    """
    AI explanation layer (SAFE MODE).

    - AI is used when available
    - Deterministic results are NEVER blocked
    - Ollama timeout or failure will NOT crash backend
    """

    prompt = f"""
You are a controlled explanation engine.

Rules:
- Use ONLY the information in Facts
- Do NOT add new facts
- Do NOT explain causes
- Do NOT infer meaning
- Keep the explanation short and neutral

Facts:
{facts}

Rewrite the facts in simple sentences.
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=30  # ⬅ shorter, safer timeout
        )

        response.raise_for_status()
        data = response.json()
        explanation = data.get("response")

        if explanation and explanation.strip():
            return explanation.strip()

    except Exception:
        # 🔒 HARD GUARANTEE:
        # Deterministic answers must ALWAYS return
        pass

    # ✅ Deterministic fallback (NO CRASH)
    return facts
