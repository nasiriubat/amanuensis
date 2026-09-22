# Benchmark

A paper that introduces a benchmark, dataset or evaluation suite, or that
systematically compares existing methods on a defined task. The contribution is a fair,
reusable way to measure something the community cares about, plus what the measurement
reveals.

## What reviewers expect

- A precise task definition: inputs, outputs, what counts as correct.
- Justification for why existing benchmarks are insufficient: saturation, leakage,
  narrow coverage, unrealistic data.
- Construction process: sources, filtering, annotation, quality control, statistics.
- Metrics with reasons, and their known weaknesses.
- Baselines that are strong and fairly tuned, with reproducible settings.
- Results with variance: multiple runs or seeds, confidence intervals where possible.
- Analysis beyond the leaderboard: error categories, what separates methods, where all
  methods fail.
- Availability: data, code, evaluation harness, licence.

## Common reasons for rejection

- Baselines are weak or misconfigured, making the proposed method look better.
- Single run per configuration, no variance reported.
- Data leakage between splits, or contamination from public sources.
- Metric does not measure what the task claims to measure.
- No analysis: a table of numbers and a claim of state of the art.
- Benchmark not released, or released without the evaluation code.

## Framing moves that work

- Show a concrete failure of an existing benchmark in the introduction.
- Report statistics of the dataset in a table early: size, splits, sources, label
  distribution.
- Include a "what this benchmark cannot tell you" paragraph.
- Present an error taxonomy with examples.
