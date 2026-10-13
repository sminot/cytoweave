import pandas as pd

from preprocess import annotations, fcs_files

DATA = "s3://project-1/datasets/d1/data"
NO_LINKS = pd.DataFrame(columns=["sample", "file"])


def links(*rows):
    return pd.DataFrame(rows, columns=["sample", "file"])


def test_fcs_files_keeps_fcs_files_sorted_and_once():
    uris = [f"{DATA}/B.FCS", f"{DATA}/A.fcs", f"{DATA}/A.fcs", f"{DATA}/notes.csv", f"{DATA}/C.lmd"]
    assert fcs_files(uris) == [f"{DATA}/A.fcs", f"{DATA}/B.FCS", f"{DATA}/C.lmd"]


def test_annotations_by_sample_name_when_files_are_not_linked():
    fcs = [f"{DATA}/D01_Stim.fcs", f"{DATA}/D01_Unstim.fcs"]
    samplesheet = pd.DataFrame({"sample": ["D01_Stim", "D01_Unstim"], "condition": ["Stim", "Unstim"], "donor": ["D01", "D01"], "empty": [None, None]})
    table, repeated = annotations(fcs, NO_LINKS, samplesheet)
    assert repeated == []
    assert table.to_dict("records") == [
        {"file": "D01_Stim", "condition": "Stim", "donor": "D01"},
        {"file": "D01_Unstim", "condition": "Unstim", "donor": "D01"},
    ]


def test_annotations_by_file_name_when_files_are_linked():
    fcs = [f"{DATA}/plate 1/tube-3.fcs", f"{DATA}/tube-1.fcs"]
    files = links(("S3", fcs[0]), ("S1", fcs[1]), ("S2", f"{DATA}/notes.csv"))
    samplesheet = pd.DataFrame({"sample": ["S1", "S2", "S3"], "condition": ["Stim", "x", "Unstim"]})
    table, _ = annotations(fcs, files, samplesheet)
    assert table.to_dict("records") == [{"file": "tube-1.fcs", "condition": "Stim"}, {"file": "tube-3.fcs", "condition": "Unstim"}]


def test_annotations_remove_what_breaks_cytoweaves_csv_reading():
    samplesheet = pd.DataFrame({"sample": ["S1"], "treatment, dose": ['IL-2; "high"'], "day": [7]})
    table, _ = annotations([f"{DATA}/S1.fcs"], NO_LINKS, samplesheet)
    assert table.to_dict("records") == [{"file": "S1", "treatment dose": "IL-2 high", "day": "7"}]


def test_annotations_write_whole_numbers_without_decimals():
    samplesheet = pd.DataFrame({"sample": ["S1", "S2"], "day": [7, None], "dose": [0.5, 2]})
    table, _ = annotations([f"{DATA}/S1.fcs", f"{DATA}/S2.fcs"], NO_LINKS, samplesheet)
    assert table.to_dict("records") == [{"file": "S1", "day": "7", "dose": "0.5"}, {"file": "S2", "day": "", "dose": "2"}]


def test_annotations_leave_out_repeated_file_names():
    fcs = [f"{DATA}/plate1/A01.fcs", f"{DATA}/plate1/A02.fcs", f"{DATA}/plate2/A01.fcs"]
    files = links(("P1_A01", fcs[0]), ("P1_A02", fcs[1]), ("P2_A01", fcs[2]))
    samplesheet = pd.DataFrame({"sample": ["P1_A01", "P2_A01", "P1_A02"], "plate": ["1", "2", "1"]})
    table, repeated = annotations(fcs, files, samplesheet)
    assert repeated == ["A01.fcs"]
    assert table.to_dict("records") == [{"file": "A02.fcs", "plate": "1"}]


def test_no_annotations_without_metadata():
    table, _ = annotations([f"{DATA}/S1.fcs"], NO_LINKS, pd.DataFrame({"sample": ["S1"]}))
    assert table.empty
