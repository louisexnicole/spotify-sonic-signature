"""
The Sonic Signature - Data preparation script
=============================================

What this script does
---------------------
1. Loads the raw Spotify CSV (read-only - the original file is never modified).
2. Checks that every column the analysis needs actually exists. If one is
   missing, the script stops with a clear error instead of guessing.
3. Cleans and validates the data (each rule is explained below).
4. Saves:
     data/processed/spotify_clean.csv               - cleaned track-level data
     data/processed/year_summary.csv                - yearly medians + track counts
     data/processed/genre_summary.csv               - genre medians by era
     data/processed/tempo_popularity_spearman.csv   - Spearman correlation result
     reports/data_quality_report.md                 - what was found and removed

How to run (from the project folder)
------------------------------------
    .sonicvenv\\Scripts\\activate
    python src/prepare_data.py

Running it again always gives the same results (there is no randomness).
"""

import hashlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------------

# Build paths relative to this file, so the script works from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "archive" / "spotify_data.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"

# The study period.
FIRST_YEAR = 2000
LAST_YEAR = 2023

# Columns the analysis cannot run without.
REQUIRED_COLUMNS = [
    "track_id", "artist_name", "track_name", "year", "genre", "popularity",
    "tempo", "energy", "danceability", "acousticness", "valence",
]

# Audio features that we summarise.
AUDIO_FEATURES = ["tempo", "energy", "danceability", "acousticness", "valence"]

# Spotify features measured on a 0-1 scale.
ZERO_TO_ONE_FEATURES = ["energy", "danceability", "acousticness", "valence"]

# A genre/era group with fewer tracks than this is flagged as "small sample".
MIN_TRACKS_FOR_RELIABLE_MEDIAN = 30


# ---------------------------------------------------------------------------
# 2. Helper functions
# ---------------------------------------------------------------------------

def file_md5(path):
    """Return the MD5 fingerprint of a file. Used to prove the raw file is unchanged."""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


def assign_era(year):
    """Group a release year into one of the three comparison eras."""
    if 2000 <= year <= 2009:
        return "2000s"
    if 2010 <= year <= 2019:
        return "2010s"
    if 2020 <= year <= 2023:
        return "2020-2023"
    return None


def df_to_markdown(df):
    """Turn a small DataFrame into a Markdown table (no extra libraries needed)."""
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    divider = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([header, divider] + rows)


# ---------------------------------------------------------------------------
# 3. Load the raw data
# ---------------------------------------------------------------------------

def load_raw_data():
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Raw data file not found: {RAW_FILE}")

    print(f"Loading {RAW_FILE.name} ...")
    df = pd.read_csv(RAW_FILE)
    print(f"  Loaded {len(df):,} rows and {len(df.columns)} columns.")
    return df


def check_required_columns(df):
    """Stop the script if any column we need is missing. We never invent columns."""
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise SystemExit(
            "STOPPING: these required columns are not in the dataset: "
            + ", ".join(missing)
            + ".\nThe analysis cannot continue without them."
        )
    print("  All required columns are present.")


# ---------------------------------------------------------------------------
# 4. Profile the raw data (feeds the quality report)
# ---------------------------------------------------------------------------

def profile_raw_data(df):
    """Collect facts about the raw data before any cleaning."""
    profile = {
        "rows": len(df),
        "columns": len(df.columns),
        "dtypes": df.dtypes.astype(str),
        "missing": df.isna().sum(),
        "exact_duplicate_rows": int(df.drop(columns=["Unnamed: 0"], errors="ignore").duplicated().sum()),
        "duplicate_track_ids": int(df["track_id"].duplicated().sum()),
    }

    # "Near duplicates": same artist + title once case and spaces are ignored.
    # These are usually re-releases/remasters with a different track_id.
    artist_key = df["artist_name"].str.lower().str.strip()
    title_key = df["track_name"].str.lower().str.strip()
    profile["near_duplicates"] = int(pd.DataFrame({"a": artist_key, "t": title_key}).duplicated().sum())

    profile["popularity_zero"] = int((df["popularity"] == 0).sum())
    return profile


# ---------------------------------------------------------------------------
# 5. Clean and validate
# ---------------------------------------------------------------------------

def clean_data(df):
    """
    Apply the cleaning rules one at a time and record how many rows each rule removes.
    Returns the cleaned DataFrame and a log (list of dictionaries) for the report.
    """
    df = df.copy()  # work on a copy so the loaded raw data stays untouched
    log = []

    def record(rule, reason, before):
        log.append({"rule": rule, "reason": reason, "rows_removed": before - len(df)})

    # Rule 1: drop the leftover index column from an earlier export.
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])

    # Rule 2: tidy text columns (remove leading/trailing spaces).
    for col in ["artist_name", "track_name", "genre", "track_id"]:
        df[col] = df[col].str.strip()

    # Rule 3: fill missing artist/track names with "Unknown".
    # These rows still have valid audio features, so we keep them.
    df["artist_name"] = df["artist_name"].fillna("Unknown")
    df["track_name"] = df["track_name"].fillna("Unknown")

    # Rule 4: remove duplicate track_ids (the same song listed twice).
    before = len(df)
    df = df.drop_duplicates(subset="track_id", keep="first")
    record("Duplicate track_id", "Same Spotify track listed more than once", before)

    # Rule 5: keep only the study period.
    before = len(df)
    df = df[df["year"].between(FIRST_YEAR, LAST_YEAR)]
    record("Year outside 2000-2023", "Outside the study period", before)

    # Rule 6: remove failed audio analyses.
    # In this dataset, tempo = 0 always comes together with danceability = 0 and
    # time_signature = 0, which means Spotify could not analyse the track.
    before = len(df)
    df = df[df["tempo"] > 0]
    record("tempo = 0", "Failed audio analysis (danceability and time_signature also 0)", before)

    before = len(df)
    df = df[df["time_signature"] > 0]
    record("time_signature = 0", "Invalid time signature", before)

    # Rule 7: validate value ranges. Anything outside the documented range is an error.
    before = len(df)
    in_range = df["popularity"].between(0, 100)
    for col in ZERO_TO_ONE_FEATURES:
        in_range &= df[col].between(0, 1)
    df = df[in_range]
    record("Out-of-range values", "popularity outside 0-100 or a 0-1 feature outside 0-1", before)

    # Rule 8: remove any rows still missing a required value (expected: none).
    before = len(df)
    df = df.dropna(subset=REQUIRED_COLUMNS)
    record("Missing required value", "A required column is empty", before)

    # Add the era column used by the genre summary.
    df["era"] = df["year"].apply(assign_era)

    df = df.reset_index(drop=True)
    return df, log


def validate_clean_data(df):
    """Final safety checks. If any fail, the script stops instead of saving bad data."""
    checks = {
        "No duplicate track_id": df["track_id"].is_unique,
        "No missing required values": df[REQUIRED_COLUMNS].notna().all().all(),
        "Years within 2000-2023": df["year"].between(FIRST_YEAR, LAST_YEAR).all(),
        "Popularity within 0-100": df["popularity"].between(0, 100).all(),
        "Tempo greater than 0": (df["tempo"] > 0).all(),
        "0-1 features within 0-1": all(df[c].between(0, 1).all() for c in ZERO_TO_ONE_FEATURES),
        "Every row has an era": df["era"].notna().all(),
    }
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if not all(checks.values()):
        raise SystemExit("STOPPING: validation failed - see the FAIL lines above.")
    return checks


# ---------------------------------------------------------------------------
# 6. Summaries
# ---------------------------------------------------------------------------

def make_year_summary(df):
    """One row per year: number of tracks and the median of each audio feature."""
    summary = df.groupby("year").agg(
        track_count=("track_id", "count"),
        median_popularity=("popularity", "median"),
        **{f"median_{f}": (f, "median") for f in AUDIO_FEATURES},
    )
    return summary.reset_index().round(4)


def make_genre_summary(df):
    """
    One row per genre and era (2000s, 2010s, 2020-2023), in "long" format,
    which works well for Power BI. Small groups are flagged.
    """
    era_order = ["2000s", "2010s", "2020-2023"]
    summary = df.groupby(["genre", "era"]).agg(
        track_count=("track_id", "count"),
        median_popularity=("popularity", "median"),
        **{f"median_{f}": (f, "median") for f in AUDIO_FEATURES},
    ).reset_index()

    summary["small_sample"] = summary["track_count"] < MIN_TRACKS_FOR_RELIABLE_MEDIAN

    # Sort eras in time order instead of alphabetically.
    summary["era"] = pd.Categorical(summary["era"], categories=era_order, ordered=True)
    summary = summary.sort_values(["genre", "era"]).reset_index(drop=True)
    return summary.round(4)


# ---------------------------------------------------------------------------
# 7. Spearman correlation: tempo vs popularity
# ---------------------------------------------------------------------------

def tempo_popularity_spearman(df):
    """
    Spearman correlation measures whether higher tempo tends to go with higher
    popularity (a monotonic relationship). It uses ranks, so it is not thrown off
    by outliers and does not assume a straight-line relationship.

    We compute it twice:
      - all cleaned tracks
      - excluding popularity = 0 (many tracks have 0, which may mean "no data"
        rather than "unpopular"), as a sensitivity check.
    """
    results = []
    subsets = {
        "All cleaned tracks": df,
        "Excluding popularity = 0": df[df["popularity"] > 0],
    }
    for name, subset in subsets.items():
        rho, p_value = stats.spearmanr(subset["tempo"], subset["popularity"])
        results.append({
            "subset": name,
            "n_tracks": len(subset),
            "spearman_rho": round(float(rho), 4),
            "p_value": float(p_value),
        })
    return pd.DataFrame(results)


def describe_strength(rho):
    """Common rule of thumb for describing the size of a correlation."""
    size = abs(rho)
    if size < 0.1:
        return "negligible"
    if size < 0.3:
        return "weak"
    if size < 0.5:
        return "moderate"
    return "strong"


# ---------------------------------------------------------------------------
# 8. Data quality report
# ---------------------------------------------------------------------------

def write_quality_report(profile, log, checks, clean_df, spearman_df, md5_before, md5_after):
    removed_total = profile["rows"] - len(clean_df)

    raw_table = pd.DataFrame({
        "column": profile["dtypes"].index,
        "dtype": profile["dtypes"].values,
        "missing": profile["missing"].values,
    })
    log_table = pd.DataFrame(log)
    checks_table = pd.DataFrame({
        "check": list(checks.keys()),
        "result": ["PASS" if v else "FAIL" for v in checks.values()],
    })
    year_counts = clean_df["year"].value_counts().sort_index()
    era_counts = clean_df["era"].value_counts().reindex(["2000s", "2010s", "2020-2023"])

    spearman_lines = []
    for row in spearman_df.itertuples(index=False):
        spearman_lines.append(
            f"- **{row.subset}** (n = {row.n_tracks:,}): rho = {row.spearman_rho}, "
            f"p = {row.p_value:.3g} - a {describe_strength(row.spearman_rho)} relationship."
        )

    report = f"""# Data Quality Report - The Sonic Signature

Generated: {datetime.now():%Y-%m-%d %H:%M} by `src/prepare_data.py`

## Source file
- Path: `data/raw/archive/spotify_data.csv`
- MD5 before run: `{md5_before}`
- MD5 after run:  `{md5_after}`
- Original file unchanged: **{"Yes" if md5_before == md5_after else "NO - investigate"}**

## Raw data overview
- Rows: {profile["rows"]:,}
- Columns: {profile["columns"]}
- Exact duplicate rows (ignoring the old index column): {profile["exact_duplicate_rows"]:,}
- Duplicate `track_id`s: {profile["duplicate_track_ids"]:,}
- Near-duplicates (same artist + title, ignoring case/spaces, different `track_id`): {profile["near_duplicates"]:,}
- Tracks with popularity = 0: {profile["popularity_zero"]:,}

{df_to_markdown(raw_table)}

## Cleaning steps
- Dropped the `Unnamed: 0` column (a leftover index from an earlier export).
- Stripped spaces from text columns.
- Filled missing `artist_name` / `track_name` with "Unknown" (rows kept because their audio features are valid).
- Added an `era` column: 2000s (2000-2009), 2010s (2010-2019), 2020-2023.

Rows removed by each rule (rules applied in this order):

{df_to_markdown(log_table)}

**Total removed: {removed_total:,} rows ({removed_total / profile["rows"]:.2%}). Clean rows: {len(clean_df):,}.**

## Validation checks on the clean data
{df_to_markdown(checks_table)}

## Clean data coverage
Tracks per era:

{df_to_markdown(era_counts.rename_axis("era").reset_index(name="track_count"))}

Tracks per year:

{df_to_markdown(year_counts.rename_axis("year").reset_index(name="track_count"))}

## Tempo vs popularity (Spearman)
{chr(10).join(spearman_lines)}

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
"""
    report_path = REPORTS_DIR / "data_quality_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# 9. Run everything
# ---------------------------------------------------------------------------

def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Fingerprint the raw file before we touch anything.
    md5_before = file_md5(RAW_FILE)

    raw_df = load_raw_data()
    check_required_columns(raw_df)

    print("Profiling raw data ...")
    profile = profile_raw_data(raw_df)

    print("Cleaning data ...")
    clean_df, log = clean_data(raw_df)
    for entry in log:
        print(f"  {entry['rule']}: removed {entry['rows_removed']:,} rows")
    print(f"  Clean rows: {len(clean_df):,}")

    print("Validating clean data ...")
    checks = validate_clean_data(clean_df)

    print("Building summaries ...")
    year_summary = make_year_summary(clean_df)
    genre_summary = make_genre_summary(clean_df)
    spearman_df = tempo_popularity_spearman(clean_df)

    print("Saving outputs ...")
    clean_df.to_csv(PROCESSED_DIR / "spotify_clean.csv", index=False)
    year_summary.to_csv(PROCESSED_DIR / "year_summary.csv", index=False)
    genre_summary.to_csv(PROCESSED_DIR / "genre_summary.csv", index=False)
    spearman_df.to_csv(PROCESSED_DIR / "tempo_popularity_spearman.csv", index=False)

    # Confirm the raw file was not changed.
    md5_after = file_md5(RAW_FILE)
    report_path = write_quality_report(profile, log, checks, clean_df, spearman_df, md5_before, md5_after)

    print("\nSpearman correlation (tempo vs popularity):")
    print(spearman_df.to_string(index=False))
    print(f"\nRaw file unchanged: {md5_before == md5_after}")
    print(f"Outputs saved to {PROCESSED_DIR} and {report_path}")


if __name__ == "__main__":
    main()
