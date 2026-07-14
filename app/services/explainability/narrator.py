def narrate_scoring(values: dict) -> str:
    # TODO: Sync with Dev 1 for exact keys
    event_type = values.get("event_type", "unknown")
    weight = values.get("weight", 0)
    severity = values.get("severity", 1.0)
    jurisdiction = values.get("jurisdiction", 1.0)
    delta = values.get("delta", 0)
    return f"{event_type} (weight {weight}) × severity {severity} × jurisdiction {jurisdiction} = +{delta}"

def narrate_detector(values: dict) -> str:
    # TODO: Sync with Dev 4 for exact keys
    n = values.get("n", 0)
    amt = values.get("approx_amount", 0)
    window = values.get("window_hours", 0)
    return f"structuring: {n} transactions of ~₹{amt} within {window}h."