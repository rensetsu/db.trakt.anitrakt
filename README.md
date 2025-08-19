# db.trakt.anitrakt

[![GitHub Repo stars](https://img.shields.io/github/stars/rensetsu/db.trakt.anitrakt?style=social)](https://github.com/rensetsu/db.trakt.anitrakt)
[![GitHub Repo forks](https://img.shields.io/github/forks/rensetsu/db.trakt.anitrakt?style=social)](https://github.com/rensetsu/db.trakt.anitrakt/fork)

A scraped table data from [AniTrakt by Huere](https://anitrakt.huere.net/) to
get anime mappings on [MyAnimeList](https://myanimelist.net) and [Trakt](https://trakt.tv).

> [!WARNING]
>
> **THIS REPO IS NOT OFFICIALLY SUPPORTED BY HUERE, MAL, or TRAKT.**

If you used any contents from this repo in your project and found bugs or want
to submit a suggestion, please send us [issues](https://github.com/rensetsu/db.trakt.anitrakt/issues).

> [!NOTE]
>
> **Extended Database Available**
>
> For a more comprehensive dataset with richer metadata, please use
> the [Extended Database](https://github.com/rensetsu/db.trakt.extended-anitrakt)
> repo instead. The extended database includes release years, external IDs
> (TMDB, TVDB, IMDb), and handles issues like `guessed_slug`. This repository
> should primarily be used if you only need the basic mapping between MyAnimeList
> and Trakt IDs.

## Data Structure

| Key Name | Type | Description |
| --- | --- | --- |
| `title` | `string` | The title of the anime |
| `mal_id` | `int` | MyAnimeList ID of the anime |
| `trakt_id` | `int` | Trakt ID of the show/movie |
| `guessed_slug` | `string \| null` | Guessed slug of the anime, see [comments](#additional-comment) for additional context |
| `type` | `Enum["shows", "movies"]` | Type of the anime |
| `season` | `int` | Season number of the anime, only for `type == "shows"` |

### Examples

> [!NOTE]
>
> Final result does not contain comments, it's just for additional context in
> this README.

#### Shows

```jsonc
[
  // Example of a show "Shingeki no Kyojin", both season 1 and 2
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

To construct to a link, you can use the following format:

```text
https://trakt.tv/{type}/{guessed_slug}/seasons/{season}
```

#### Movies

```jsonc
[
  // Example of a movie "Kimi no Na wa."
  {
    "title": "Kimi no Na wa.",
    "mal_id": 32281,
    "trakt_id": 1402,
    // Guessed slug won't work for movies, see additional comment
    "guessed_slug": "your-name",
    "type": "movies"
  }
]
```

To construct to a link, you can use the following format:

```text
https://trakt.tv/{type}/{guessed_slug}-{year, see additional comment}
```

## Additional Comment

### Guessed Slug

#### Recommendation

For the most reliable and complete data, including accurate slugs, release
years, and other metadata, it is **highly recommended** to use the **[Extended repo](https://github.com/rensetsu/db.trakt.extended-anitrakt)**.
The extended database programmatically fetches the correct information directly
from the Trakt.tv API, resolving the limitations described below.

This repository is best suited for users who only require the basic mapping
between MyAnimeList and Trakt IDs.

#### `guessed_slug` Limitations

If you choose to use this repository, please be aware of the following
limitations regarding the `guessed_slug` field:

* **Based on English Titles:** \
   Slugs are generated from the presumed English title of the anime. This can
   lead to inaccuracies if the title on Trakt.tv differs.
* **Movies Require the Year:** \
   The `guessed_slug` for movies is incomplete. Trakt.tv requires the release
   year to be appended to the slug (e.g., `your-name-2016`). This information
   is not included in this database.
* **Potential for Mismatches:** \
   While generally effective for TV shows, a `guessed_slug` might not work for
   shows with similar names on Trakt.
* **Non-alphabetical Titles:** \
  Titles that are purely numerical or symbols have a `null` value for
  `guessed_slug` to prevent conflicts with Trakt's numeric ID system.

In cases where the `guessed_slug` is incorrect, you can always fall back to
using the `trakt_id` to fetch the correct information directly from the
Trakt.tv API.

### Additional File

In `db/` folder, you might encounter some files started with `overwrite_`. This
file contains pure rules from this repo to overwrite the existing data in the database.
