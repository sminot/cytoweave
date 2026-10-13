# CytoWeave in a pipeline

A Nextflow workflow that applies a CytoWeave analysis template (`.cwt`) to a set
of FCS files with [`cytoweave run`](../README.md#headless-runs), in a container
with CytoWeave and Chromium, and publishes what the run writes:

- the template's tables, as `tables.xlsx` and a CSV per table;
- the batch report of its last figure (`report.pdf`, or `.pptx`);
- the workspace (`workspace.cwz`), to open and review in CytoWeave;
- the methods (`methods.txt`);
- `run.json`: each input's checksum, each step's outcome, every population's
  count in every sample, and what was written;
- on request, a FlowJo workspace (`workspace.wsp`), a review report
  (`review.html`) and a reproducibility certificate (`certificate.acs`).

It is the same analysis as the window's and as a `cytoweave run` on a laptop,
for datasets too large to open in a browser tab: [Cirro](https://cirro.bio)
runs it on its own compute and makes the outputs a new dataset.

| File | |
|---|---|
| `main.nf`, `nextflow.config` | The workflow: one task runs `cytoweave run` on all the files. |
| `Dockerfile` | The container: CytoWeave built from this repository, Chromium and fonts. |
| `cirro/` | The Cirro process configuration: form, parameter map, compute, preprocess. |

## Running it

Build the container from the repository root:

```sh
docker build -f pipeline/Dockerfile -t cytoweave-run:dev .
```

Then run the workflow on a folder of FCS files:

```sh
nextflow run pipeline/main.nf --fcs 'plate-12/*.fcs' --template panel.cwt \
  --annotations samples.csv --outdir results --container cytoweave-run:dev
```

Without `--container` it uses the published image,
`public.ecr.aws/cirrobio/cytoweave-run:0.8.0` (CytoWeave 0.8.0, linux/amd64);
build that one with `docker buildx build --platform linux/amd64`.

| Parameter | Default | |
|---|---|---|
| `--fcs` | | The FCS files: a glob or a path. |
| `--input` | | Instead of `--fcs`, a CSV with a `file` column (Cirro's preprocess writes one). |
| `--template` | | The analysis template (`.cwt`). |
| `--annotations` | | A CSV of sample annotations (first column the sample or file name), or a plate layout. |
| `--outdir` | `results` | Where the outputs are published. |
| `--report` | `pdf` | The batch report: `pdf`, `pptx` or `none`. |
| `--report_by` | | The report's pages: `sample`, or an annotation such as `subject`. |
| `--qc` | false | Run acquisition QC first, with a "QC pass" population above the template's. |
| `--flowjo`, `--review`, `--certificate` | false | Also write a FlowJo workspace, a review report, a certificate. |
| `--timeout` | `12h` | Stop a `cytoweave run` that takes longer. |

The task fails when any step of the run fails; its log shows each step's
outcome, as `cytoweave run` prints them. Files with the same name in different
folders are each staged in a folder of their own, and keep their names.

The task runs in a container as root, so the image starts Chromium with
`--no-sandbox` (the container is the sandbox) and `--disable-dev-shm-usage`
(Docker's 64 MB `/dev/shm` is too small for large samples).

## In Cirro

`cirro/` holds the process configuration: it takes a Flow Cytometry (FCS)
dataset, and its form asks for the template, whether to annotate the samples
with the dataset's sample metadata, QC, and which outputs to write. The
template is a `.cwt` file in any of the project's datasets: in CytoWeave,
*Save as a template…* and *Download (.cwt)*, then upload it to the project.

`preprocess.py` runs before the workflow. It lists the input dataset's FCS
files for `--input`, and turns Cirro's sample metadata (condition, donor,
timepoint) into an annotations table keyed by file name for `--annotations`.
A file name that more than one file has is left out of the table, since the
name cannot say which sample it is. CytoWeave reads that table without
quoting, so commas, semicolons, tabs and quotes in the metadata become spaces.
`test_preprocess.py` tests it offline (`pytest pipeline/cirro`).

Each run uses 8 CPUs and 32 GB, and runs again with twice the memory when it
runs out. All the files are analyzed in one Chromium page, as in the window;
`cytoweave run` opens up to 20,000 files.

`cirro/process-definition.json` is the process record (id `cytoweave-run`,
parent process `fcs`). With the Cirro plugin for Claude Code, `create_process` registers it and `upload_process_config` with
`assets_dir: pipeline/cirro` uploads the files as they are written. Check them
first with `cirro-agent read check-config pipeline/cirro`.

### Applying a template from CytoWeave

CytoWeave's Cirro integration opens Cirro datasets and saves analyses to
Cirro. A later change could offer *Apply this template to a Cirro dataset* for datasets too
large to open: CytoWeave would save the template as a file in the project (as
it saves analyses, as a dataset tagged `cirro-app: cytoweave`), then start this
process with `ExecutionApi.runAnalysis` from `@cirrobio/api-client`:

```js
await execution.runAnalysis({ projectId, runAnalysisRequest: {
  name: `${template.name} on ${dataset.name}`,
  processId: 'cytoweave-run',
  sourceDatasetIds: [dataset.id],
  params: { analysis: { template: templateUri, sample_metadata: true }, outputs: { report: 'pdf' } },
} });
```

`params` mirrors the form's groups (`process-input.json` maps them to the
workflow's parameters), and `templateUri` is the `s3://` address of the saved
`.cwt`. The app's registration would need the `RUN_ANALYSIS` permission (with
`VIEW_DATASET_LOGS` to follow the run). The run's output dataset holds
`workspace.cwz`, which the integration opens like a saved analysis.
