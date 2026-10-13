"""Before the workflow starts in Cirro: list the input datasets' FCS files for --input, and turn
Cirro's sample metadata into a CytoWeave annotations table for --annotations."""

import re
from collections import Counter
from pathlib import PurePosixPath

import pandas as pd

FCS_SUFFIXES = (".fcs", ".lmd")

# CytoWeave splits an annotations table's lines on these without reading quotes.
CSV_UNSAFE = re.compile(r'[,;\t"\r\n]')


def csv_safe(value) -> str:
    # A numeric column with blanks is read as floats: 7.0 is written 7.
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(CSV_UNSAFE.sub(" ", str(value)).split())


def fcs_files(uris: list[str]) -> list[str]:
    """The FCS files among a dataset's files, sorted, each once."""
    return sorted({uri for uri in uris if uri.lower().endswith(FCS_SUFFIXES)})


def annotations(fcs: list[str], files: pd.DataFrame, samplesheet: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """CytoWeave sample annotations from Cirro's sample metadata (samplesheet: sample and its
    fields). When Cirro links the FCS files to samples (files: sample, file), the table is keyed by
    file name, and a name that more than one file has is left out (returned), since it cannot say
    which sample it is. Otherwise it is keyed by sample name, which CytoWeave matches to the file
    <sample>.fcs. Empty when there is no metadata."""
    fields = [c for c in samplesheet.columns if c != "sample" and samplesheet[c].notna().any()]
    if not fields:
        return pd.DataFrame(), []
    metadata = samplesheet[["sample", *fields]].drop_duplicates("sample")
    linked = files[files["file"].isin(fcs)]
    repeated = []
    if linked.empty:
        table = metadata.rename(columns={"sample": "file"})
    else:
        names = linked["file"].map(lambda f: PurePosixPath(f).name)
        repeated = sorted(name for name, n in Counter(names).items() if n > 1)
        keys = pd.DataFrame({"file": names, "sample": linked["sample"]})
        keys = keys[~keys["file"].isin(repeated)].sort_values("file")
        table = keys.merge(metadata, on="sample", how="left").drop(columns="sample")
    table = table.rename(columns=csv_safe)
    for column in table.columns[1:]:
        table[column] = table[column].map(lambda v: "" if pd.isna(v) else csv_safe(v))
    return table.reset_index(drop=True), repeated


def list_s3(prefix: str) -> list[str]:
    """Every object below an s3:// prefix, as s3:// URIs."""
    import boto3

    bucket, _, key = prefix.removeprefix("s3://").partition("/")
    pages = boto3.client("s3").get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=key.rstrip("/") + "/")
    return [f"s3://{bucket}/{item['Key']}" for page in pages for item in page.get("Contents", [])]


if __name__ == "__main__":
    from cirro.helpers.preprocess_dataset import PreprocessDataset

    ds = PreprocessDataset.from_running()
    ds.log()
    # Cirro's file table lists only files linked to samples, which FCS datasets' files are not.
    fcs = fcs_files([uri for dataset in ds.metadata["inputs"] for uri in list_s3(dataset["dataPath"])])
    if not fcs:
        raise SystemExit("The input datasets hold no FCS files.")
    ds.logger.info(f"FCS files: {len(fcs):,}")
    pd.DataFrame({"file": fcs}).to_csv("fcs_files.csv", index=False)
    ds.add_param("input", "fcs_files.csv")
    # A form option, not a workflow parameter.
    use_metadata = ds.params.get("sample_metadata", True)
    if "sample_metadata" in ds.params:
        ds.remove_param("sample_metadata")
    if use_metadata:
        table, repeated = annotations(fcs, ds.files, ds.samplesheet)
        if repeated:
            ds.logger.warning(f"Not annotated: {len(repeated)} file names belong to more than one file ({', '.join(repeated[:5])})")
        ds.logger.info(f"Annotations: {len(table):,} rows, fields {', '.join(table.columns[1:]) or 'none'}")
        if not table.empty:
            table.to_csv("annotations.csv", index=False)
            ds.add_param("annotations", "annotations.csv")
