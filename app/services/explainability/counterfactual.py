def generate_counterfactual(dismiss_reason: str, values: dict) -> str:
    # Example logic
    if dismiss_reason == "low_confidence":
        actual = values.get("confidence", 0)
        return f"Dismissed at confidence {actual}. Would have proceeded if source credibility ≥ 0.7 or fuzzy match ≥ 80."
    return "Dismissed due to manual rule."