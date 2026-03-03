"""Timezone compliance: no bare datetime.now() in src/pib/."""

import ast
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "src" / "pib"


def test_no_bare_datetime_now():
    """AST-based scan: no bare datetime.now() or datetime.utcnow() in source."""
    violations = []
    for py_file in SRC_DIR.glob("*.py"):
        source = py_file.read_text()
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Check for datetime.now() with no args
                if (isinstance(func, ast.Attribute) and func.attr == "now"
                        and isinstance(func.value, ast.Name) and func.value.id == "datetime"
                        and len(node.args) == 0 and len(node.keywords) == 0):
                    violations.append(f"{py_file.name}:{node.lineno} — bare datetime.now()")
                # Check for datetime.utcnow()
                if (isinstance(func, ast.Attribute) and func.attr == "utcnow"
                        and isinstance(func.value, ast.Name) and func.value.id == "datetime"):
                    violations.append(f"{py_file.name}:{node.lineno} — datetime.utcnow()")

    assert not violations, f"Bare datetime calls found:\n" + "\n".join(violations)


def test_tz_module_exports():
    """Verify tz.py exports the expected symbols."""
    from pib.tz import HOUSEHOLD_TZ, now_et
    from datetime import datetime

    assert str(HOUSEHOLD_TZ) == "America/New_York"
    result = now_et()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None
