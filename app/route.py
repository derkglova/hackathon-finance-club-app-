from flask import Blueprint, jsonify, request

import storage

bp = Blueprint("api", __name__, url_prefix="/api")

CATEGORIES = {"Food & Drinks", "Supplies", "Printing", "Travel", "Equipment", "Other"}
STATUSES = {"pending", "approved", "rejected"}


# ---- Budgets ----

@bp.get("/budgets")
def list_budgets():
    return jsonify(storage.budgets)


@bp.post("/budgets")
def create_budget():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    allocated = data.get("allocated")

    if not name:
        return jsonify(error="name is required"), 400
    try:
        allocated = float(allocated)
    except (TypeError, ValueError):
        return jsonify(error="allocated must be a number"), 400
    if allocated <= 0:
        return jsonify(error="allocated must be greater than 0"), 400

    budget = {"id": storage.next_budget_id(), "name": name, "allocated": allocated}
    storage.budgets.append(budget)
    return jsonify(budget), 201


# ---- Requests ----

@bp.get("/requests")
def list_requests():
    status = request.args.get("status")
    items = storage.requests
    if status:
        if status not in STATUSES:
            return jsonify(error=f"status must be one of {sorted(STATUSES)}"), 400
        items = [r for r in items if r["status"] == status]
    return jsonify(items)


@bp.get("/requests/<int:request_id>")
def get_request(request_id):
    req = next((r for r in storage.requests if r["id"] == request_id), None)
    if not req:
        return jsonify(error="request not found"), 404
    return jsonify(req)


@bp.post("/requests")
def create_request():
    data = request.get_json(silent=True) or {}

    merchant = (data.get("merchant") or "").strip()
    amount = data.get("amount")
    date = (data.get("date") or "").strip()
    category = data.get("category") or "Other"
    budget_id = data.get("budgetId") or ""

    if not merchant:
        return jsonify(error="merchant is required"), 400
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify(error="amount must be a number"), 400
    if not budget_id:
        return jsonify(error="budgetId is required"), 400
    if category not in CATEGORIES:
        return jsonify(error=f"category must be one of {sorted(CATEGORIES)}"), 400
    if not any(b["id"] == budget_id for b in storage.budgets):
        return jsonify(error="budgetId does not match an existing budget"), 400

    new_request = {
        "id": storage.next_request_id(),
        "memberId": data.get("memberId") or "me",
        "merchant": merchant,
        "amount": amount,
        "date": date,
        "category": category,
        "budgetId": budget_id,
        "note": data.get("note") or "",
        "status": "pending",
        "comment": "",
        "previewUrl": data.get("previewUrl"),
        "fileType": data.get("fileType"),
    }
    storage.requests.insert(0, new_request)
    return jsonify(new_request), 201


@bp.patch("/requests/<int:request_id>")
def update_request(request_id):
    req = next((r for r in storage.requests if r["id"] == request_id), None)
    if not req:
        return jsonify(error="request not found"), 404

    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status is not None:
        if status not in STATUSES:
            return jsonify(error=f"status must be one of {sorted(STATUSES)}"), 400
        req["status"] = status
    if "comment" in data:
        req["comment"] = data.get("comment") or ""

    return jsonify(req)


# ---- Receipt OCR ----

@bp.post("/receipts/parse")
def parse_receipt():
    # Placeholder until this is wired to a real OCR/LLM provider (e.g. Anthropic API with a base64 image/PDF).
    return jsonify(error="receipt parsing is not implemented yet"), 501
