"""LangGraph agent network for the Continuous KYC Autonomous Auditor.

Public entry point: ``run_pipeline(event)`` in supervisor.py.

Node execution order:
    monitor → resolver → [dismiss | review_queued | investigator]
                                               → reporter
"""
