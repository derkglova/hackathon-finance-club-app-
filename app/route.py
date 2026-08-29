from flask import Blueprint, jsonify, request

import storage
from ocr import OcrError, parse_receipt

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

    budget = {"id": storage.next_budget_id(), "name": name, "allocated": allocated, "subsections": []}
    storage.budgets.append(budget)
    return jsonify(budget), 201


@bp.patch("/budgets/<budget_id>")
def update_budget(budget_id):
    budget = next((b for b in storage.budgets if b["id"] == budget_id), None)
    if not budget:
        return jsonify(error="budget not found"), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify(error="name is required"), 400
        budget["name"] = name
    if "allocated" in data:
        try:
            allocated = float(data.get("allocated"))
        except (TypeError, ValueError):
            return jsonify(error="allocated must be a number"), 400
        if allocated <= 0:
            return jsonify(error="allocated must be greater than 0"), 400
        budget["allocated"] = allocated

    return jsonify(budget)


@bp.delete("/budgets/<budget_id>")
def delete_budget(budget_id):
    budget = next((b for b in storage.budgets if b["id"] == budget_id), None)
    if not budget:
        return jsonify(error="budget not found"), 404

    storage.requests[:] = [r for r in storage.requests if r["budgetId"] != budget_id]
    storage.budgets.remove(budget)
    return "", 204


# ---- Budget subsections ----

@bp.post("/budgets/<budget_id>/subsections")
def create_subsection(budget_id):
    budget = next((b for b in storage.budgets if b["id"] == budget_id), None)
    if not budget:
        return jsonify(error="budget not found"), 404

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

    subsection = {"id": storage.next_subsection_id(), "name": name, "allocated": allocated}
    budget.setdefault("subsections", []).append(subsection)
    return jsonify(subsection), 201


@bp.patch("/budgets/<budget_id>/subsections/<sub_id>")
def update_subsection(budget_id, sub_id):
    budget = next((b for b in storage.budgets if b["id"] == budget_id), None)
    if not budget:
        return jsonify(error="budget not found"), 404
    sub = next((x for x in budget.get("subsections", []) if x["id"] == sub_id), None)
    if not sub:
        return jsonify(error="subsection not found"), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify(error="name is required"), 400
        sub["name"] = name
    if "allocated" in data:
        try:
            allocated = float(data.get("allocated"))
        except (TypeError, ValueError):
            return jsonify(error="allocated must be a number"), 400
        if allocated <= 0:
            return jsonify(error="allocated must be greater than 0"), 400
        sub["allocated"] = allocated

    return jsonify(sub)


@bp.delete("/budgets/<budget_id>/subsections/<sub_id>")
def delete_subsection(budget_id, sub_id):
    budget = next((b for b in storage.budgets if b["id"] == budget_id), None)
    if not budget:
        return jsonify(error="budget not found"), 404
    subsections = budget.get("subsections", [])
    sub = next((x for x in subsections if x["id"] == sub_id), None)
    if not sub:
        return jsonify(error="subsection not found"), 404

    linked = [r for r in storage.requests if r.get("subsectionId") == sub_id]
    if linked:
        return jsonify(error=f"can't delete — {len(linked)} request(s) are tagged to this subsection"), 400

    subsections.remove(sub)
    return "", 204


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
    subsection_id = data.get("subsectionId") or ""
    member_name = (data.get("memberName") or "").strip()

    if not merchant:
        return jsonify(error="merchant is required"), 400
    if not member_name:
        return jsonify(error="memberName is required"), 400
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify(error="amount must be a number"), 400
    if not budget_id:
        return jsonify(error="budgetId is required"), 400
    if category not in CATEGORIES:
        return jsonify(error=f"category must be one of {sorted(CATEGORIES)}"), 400
    budget = next((b for b in storage.budgets if b["id"] == budget_id), None)
    if not budget:
        return jsonify(error="budgetId does not match an existing budget"), 400
    if subsection_id and not any(sub["id"] == subsection_id for sub in budget.get("subsections", [])):
        return jsonify(error="subsectionId does not match an existing subsection for this budget"), 400

    new_request = {
        "id": storage.next_request_id(),
        "memberId": data.get("memberId") or "me",
        "memberName": member_name,
        "merchant": merchant,
        "amount": amount,
        "date": date,
        "category": category,
        "budgetId": budget_id,
        "subsectionId": subsection_id,
        "note": data.get("note") or "",
        "status": "pending",
        "comment": "",
        "paid": False,
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
    if "paid" in data:
        paid = data.get("paid")
        if not isinstance(paid, bool):
            return jsonify(error="paid must be a boolean"), 400
        req["paid"] = paid

    return jsonify(req)


@bp.delete("/requests/<int:request_id>")
def delete_request(request_id):
    req = next((r for r in storage.requests if r["id"] == request_id), None)
    if not req:
        return jsonify(error="request not found"), 404

    storage.requests.remove(req)
    return "", 204


# ---- Receipt OCR ----

@bp.post("/receipts/parse")
def parse_receipt_route():
    data = request.get_json(silent=True) or {}
    media_type = data.get("media_type")
    b64 = data.get("data")

    if not media_type or not b64:
        return jsonify(error="media_type and data are required"), 400

    try:
        result = parse_receipt(media_type, b64)
    except OcrError as e:
        return jsonify(error=str(e)), 502

    return jsonify(result)
