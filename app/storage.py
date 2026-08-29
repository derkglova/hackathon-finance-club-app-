"""In-memory data store. Swap for real database calls later."""

budgets = []
requests = []

_budget_id = 0
_request_id = 0


def next_budget_id():
    global _budget_id
    _budget_id += 1
    return f"b{_budget_id}"


def next_request_id():
    global _request_id
    _request_id += 1
    return _request_id
