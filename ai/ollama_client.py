import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"


def generate_response(prompt):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    return response.json()["response"]

def answer_financial_question(question, financial_context):
    prompt = f"""
You are SmartSpend AI, a personal finance assistant.

STRICT RULES:

1. Use ONLY the financial context provided below.
2. Never invent, estimate, assume, or fabricate financial numbers.
3. Treat backend-calculated values as authoritative.
4. Do not perform your own alternative calculations when an exact
   calculated value is already provided in the context.
5. If the requested information is not present in the context,
   clearly say that you do not have enough information.
6. Clearly distinguish predicted/forecasted spending from actual spending.
7. Do not present a forecast as a confirmed future expense.
8. When explaining a change between two months, use the provided
   month totals and category-wise differences.
9. Do not omit relevant categories when explaining a spending change.
10. Keep the answer concise, factual, and easy to understand.
11. Do not give financial data that is not present in the context.

FINANCIAL CONTEXT:
{financial_context}

USER QUESTION:
{question}

ANSWER:
"""

    return generate_response(prompt)