# Recall Matching Benchmark

A small benchmark for evaluating recall-to-story segment matching methods.

> We are currently constructing a larger benchmark with multiple raters and many more recalls!

## Datasets
| Dataset           | Stories                      | Modality    | Transcript segmentation | Recall segmentation | Source                                                               |
| ----------------- | ---------------------------- | ----------- | ----------------------- | ------------------- | -------------------------------------------------------------------- |
| **alice**         | 10 short interactive stories | text        | scenes                  | sub_sentences       | [Li et al. 2026](https://www.nature.com/articles/s41467-026-73907-2) |
| **monthiversary** | 7 long interactive stories   | text        | scenes                  | sub_sentences       | [Li et al. 2026](https://www.nature.com/articles/s41467-026-73907-2) |
| **memsearch**     | 10 short animated films      | audiovisual | events, scenes          | sentences           | Kahlyn Eckles & Janice Chen, previously unpublished data.            |

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

## Sources

### Alice

Sourced from https://github.com/xianNeuro/cyoa:
> Li, Xian, Nicole Kim Ni, Savannah J. Born, et al. “Interactive Narratives Reveal the Personalizing Effect of Agency on Episodic Memory.” Nature Communications 17, no. 1 (2026): 7272. https://doi.org/10.1038/s41467-026-73907-2.

*Participants read a story segment by segment, and then recalled it by typing into text box. Story segments could be very short or multiple sentences long. During the reading, participants were presented with 'choice points', in which they could influence how the story continued. Here, we only selected recalls from the control condition, in which participants only had one 'choice' (passive condition). The text of the choice point is included in the story transcripts (e.g. 'Stare at it' for [alice_2](data/alice/alice_2/transcripts/scenes.json)) Recalls were segmented based on punctuation and topic shifts. Trained raters matched recall segments to segments of the original story. Each recall was matched by only one rater.*


### Memsearch

Data was collected by Kahlyn Eckles for a larger project, and is unpublished outside of these behavioral recalls.

*Participants saw 1-2 min long videos and recalled them verbally in the end. Movies were segmented and transcribed. Recalls were also transcribed. Raters matched recall segments to the story segments they referred to. Each recall was matched by only one rater.*

The video stimuli can be found here: https://figshare.com/account/articles/34918569

### Monthiversary

Sourced from https://github.com/xianNeuro/cyoa:
> Li, Xian, Nicole Kim Ni, Savannah J. Born, et al. “Interactive Narratives Reveal the Personalizing Effect of Agency on Episodic Memory.” Nature Communications 17, no. 1 (2026): 7272. https://doi.org/10.1038/s41467-026-73907-2.

*Data collection for this category followed the same procedure as `alice` - except that this time the participants in the passive condition (the participants that we chose) saw two 'choices' but had to click on one of them. Only the choice that was clicked is included in the transcript.*
