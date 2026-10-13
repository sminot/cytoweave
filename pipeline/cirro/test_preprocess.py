import pandas as pd

from preprocess import annotations, fcs_files

DATA = "s3://project-1/datasets/d1/data"


def files_table(*rows):
    return pd.DataFrame(rows, columns=["sample", "file"])


def test_fcs_files_keeps_fcs_files_sorted_and_once():
    files = files_table(
        ("B", f"{DATA}/B.FCS"),
        ("A", f"{DATA}/A.fcs"),
        ("A", f"{DATA}/A.fcs"),
        ("notes", f"{DATA}/notes.csv"),
        ("C", f"{DATA}/C.lmd"),
    )
    assert fcs_files(files)["file"].tolist() == [f"{DATA}/A.fcs", f"{DATA}/B.FCS", f"{DATA}/C.lmd"]


def test_annotations_by_file_name_from_sample_metadata():
    fcs = fcs_files(files_table(("D01_Stim", f"{DATA}/plate 1/D01_Stim.fcs"), ("D01_Unstim", f"{DATA}/D01_Unstim.fcs")))
    samplesheet = pd.DataFrame({"sample": ["D01_Stim", "D01_Unstim"], "condition": ["Stim", "Unstim"], "donor": ["D01", "D01"], "empty": [None, None]})
    table, repeated = annotations(fcs, samplesheet)
    assert repeated == []
    assert table.to_dict("records") == [
        {"file": "D01_Unstim.fcs", "condition": "Unstim", "donor": "D01"},
        {"file": "D01_Stim.fcs", "condition": "Stim", "donor": "D01"},
    ]


def test_annotations_remove_what_breaks_cytoweaves_csv_reading():
    fcs = fcs_files(files_table(("S1", f"{DATA}/S1.fcs")))
    samplesheet = pd.DataFrame({"sample": ["S1"], "treatment, dose": ['IL-2; "high"'], "day": [7]})
    table, _ = annotations(fcs, samplesheet)
    assert table.to_dict("records") == [{"file": "S1.fcs", "treatment dose": "IL-2 high", "day": "7"}]


def test_annotations_write_whole_numbers_without_decimals():
    fcs = fcs_files(files_table(("S1", f"{DATA}/S1.fcs"), ("S2", f"{DATA}/S2.fcs")))
    samplesheet = pd.DataFrame({"sample": ["S1", "S2"], "day": [7, None], "dose": [0.5, 2]})
    table, _ = annotations(fcs, samplesheet)
    assert table.to_dict("records") == [{"file": "S1.fcs", "day": "7", "dose": "0.5"}, {"file": "S2.fcs", "day": "", "dose": "2"}]


def test_annotations_leave_out_repeated_file_names():
    fcs = fcs_files(files_table(("P1_A01", f"{DATA}/plate1/A01.fcs"), ("P2_A01", f"{DATA}/plate2/A01.fcs"), ("P1_A02", f"{DATA}/plate1/A02.fcs")))
    samplesheet = pd.DataFrame({"sample": ["P1_A01", "P2_A01", "P1_A02"], "plate": ["1", "2", "1"]})
    table, repeated = annotations(fcs, samplesheet)
    assert repeated == ["A01.fcs"]
    assert table.to_dict("records") == [{"file": "A02.fcs", "plate": "1"}]


def test_no_annotations_without_metadata():
    fcs = fcs_files(files_table(("S1", f"{DATA}/S1.fcs")))
    table, _ = annotations(fcs, pd.DataFrame({"sample": ["S1"]}))
    assert table.empty
