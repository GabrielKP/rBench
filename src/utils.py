import json
from pathlib import Path


def write_json(path: Path, data: dict, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    print(f"  wrote {path}")
