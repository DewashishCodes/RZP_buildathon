"""Architecture invariants that must never regress.

The hidden recoverability model (app/simulation/recoverability.py) is the
ground truth the execution layer rolls against - detection and policy must
reason WITHOUT it or the whole "can the agent recover money it can't see
the odds of" claim collapses. Until now that boundary was enforced only by
a comment; this test makes importing it from the wrong layer fail CI.
"""
import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
GUARDED_PACKAGES = ["app/detection", "app/policy"]
FORBIDDEN_MODULE = "recoverability"


def _imports_recoverability(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(FORBIDDEN_MODULE in alias.name for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and FORBIDDEN_MODULE in node.module:
                return True
            # relative imports: from ..simulation.recoverability import ...
            if any(FORBIDDEN_MODULE in (alias.name or "") for alias in node.names):
                return True
    return False


def test_detection_and_policy_never_import_the_recoverability_model():
    offenders = []
    for package in GUARDED_PACKAGES:
        for path in (BACKEND_ROOT / package).rglob("*.py"):
            if _imports_recoverability(path):
                offenders.append(str(path.relative_to(BACKEND_ROOT)))
    assert offenders == [], (
        f"Guardrail violation - these modules import the hidden recoverability "
        f"model they must never see: {offenders}"
    )


def test_only_execution_layer_rolls_against_recoverability():
    importors = []
    for path in (BACKEND_ROOT / "app").rglob("*.py"):
        if _imports_recoverability(path):
            importors.append(path.relative_to(BACKEND_ROOT).as_posix())
    assert importors == ["app/execution/connectors.py"], (
        f"recoverability should be imported by exactly the execution connector, found: {importors}"
    )
