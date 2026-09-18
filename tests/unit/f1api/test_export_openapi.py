from __future__ import annotations

import json
from pathlib import Path

from f1api.export_openapi import main


def test_writes_a_valid_openapi_document(tmp_path: Path) -> None:
    output_path = tmp_path / "openapi.json"

    exit_code = main(["export_openapi", str(output_path)])

    assert exit_code == 0
    schema = json.loads(output_path.read_text())
    assert "/sessions" in schema["paths"]
    assert "/circuits/{circuit_id}/geometry" in schema["paths"]
    assert "SessionOut" in schema["components"]["schemas"]


def test_prints_usage_and_returns_2_with_wrong_args(capsys) -> None:
    exit_code = main(["export_openapi"])

    assert exit_code == 2
    assert "usage" in capsys.readouterr().err
