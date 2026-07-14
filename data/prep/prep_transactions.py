"""Stratified sampler for the 9.5M-row SAML-D transactions dataset.

Keeps every laundering-positive row and samples 2% of normal rows, streaming
the source parquet in 500k-row batches so the full file is never
materialized in memory. Output feeds ingestion/transactions.py's
replay-clock adapter (Sprint 2, later this sprint).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SOURCE_PATH = Path("data/aml_transactions/SAML-D_cleaned.parquet")
OUTPUT_PATH = Path("data/processed/txn_sample.parquet")
CHUNK_SIZE = 500_000
NORMAL_SAMPLE_RATE = 0.02
RANDOM_SEED = 42


def sample_transactions(
    source_path: Path = SOURCE_PATH,
    output_path: Path = OUTPUT_PATH,
    chunk_size: int = CHUNK_SIZE,
    normal_sample_rate: float = NORMAL_SAMPLE_RATE,
    random_seed: int = RANDOM_SEED,
) -> Path:
    """Stream `source_path`, keep all laundering rows plus a sample of normals.

    Reads via pyarrow's batch iterator (not pandas.read_parquet) specifically
    so the 9.5M-row source is never loaded whole into memory.
    """
    if not source_path.exists():
        raise FileNotFoundError(f"SAML-D source dataset not found at {source_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    parquet_file = pq.ParquetFile(source_path)
    total_rows = parquet_file.metadata.num_rows
    logger.info("streaming %s (%d rows) in %d-row batches", source_path, total_rows, chunk_size)

    kept_chunks: list[pd.DataFrame] = []
    laundering_count = 0
    normal_kept_count = 0
    rows_seen = 0

    for batch_index, batch in enumerate(parquet_file.iter_batches(batch_size=chunk_size)):
        chunk = batch.to_pandas()
        rows_seen += len(chunk)

        laundering_rows = chunk[chunk["Is_laundering"] == 1]
        normal_rows = chunk[chunk["Is_laundering"] == 0]

        # Seed offset by batch_index so the sample isn't biased toward
        # whatever random state chunk 0 happened to leave behind, while
        # staying fully deterministic across reruns.
        sampled_normal = normal_rows.sample(frac=normal_sample_rate, random_state=random_seed + batch_index)

        laundering_count += len(laundering_rows)
        normal_kept_count += len(sampled_normal)

        kept_chunks.append(pd.concat([laundering_rows, sampled_normal], ignore_index=True))
        logger.info(
            "batch %d: %d rows seen (%d total so far) -> kept %d laundering, %d normal",
            batch_index,
            len(chunk),
            rows_seen,
            len(laundering_rows),
            len(sampled_normal),
        )

    result = pd.concat(kept_chunks, ignore_index=True)
    result.to_parquet(output_path, index=False)

    logger.info(
        "wrote %d rows (%d laundering, %d normal) to %s",
        len(result),
        laundering_count,
        normal_kept_count,
        output_path,
    )
    return output_path


if __name__ == "__main__":
    sample_transactions()
