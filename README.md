# Recall Matching Benchmark

A benchmark for evaluating recall-to-story segment matching methods.

## Datasets
| Dataset | Stories | Modality | Transcript segmentation | Recall segmentation |
|---|---|---|---|---|
| **alice** | 10 short interactive stories | text | scenes | sub_sentences |
| **monthiversary** | 7 long interactive stories | text | scenes | sub_sentences |
| **memsearch** | 10 short animated films | audiovisual | events, scenes | sentences |

## Directory structure

```
benchmark/
  description.json
  {dataset}/
    dataset.json
    {story}/
      transcripts/{method}.json
      recalls/{method}.json
      matches/{matcher}-{story_method}-{recall_method}.json
```

## File formats

All files are JSON.

### Transcript (`transcripts/{method}.json`)
```json
{
  "type": "transcript",
  "segmentation_method": "scenes",
  "segments": ["segment 1 text", "segment 2 text", "..."]
}
```

### Recalls (`recalls/{method}.json`)

```json
{
  "type": "recalls",
  "segmentation_method": "sentences",
  "recalls": {
    "sub-001": ["recall segment 1", "recall segment 2", "..."]
  }
}
```

### Matches (`matches/{matcher}-{story_method}-{recall_method}.json`)

```json
{
  "type": "matches",
  "matcher": "human",
  "story_segmentation": "events",
  "recall_segmentation": "sentences",
  "n_story_segments": 4,
  "ratings": {
    "sub-001": [[0, [0]], [1, [1, 2]], [2, [3]], [3, []]]
  }
}
```

Each entry in `ratings` maps a subject to a list of `[recall_segment_idx, [matched_story_segment_idx, ...]]` pairs (0-based). A single recall segment can match multiple story segments.
