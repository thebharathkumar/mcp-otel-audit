"""Tool function bodies shared across all four target stacks.

Anything that differs between stacks lives in the per-target server.py wiring
(which framework, which instrumentation, transport setup). The behavior of the
three tools themselves must be byte-identical, so this file is imported by
every target.
"""

from __future__ import annotations


def echo(text: str) -> str:
    return text


_MOCK_DATA = {
    "alpha": "first item",
    "beta": "second item",
    "gamma": "third item",
}


def fetch_mock_data(key: str) -> str:
    if key not in _MOCK_DATA:
        raise KeyError(f"unknown key: {key}")
    return _MOCK_DATA[key]


def calculate(op: str, a: float, b: float) -> float:
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "mul":
        return a * b
    if op == "div":
        return a / b
    raise ValueError(f"unknown op: {op}")
