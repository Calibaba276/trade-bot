"""Strategy runner entry points.

Each runner is launched directly as a module (``python -m backend.runners.eurusd``)
by the orchestrator, so this package intentionally performs no eager imports —
importing one runner must not drag in the others (or their heavy dependencies),
and removing a retired runner must not break the package.
"""
