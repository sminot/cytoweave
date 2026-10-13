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


def fcs_files(files: pd.DataFrame) -> pd.DataFrame:
    """The FCS files of Cirro's file table (columns sample, file), one row per file."""
    fcs = files[files["file"].str.lower().str.endswith(FCS_SUFFIXES)]
    return fcs[["sample", "file"]].drop_duplicates("file").sort_values("file").reset_index(drop=True)


def annotations(fcs: pd.DataFrame, samplesheet: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """CytoWeave sample annotations keyed by file name (its first column), from the metadata of each
    file's Cirro sample. Returns the table (empty when there is no metadata) and the file names left
    out because more than one file has that name, so the name cannot say which sample it is."""
    fields = [c for c in samplesheet.columns if c != "sample" and samplesheet[c].notna().any()]
    names = fcs["file"].map(lambda f: PurePosixPath(f).name)
    repeated = sorted(name for name, n in Counter(names).items() if n > 1)
    if not fields:
        return pd.DataFrame(), repeated
    table = pd.DataFrame({"file": names, "sample": fcs["sample"]})
    table = table[~table["file"].isin(repeated)]
    table = table.merge(samplesheet[["sample", *fields]].drop_duplicates("sample"), on="sample", how="left")
    table = table.drop(columns="sample").rename(columns=csv_safe)
    for column in table.columns[1:]:
        table[column] = table[column].map(lambda v: "" if pd.isna(v) else csv_safe(v))
    return table, repeated


if __name__ == "__main__":
    from cirro.helpers.preprocess_dataset import PreprocessDataset

    ds = PreprocessDataset.from_running()
    ds.log()
    fcs = fcs_files(ds.files)
    if fcs.empty:
        raise SystemExit("The input datasets hold no FCS files.")
    fcs[["file"]].to_csv("fcs_files.csv", index=False)
    ds.add_param("input", "fcs_files.csv")
    # A form option, not a workflow parameter.
    use_metadata = ds.params.get("sample_metadata", True)
    if "sample_metadata" in ds.params:
        ds.remove_param("sample_metadata")
    if use_metadata:
        table, repeated = annotations(fcs, ds.samplesheet)
        if repeated:
            ds.logger.warning(f"Not annotated: {len(repeated)} file names belong to more than one file ({', '.join(repeated[:5])})")
        if not table.empty:
            table.to_csv("annotations.csv", index=False)
            ds.add_param("annotations", "annotations.csv")
