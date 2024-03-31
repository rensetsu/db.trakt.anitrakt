# aniTrakt-IndexParser

A scraped table data from [AniTrakt by Huere](https://anitrakt.huere.net/) to
get anime mappings on [MyAnimeList](https://myanimelist.net) and [Trakt](https://trakt.tv).

> [!WARNING]
>
> **THIS REPO IS NOT OFFICIALLY SUPPORTED BY HUERE, MAL, or TRAKT.**

If you used any contents from this repo in your project and found bugs or want
to submit a suggestion, please send us [issues](https://github.com/ryuuganime/aniTrakt-IndexParser/issues).

To get the scraped data, go to [`db/`](db/) folder and download as raw.

## Data Structure

| Key Name | Type | Description |
| --- | --- | --- |
| `title` | `string` | The title of the anime |
| `mal_id` | `int` | MyAnimeList ID of the anime |
| `trakt_id` | `int` | Trakt ID of the show/movie |
| `guessed_slug` | `string` | Guessed slug of the anime, Trakt mainly uses this for human-readable URL |
| `type` | `Enum["shows", "movies"]` | Type of the anime |
| `season` | `int` | Season number of the anime, only for `type == "shows"` |

### Examples

#### Shows

```json
[
  {
    "title": "Shingeki no Kyojin",
    "mal_id": 16498,
    "trakt_id": 1420,
    "guessed_slug": "attack-on-titan",
    "type": "shows",
    "season": 1
  },
  {
    "title": "Shingeki no Kyojin Season 2",
    "mal_id": 25777,
    "trakt_id": 1420,
    "guessed_slug": "attack-on-titan",
    "type": "shows",
    "season": 2
  }
]
```

#### Movies

```json
[
  {
    "title": "Kimi no Na wa.",
    "mal_id": 32281,
    "trakt_id": 1402,
    "guessed_slug": "your-name",
    "type": "movies"
  }
]
```

## Additional Comment

In `db/` folder, you might encounter some files started with `overwrite_`. This
file contains pure rules from this repo to overwrite the existing data in the database.
