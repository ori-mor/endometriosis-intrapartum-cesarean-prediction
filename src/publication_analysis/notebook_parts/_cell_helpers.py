"""Shared notebook-cell construction helpers, matching the convention used by
``analysis/eda/notebook_build/eda_c/*``: each cell is a plain notebook-JSON
dict, no ``nbformat`` library involved.
"""
from __future__ import annotations


def src(text: str) -> list[str]:
    lines = text.lstrip("\n").splitlines(keepends=True)
    if lines and lines[-1].endswith("\n"):
        lines[-1] = lines[-1][:-1]
    return lines


def md(cid: str, text: str) -> dict:
    return {"id": cid, "cell_type": "markdown", "metadata": {}, "source": src(text)}


def code(cid: str, text: str) -> dict:
    return {
        "id": cid,
        "cell_type": "code",
        "metadata": {},
        "source": src(text),
        "outputs": [],
        "execution_count": None,
    }
