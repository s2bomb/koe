from __future__ import annotations

from typing import assert_type

from koe.types import InsertionError, Result


def t01_insert_result_narrowing(result: Result[None, InsertionError]) -> None:
    if result["ok"] is True:
        assert_type(result["value"], None)
    else:
        assert_type(result["error"], InsertionError)
