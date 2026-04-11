"""Import the Monthiversary (rom_pasv) CYOA dataset from GitHub into the benchmark format.

Writes to:
  data/monthiversary/<story_name>/transcripts/scenes.json
  data/monthiversary/<story_name>/recalls/sub_sentences.json
  data/monthiversary/<story_name>/matches/human-scenes-sub_sentences.json
"""

from import_alice import cyoa_import

MONTHIVERSARY_GITHUB_URL = (
    "https://api.github.com/repos/xianNeuro/cyoa/contents/data/ratings/rom_pasv"
)
MONTHIVERSARY_STORIES = [
    "monthiversary_3",
    "monthiversary_4",
    "monthiversary_10",
    "monthiversary_14",
    "monthiversary_19",
    "monthiversary_23",
    "monthiversary_25",
]


def main() -> None:
    cyoa_import(
        github_url=MONTHIVERSARY_GITHUB_URL,
        dataset_name="monthiversary",
        stories=MONTHIVERSARY_STORIES,
    )


if __name__ == "__main__":
    main()
