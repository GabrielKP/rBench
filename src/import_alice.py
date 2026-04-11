"""Import the Alice (adv_pasv) CYOA dataset from GitHub into the benchmark format.

All source files (transcripts and recall ratings) live in the same GitHub
directory and are downloaded via the GitHub contents API.

The download/conversion functions in this module are also used by
import_monthiversary.py, which shares the same file format and structure.

Writes to:
  data/alice/<story_name>/transcripts/scenes.json
  data/alice/<story_name>/recalls/sub_sentences.json
  data/alice/<story_name>/matches/human-scenes-sub_sentences.json
"""

import io
import json
import math
from pathlib import Path

import pandas as pd
import requests
from rich.console import Console

# ── alice config ──────────────────────────────────────────────────────────────
ALICE_GITHUB_URL = (
    "https://api.github.com/repos/xianNeuro/cyoa/contents/data/ratings/adv_pasv"
)
ALICE_STORIES = [
    "alice_2",
    "alice_3",
    "alice_4",
    "alice_5",
    "alice_6",
    "alice_7",
    "alice_8",
    "alice_11",
    "alice_12",
    "alice_13",
]


# ── helpers ───────────────────────────────────────────────────────────────────

console = Console()


def write_json(path: Path, data: dict, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    print(f"  wrote {path}")


def _download_bytes(url: str) -> bytes:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def _parse_story_version(filestem: str) -> str:
    """Strip the 2-character alphabetic prefix from the first ``_``-split token.

    e.g. ``"ap2_sub3027_rate-recall"`` → ``"2"``
         ``"rp3_sub3042_rate-recall"`` → ``"3"``
    """
    return filestem.split("_")[0][2:]


def parse_cyoa_events(
    events_raw, sub_id: str, story_name: str, n_events: int, idx_recall: int
) -> list[int]:
    """Parse the events column from a CYOA recall CSV into 0-based story indices."""
    if isinstance(events_raw, float) and math.isnan(events_raw):
        # For alice10, monthiversary6, all 'none' values stem from empty cells, I checked.
        return []
    elif isinstance(events_raw, int):
        events_raw = str(events_raw)
    elif isinstance(events_raw, float):
        if ".0" in str(events_raw):  # It's X.0
            events_raw = str(int(events_raw))
        # if not, someone placed a comma by accident (X.64)

    events_raw = str(events_raw).replace(".", ",")
    indices = []
    for idx_event_str in events_raw.split(","):
        idx_event_str = idx_event_str.strip()
        if not idx_event_str:
            continue
        idx_event = int(idx_event_str) - 1

        if idx_event >= n_events and len(idx_event_str) >= 4:
            # Excel drops comma thousands separators, turning "98,100" into 98100.
            # Split from the right in 3-digit chunks; the leading chunk may be 1–2 digits.
            remainder = idx_event_str
            chunks: list[str] = []
            while len(remainder) > 3:
                chunks.append(remainder[-3:])
                remainder = remainder[:-3]
            chunks.append(remainder)
            chunks.reverse()
            for chunk in chunks:
                chunk_idx = int(chunk) - 1
                if 0 <= chunk_idx < n_events:
                    indices.append(chunk_idx)
                else:
                    console.print(
                        "  Warning: event index out of range:"
                        f" {sub_id=} {story_name=} idx={chunk_idx} {idx_recall=}",
                        style="red",
                    )
        elif idx_event < 0 or idx_event >= n_events:
            console.print(
                f"  Warning: event index out of range:"
                f" {sub_id=} {story_name=} idx={idx_event} {idx_recall=}",
                style="red",
            )
        else:
            indices.append(idx_event)

    return sorted(set(indices))


# ── download phase ────────────────────────────────────────────────────────────


def download_all(
    github_url: str,
    dataset_name: str,
    stories: list[str],
    downloads_dir: Path,
) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, pd.DataFrame]]]:
    """Download every relevant XLSX from a GitHub contents API directory.

    Returns:
        transcripts_by_version  – ``{ version: DataFrame(event, text) }``
        recalls_by_version      – ``{ version: { sub_id: DataFrame(segment, events, text) } }``
    """
    print(f"Listing source files for '{dataset_name}' via GitHub API …")
    resp = requests.get(github_url, timeout=30)
    resp.raise_for_status()
    entries = resp.json()

    downloads_dir.mkdir(parents=True, exist_ok=True)

    transcripts: dict[str, pd.DataFrame] = {}
    recalls: dict[str, dict[str, pd.DataFrame]] = {}

    for entry in entries:
        name: str = entry["name"]
        if not name.endswith(".xlsx") or name.startswith("~$"):
            continue

        stem = Path(name).stem  # e.g. "ap2_sub3027_rate-recall"
        parts = stem.split("_")
        version = _parse_story_version(stem)

        if f"{dataset_name}_{version}" not in stories:
            continue

        dest = downloads_dir / name
        if dest.exists():
            print(f"  cached {name}")
            raw = dest.read_bytes()
        else:
            print(f"  downloading {name} …")
            raw = _download_bytes(entry["download_url"])
            dest.write_bytes(raw)

        # ── transcript (events) file ──────────────────────────────────────────
        if len(parts) >= 3 and parts[2].startswith("events"):
            df = pd.read_excel(io.BytesIO(raw))
            df = df.rename(columns={"story_texts": "text"})
            transcripts[version] = df[["event", "text"]]

        # ── recall (rate-recall) file ─────────────────────────────────────────
        elif len(parts) >= 3 and parts[2].startswith("rate-recall"):
            sub_id = parts[1]
            df = pd.read_excel(io.BytesIO(raw))
            df = df.rename(
                columns={
                    "recalled_events": "events",
                    "recall_in_temporal_order": "text",
                }
            )
            df["segment"] = list(range(1, len(df) + 1))
            recalls.setdefault(version, {})[sub_id] = df[["segment", "events", "text"]]

        else:
            print(f"  skipping unrecognised filename: {name}")

    return transcripts, recalls


# ── conversion phase ──────────────────────────────────────────────────────────


def convert_story_version(
    version: str,
    dataset_name: str,
    data_dir: Path,
    transcript_df: pd.DataFrame,
    sub_recalls: dict[str, pd.DataFrame],
) -> None:
    """Write the three benchmark JSONs for a single story version."""
    story_name = f"{dataset_name}_{version}"
    out_dir = data_dir / story_name
    print(f"\nConverting {story_name} …")

    story_segments = transcript_df["text"].tolist()
    n_events = len(story_segments)

    write_json(
        out_dir / "transcripts" / "scenes.json",
        {
            "type": "transcript",
            "segmentation_method": "scenes",
            "segments": story_segments,
        },
    )

    all_recalls: dict[str, list[str]] = {}
    all_ratings: dict[str, list] = {}

    for sub_id, recall_df in sorted(sub_recalls.items()):
        all_recalls[sub_id] = recall_df["text"].tolist()

        sub_ratings = []
        for idx_recall, row in recall_df.iterrows():
            matched = parse_cyoa_events(
                row["events"],
                sub_id,
                story_name,
                n_events,
                idx_recall=int(idx_recall),  # type: ignore
            )
            sub_ratings.append([int(idx_recall), matched])  # type: ignore
        all_ratings[sub_id] = sub_ratings

    write_json(
        out_dir / "recalls" / "sub_sentences.json",
        {
            "type": "recalls",
            "segmentation_method": "sub_sentences",
            "recalls": all_recalls,
        },
    )

    write_json(
        out_dir / "matches" / "human-scenes-sub_sentences.json",
        {
            "type": "matches",
            "matcher": "human",
            "story_segmentation": "scenes",
            "recall_segmentation": "sub_sentences",
            "n_story_segments": n_events,
            "ratings": all_ratings,
        },
    )


# ── shared entry point ────────────────────────────────────────────────────────


def cyoa_import(github_url: str, dataset_name: str, stories: list[str]) -> None:
    downloads_dir = Path("downloads") / dataset_name
    data_dir = Path("data") / dataset_name

    transcripts_by_version, recalls_by_version = download_all(
        github_url, dataset_name, stories, downloads_dir
    )

    all_versions = set(transcripts_by_version) | set(recalls_by_version)
    for version in sorted(all_versions, key=lambda v: int(str(v))):
        if version not in transcripts_by_version:
            print(f"\nWarning: no transcript for version '{version}', skipping")
            continue
        if version not in recalls_by_version:
            print(f"\nWarning: no recalls for version '{version}', skipping")
            continue
        convert_story_version(
            version,
            dataset_name,
            data_dir,
            transcripts_by_version[version],
            recalls_by_version[version],
        )

    print("\nDone.")


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    cyoa_import(
        github_url=ALICE_GITHUB_URL,
        dataset_name="alice",
        stories=ALICE_STORIES,
    )


if __name__ == "__main__":
    main()
