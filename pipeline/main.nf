#!/usr/bin/env nextflow
// Applies a CytoWeave analysis template (.cwt) to a set of FCS files with "cytoweave run" and
// publishes its outputs: the tables (tables.xlsx and a CSV per table), the batch report, the
// workspace (workspace.cwz), the methods and run.json. See README.md.

nextflow.enable.dsl = 2

def requireParam(name) {
    if (!params[name]) error "Give --${name}; see pipeline/README.md."
    params[name]
}

process CYTOWEAVE_RUN {
    label 'cytoweave'
    publishDir params.outdir, mode: 'copy', saveAs: { path -> file(path).name }

    input:
    // One folder per file: a dataset may hold the same file name in different folders.
    path fcs, stageAs: 'fcs/?/*'
    path template
    path annotations

    output:
    path 'results/*'

    script:
    def options = ["--report ${params.report}"]
    if (annotations) options << "--annotations ${annotations}"
    if (params.report_by) options << "--report-by '${params.report_by}'"
    if (params.qc) options << '--qc'
    if (params.flowjo) options << '--flowjo'
    if (params.review) options << '--review'
    if (params.certificate) options << '--certificate'
    """
    cytoweave run --template ${template} --output results --timeout ${params.timeout} ${options.join(' ')} ${fcs}
    """
}

workflow {
    // These reach a shell command line.
    if (!(params.report in ['pdf', 'pptx', 'none'])) error "--report is pdf, pptx or none, not '${params.report}'."
    if (params.report_by && !(params.report_by ==~ /[A-Za-z0-9 _.-]+/)) error "--report_by is a sample annotation's name (letters, digits, spaces, _ . -), not '${params.report_by}'."
    if (!(params.timeout ==~ /(\d+(\.\d+)?[hms])+/)) error "--timeout is a duration such as 12h or 90m, not '${params.timeout}'."
    // --input: a CSV with a "file" column (the Cirro preprocess writes one); --fcs: a glob.
    def fcs = params.input
        ? Channel.fromPath(params.input, checkIfExists: true).splitCsv(header: true).map { row -> file(row.file, checkIfExists: true) }
        : Channel.fromPath(requireParam('fcs'), checkIfExists: true)
    def annotations = params.annotations ? file(params.annotations, checkIfExists: true) : []
    CYTOWEAVE_RUN(
        fcs.collect(sort: true).ifEmpty { error 'No FCS files were found.' },
        file(requireParam('template'), checkIfExists: true),
        annotations
    )
}
