"""Import the FilmFest dataset from GitHub into the benchmark format.

All source files (recalls and annotations) are downloaded via the GitHub
contents API and cached locally under downloads/filmfest/.

The recall `scenes` column contains global Segment numbers from the annotation
(after ffill + Run-2 offset), which are mapped to 0-based per-movie indices.
Only the first annotation file (alphabetically) is used for transcript text.

Writes to:
  data/filmfest/<movie_name>/transcripts/scenes.json
  data/filmfest/<movie_name>/recalls/sub_sentences.json
  data/filmfest/<movie_name>/matches/human-scenes-sub_sentences.json
"""

import io
import json
from pathlib import Path

import pandas as pd
import requests

# ── filmfest config ────────────────────────────────────────────────────────────
FILMFEST_GITHUB_URL = (
    "https://api.github.com/repos/jchenlab-jhu/filmfest/contents/recall_scenematched"
)
FILMFEST_ANNOTATIONS_URL = (
    "https://api.github.com/repos/jchenlab-jhu/filmfest/contents/annotations"
)

FILMFEST_MOVIE_TO_NUM = {
    "1. Cartoon intro 1": 12,
    "2. Catch Me If You Can": 1,
    "3. The Record": 2,
    "4. The Boyfriend": 3,
    "5. The Shoe": 4,
    "6. Keith Reynolds": 5,
    "8. The Rock": 6,
    "9. The Prisoner": 7,
    "10. The Black Hole": 8,
    "11. Post-it Love": 9,
    "12. Bus Stop": 10,
    "7. Cartoon intro 2": 11,
}
FILMFEST_NUM_TO_MOVIE = {
    12: "cartoon_intro_1",
    1: "catch_me_if_you_can",
    2: "the_record",
    3: "the_boyfriend",
    4: "the_shoe",
    5: "keith_reynolds",
    6: "the_rock",
    7: "the_prisoner",
    8: "the_black_hole",
    9: "post_it_love",
    10: "bus_stop",
    11: "cartoon_intro_2",
}

# Cartoon intros are excluded from the benchmark output
FILMFEST_SKIP_MOVIES = {11, 12}  # cartoon_intro_1, cartoon_intro_2

# Scene numbers used in recalls to indicate no match
_NO_MATCH_SCENES = {-1, 10000}


# ── helpers ───────────────────────────────────────────────────────────────────


def write_json(path: Path, data: dict, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    print(f"  wrote {path}")


def _download_bytes(url: str) -> bytes:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def _list_github_dir(api_url: str) -> list[dict]:
    resp = requests.get(api_url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _fetch_cached(entry: dict, cache_dir: Path) -> bytes:
    dest = cache_dir / entry["name"]
    if dest.exists():
        print(f"  cached {entry['name']}")
        return dest.read_bytes()
    print(f"  downloading {entry['name']} …")
    raw = _download_bytes(entry["download_url"])
    dest.write_bytes(raw)
    return raw


# ── download phase ────────────────────────────────────────────────────────────


def download_all(
    downloads_dir: Path,
) -> tuple[list[tuple[str, bytes]], list[tuple[str, bytes]]]:
    """Download all recall and annotation XLSX files from GitHub.

    Returns:
        recalls     - list of (filename_stem, raw_bytes), sorted by stem
        annotations - list of (filename_stem, raw_bytes), sorted by stem
    """
    recalls_dir = downloads_dir / "recall_scenematched"
    annotations_dir = downloads_dir / "annotations"
    recalls_dir.mkdir(parents=True, exist_ok=True)
    annotations_dir.mkdir(parents=True, exist_ok=True)

    print("Listing recall files via GitHub API …")
    recall_entries = _list_github_dir(FILMFEST_GITHUB_URL)
    recalls: list[tuple[str, bytes]] = []
    for entry in sorted(recall_entries, key=lambda e: e["name"]):
        name: str = entry["name"]
        if not name.endswith(".xlsx") or name.startswith("~$") or name.startswith("_"):
            continue
        recalls.append((Path(name).stem, _fetch_cached(entry, recalls_dir)))

    print("Listing annotation files via GitHub API …")
    annotation_entries = _list_github_dir(FILMFEST_ANNOTATIONS_URL)
    annotations: list[tuple[str, bytes]] = []
    for entry in sorted(annotation_entries, key=lambda e: e["name"]):
        name = entry["name"]
        if not name.endswith(".xlsx") or name.startswith("~$"):
            continue
        annotations.append((Path(name).stem, _fetch_cached(entry, annotations_dir)))

    return recalls, annotations


# ── annotation parsing ────────────────────────────────────────────────────────


def parse_annotation(raw: bytes) -> pd.DataFrame:
    """Parse an annotation XLSX into a clean per-row DataFrame.

    Returns a DataFrame with columns:
        movie_num, seg_num (global, continuous across runs), description
    """
    df = pd.read_excel(io.BytesIO(raw))

    idx_run2 = int(df[df["Scanning run"] == "Run 2"].index[0])
    df = df.ffill(axis=0)

    # Make Segment numbers continuous across Run 1 and Run 2
    idx_col = df.columns.get_loc("Segment number")
    last_seg_run1 = df.iloc[idx_run2 - 1, idx_col]
    df.iloc[idx_run2:, idx_col] += int(last_seg_run1)  # type: ignore[operator]

    df["movie_num"] = df["Movie title"].map(FILMFEST_MOVIE_TO_NUM)
    df = df.rename(columns={"Segment number": "seg_num", "Description": "description"})
    df["description"] = df["description"].str.strip()

    return df[["movie_num", "seg_num", "description"]]


def build_transcript_per_movie(
    annotation_df: pd.DataFrame,
) -> dict[int, tuple[list[str], dict[int, int]]]:
    """Build per-movie scene lists from the annotation.

    For each movie, coarse scenes (unique seg_num values) are extracted in
    order. The first fine-grained description for each coarse scene is used.

    Returns:
        { movie_num: (segments_list, seg_num_to_0based_idx) }
    """
    transcripts: dict[int, tuple[list[str], dict[int, int]]] = {}
    for movie_num, grp in annotation_df.groupby("movie_num"):
        # One description per coarse segment (first fine-grained row)
        first_per_seg = grp.drop_duplicates(subset="seg_num", keep="first")
        first_per_seg = first_per_seg.sort_values("seg_num")
        segments = first_per_seg["description"].tolist()
        seg_to_idx = {
            int(seg): idx for idx, seg in enumerate(first_per_seg["seg_num"].tolist())
        }
        transcripts[int(movie_num)] = (segments, seg_to_idx)  # type: ignore[arg-type]
    return transcripts


# ── recall parsing ────────────────────────────────────────────────────────────


def parse_recall(raw: bytes, sub_id: str) -> pd.DataFrame:
    """Parse a recall XLSX. Returns a DataFrame with movie_num, scene, text."""
    df = pd.read_excel(io.BytesIO(raw))
    df = df.rename(columns={"movies": "movie_num", "scenes": "scene"})
    df["text"] = df["text"].str.strip()
    df["sub_id"] = sub_id
    return df[["sub_id", "movie_num", "scene", "text"]]


def _parse_scene_numbers(raw_scenes) -> list[int]:
    """Parse a scenes cell (e.g. '182, 185' or -1) into a list of ints."""
    if pd.isna(raw_scenes):
        return []
    s = str(raw_scenes).strip()
    result = []
    for token in s.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            result.append(int(float(token)))
        except ValueError:
            pass
    return result


def recall_to_scene_indices(scene_raw, seg_to_idx: dict[int, int]) -> list[int]:
    """Map a recall `scenes` cell to 0-based indices in the transcript segments."""
    scene_nums = _parse_scene_numbers(scene_raw)
    indices = []
    for sn in scene_nums:
        if sn in _NO_MATCH_SCENES:
            continue
        idx = seg_to_idx.get(sn)
        if idx is not None:
            indices.append(idx)
        else:
            print(f"  Warning: scene number {sn} not found in annotation")
    return sorted(set(indices))


# ── conversion phase ──────────────────────────────────────────────────────────


def convert_movie(
    movie_num: int,
    segments: list[str],
    seg_to_idx: dict[int, int],
    sub_recalls: dict[str, pd.DataFrame],
    data_dir: Path,
) -> None:
    """Write the three benchmark JSONs for a single movie."""
    movie_name = FILMFEST_NUM_TO_MOVIE[movie_num]
    out_dir = data_dir / movie_name
    print(f"\nConverting {movie_name} …")

    write_json(
        out_dir / "transcripts" / "scenes.json",
        {
            "type": "transcript",
            "segmentation_method": "scenes",
            "segments": segments,
        },
    )

    all_recalls: dict[str, list[str]] = {}
    all_ratings: dict[str, list] = {}

    for sub_id, recall_df in sorted(sub_recalls.items()):
        movie_df = recall_df[recall_df["movie_num"] == movie_num].reset_index(drop=True)
        if movie_df.empty:
            continue
        all_recalls[sub_id] = movie_df["text"].tolist()
        sub_ratings = []
        for idx_recall, row in movie_df.iterrows():
            matched = recall_to_scene_indices(row["scene"], seg_to_idx)
            sub_ratings.append([int(idx_recall), matched])  # type: ignore[arg-type]
        all_ratings[sub_id] = sub_ratings

    if not all_recalls:
        print(
            f"  Warning: no recalls found for {movie_name}, skipping recall/match files"
        )
        return

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
            "n_story_segments": len(segments),
            "ratings": all_ratings,
        },
    )


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    downloads_dir = Path("downloads") / "filmfest"
    data_dir = Path("data") / "filmfest"

    recall_files, annotation_files = download_all(downloads_dir)

    # Use the first annotation file (alphabetically) for transcript text
    print(f"\nParsing annotation from '{annotation_files[0][0]}' …")
    annotation_df = parse_annotation(annotation_files[0][1])
    transcripts_by_movie = build_transcript_per_movie(annotation_df)

    # Parse all recall files, keyed by sub_id
    print("\nParsing recall files …")
    sub_recalls: dict[str, pd.DataFrame] = {}
    for stem, raw in recall_files:
        sub_id = stem  # e.g. "sub-01_recall", "sub-08_recall1"
        sub_recalls[sub_id] = parse_recall(raw, sub_id)

    for movie_num, (segments, seg_to_idx) in sorted(transcripts_by_movie.items()):
        if movie_num in FILMFEST_SKIP_MOVIES:
            print(f"\nSkipping {FILMFEST_NUM_TO_MOVIE[movie_num]} (cartoon intro)")
            continue
        convert_movie(movie_num, segments, seg_to_idx, sub_recalls, data_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
