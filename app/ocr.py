import json
import os
import re
import requests

GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

CATEGORIES = {"Food & Drinks", "Supplies", "Printing", "Travel", "Equipment", "Other"}
DOCUMENT_TYPES = {"receipt", "quote"}

PROMPT = (
    'Extract details from this receipt or quote. Respond with ONLY minified JSON, no markdown, '
    'matching exactly this shape: {"merchant":string,"amount":number,"date":"YYYY-MM-DD",'
    '"category":"Food & Drinks"|"Supplies"|"Printing"|"Travel"|"Equipment"|"Other",'
    '"documentType":"receipt"|"quote","lineItems":[{"description":string,"cost":number}]}. '
    'Pick the category that best fits. For documentType, use "quote" if this is a quotation, '
    'estimate, proforma or proposal for money not yet paid; use "receipt" if it is a receipt, '
    'tax invoice, bill or any proof of a completed payment. '
    'If a field is illegible or missing, use "" / 0 / [].'
)


class OcrError(Exception):
    pass


def parse_receipt(media_type, data_b64):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise OcrError("GEMINI_API_KEY is not configured on the server")

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": media_type, "data": data_b64}},
                {"text": PROMPT},
            ],
        }],
        "generationConfig": {"maxOutputTokens": 8192, "thinkingConfig": {"thinkingLevel": "low"}},
    }

    try:
        resp = requests.post(GEMINI_URL, params={"key": api_key}, json=payload, timeout=30)
    except requests.RequestException as e:
        raise OcrError(f"could not reach Gemini: {e}")

    if not resp.ok:
        raise OcrError(f"Gemini request failed ({resp.status_code}): {resp.text[:300]}")

    body = resp.json()
    try:
        candidate = body["candidates"][0]
        raw_text = candidate["content"]["parts"][0]["text"]
    except (KeyError, IndexError, ValueError):
        finish_reason = body.get("candidates", [{}])[0].get("finishReason", "unknown")
        raise OcrError(f"Gemini returned no usable text (finishReason: {finish_reason})")

    cleaned = re.sub(r"^```(json)?", "", raw_text.strip(), flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise OcrError("could not parse JSON from Gemini response")

    category = data.get("category")
    if category not in CATEGORIES:
        category = "Other"

    amount = data.get("amount")
    if not isinstance(amount, (int, float)):
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = 0

    line_items = data.get("lineItems")
    if not isinstance(line_items, list):
        line_items = []

    document_type = data.get("documentType")
    if document_type not in DOCUMENT_TYPES:
        document_type = "receipt"

    return {
        "merchant": data.get("merchant") or "",
        "amount": amount,
        "date": data.get("date") or "",
        "category": category,
        "documentType": document_type,
        "lineItems": line_items,
    }
