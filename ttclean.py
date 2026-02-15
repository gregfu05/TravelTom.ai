import pandas as pd
import numpy as np
from pathlib import Path
import tarfile
import pyarrow as pa
from pyarrow import parquet as pq


# ── Config ──────────────────────────────────────────────
TAR_PATH = Path("data/yelp_dataset.tar")          # adjust to your local path
MEMBER = "yelp_academic_dataset_business.json"
CITIES = ["Santa Barbara"]
PARQUET_PATH = Path("data/business_SB_cluster.parquet")
CHUNK = 200_000

# Columns to drop:
#   - postal_code: not useful for training (lat/long is sufficient)
#   - name: business_id is the unique identifier
#   - city: redundant with lat/long
#   - state: redundant with lat/long
#   - address: redundant with lat/long
COLS_TO_DROP = ["postal_code", "name", "city", "state", "address"]


def extract_to_parquet(tar_path: Path, member: str, cities: list, out_path: Path, chunk_size: int = CHUNK):
    """Extract Santa Barbara businesses from Yelp tar and write to parquet."""
    if out_path.exists():
        out_path.unlink()

    writer = None
    written = 0

    with tarfile.open(tar_path, "r:*") as tar:
        with tar.extractfile(member) as f:
            for chunk in pd.read_json(f, lines=True, chunksize=chunk_size):
                sub = chunk[
                    (chunk["state"].astype(str).str.strip() == "CA")
                    & (chunk["city"].astype(str).str.strip().isin(cities))
                ]
                if sub.empty:
                    continue
                table = pa.Table.from_pandas(sub, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(out_path, table.schema, compression="zstd")
                writer.write_table(table)
                written += len(sub)

    if writer:
        writer.close()

    print(f"Rows written: {written}")
    print(f"Exists? {out_path.exists()}  Size: {out_path.stat().st_size if out_path.exists() else 0}")
    return out_path


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the business dataframe: drop unnecessary columns and add popularity score."""
    # Drop columns not needed for training
    df = df.drop(columns=[c for c in COLS_TO_DROP if c in df.columns])

    # Stars alone is misleading when review_count is very low.
    # Popularity score weights stars by log of review count.
    df["popularity"] = df["stars"] * np.log1p(df["review_count"])

    return df


def main():
    # Step 1: Extract from tar → parquet (skip if parquet already exists)
    if not PARQUET_PATH.exists():
        print("Parquet not found — extracting from tar...")
        PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
        extract_to_parquet(TAR_PATH, MEMBER, CITIES, PARQUET_PATH)
    else:
        print(f"Using existing parquet: {PARQUET_PATH}")

    # Step 2: Load
    df = pd.read_parquet(PARQUET_PATH)
    print(f"Raw shape: {df.shape}")

    # Step 3: Clean
    df = clean(df)
    print(f"Cleaned shape: {df.shape}")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nHead:\n{df.head()}")

    # Step 4: Save cleaned version
    out = PARQUET_PATH.with_name("business_SB_clean.parquet")
    df.to_parquet(out, compression="zstd", index=False)
    print(f"\nSaved cleaned parquet → {out}")


if __name__ == "__main__":
    main()
