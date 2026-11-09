# Data Quality Report - The Sonic Signature

Generated: 2026-11-09 20:09 by `src/prepare_data.py`

## Source file
- Path: `data/raw/archive/spotify_data.csv`
- MD5 before run: `96bf298b1baba3d59dc4c1335e8fd168`
- MD5 after run:  `96bf298b1baba3d59dc4c1335e8fd168`
- Original file unchanged: **Yes**

## Raw data overview
- Rows: 1,159,764
- Columns: 20
- Exact duplicate rows (ignoring the old index column): 0
- Duplicate `track_id`s: 0
- Near-duplicates (same artist + title, ignoring case/spaces, different `track_id`): 7,868
- Tracks with popularity = 0: 158,391

| column | dtype | missing |
| --- | --- | --- |
| Unnamed: 0 | int64 | 0 |
| artist_name | str | 15 |
| track_name | str | 1 |
| track_id | str | 0 |
| popularity | int64 | 0 |
| year | int64 | 0 |
| genre | str | 0 |
| danceability | float64 | 0 |
| energy | float64 | 0 |
| key | int64 | 0 |
| loudness | float64 | 0 |
| mode | int64 | 0 |
| speechiness | float64 | 0 |
| acousticness | float64 | 0 |
| instrumentalness | float64 | 0 |
| liveness | float64 | 0 |
| valence | float64 | 0 |
| tempo | float64 | 0 |
| duration_ms | int64 | 0 |
| time_signature | int64 | 0 |

## Cleaning steps
- Dropped the `Unnamed: 0` column (a leftover index from an earlier export).
- Stripped spaces from text columns.
- Filled missing `artist_name` / `track_name` with "Unknown" (rows kept because their audio features are valid).
- Added an `era` column: 2000s (2000-2009), 2010s (2010-2019), 2020-2023.

Rows removed by each rule (rules applied in this order):

| rule | reason | rows_removed |
| --- | --- | --- |
| Duplicate track_id | Same Spotify track listed more than once | 0 |
| Year outside 2000-2023 | Outside the study period | 0 |
| tempo = 0 | Failed audio analysis (danceability and time_signature also 0) | 1199 |
| time_signature = 0 | Invalid time signature | 29 |
| Out-of-range values | popularity outside 0-100 or a 0-1 feature outside 0-1 | 0 |
| Missing required value | A required column is empty | 0 |

**Total removed: 1,228 rows (0.11%). Clean rows: 1,158,536.**

## Validation checks on the clean data
| check | result |
| --- | --- |
| No duplicate track_id | PASS |
| No missing required values | PASS |
| Years within 2000-2023 | PASS |
| Popularity within 0-100 | PASS |
| Tempo greater than 0 | PASS |
| 0-1 features within 0-1 | PASS |
| Every row has an era | PASS |

## Clean data coverage
Tracks per era:

| era | track_count |
| --- | --- |
| 2000s | 443428 |
| 2010s | 514265 |
| 2020-2023 | 200843 |

Tracks per year:

| year | track_count |
| --- | --- |
| 2000 | 44007 |
| 2001 | 42330 |
| 2002 | 42065 |
| 2003 | 42296 |
| 2004 | 43360 |
| 2005 | 43729 |
| 2006 | 45448 |
| 2007 | 45967 |
| 2008 | 47408 |
| 2009 | 46818 |
| 2010 | 46794 |
| 2011 | 46406 |
| 2012 | 54751 |
| 2013 | 53177 |
| 2014 | 53087 |
| 2015 | 51500 |
| 2016 | 40259 |
| 2017 | 56118 |
| 2018 | 56465 |
| 2019 | 55708 |
| 2020 | 54940 |
| 2021 | 53565 |
| 2022 | 53691 |
| 2023 | 38647 |

## Tempo vs popularity (Spearman)
- **All cleaned tracks** (n = 1,158,536): rho = -0.0036, p = 0.000105 - a negligible relationship.
- **Excluding popularity = 0** (n = 1,000,578): rho = -0.0014, p = 0.172 - a negligible relationship.

With over a million tracks, even a tiny correlation will be "statistically significant",
so judge it by the size of rho, not by the p-value.

## Known limitations (kept, not fixed)
- **Near-duplicates were kept.** They have different `track_id`s and may be genuine
  re-releases, so removing them would be a judgement call.
- **Popularity is a snapshot** taken when the data was collected, not popularity at release.
  Older tracks may score lower simply because fewer people stream them today.
- **Popularity = 0 is common** and may mean "no data" rather than "unpopular".
  This is why the Spearman test is also run without those tracks.
- **One genre per track.** Each track has a single genre label from the source dataset.
- **Uneven coverage:** some genres have few or no tracks in some years. See
  `small_sample` in `genre_summary.csv`.
