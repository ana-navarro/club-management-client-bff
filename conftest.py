from pathlib import Path


def pytest_ignore_collect(collection_path: Path) -> bool | None:
    """Skip test files marked @wip (constitution, Principle III)."""
    if collection_path.suffix == ".py" and "@wip" in collection_path.read_text(encoding="utf-8"):
        return True
    return None
