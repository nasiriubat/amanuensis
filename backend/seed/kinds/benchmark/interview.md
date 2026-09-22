# Interview rounds

## Round 1: Task and motivation

- The task in one paragraph: input, output, what counts as correct.
- Why does measuring this matter, and to whom?
- Which existing benchmarks cover it, and what is wrong with each? Be specific:
  saturated, leaked, too small, unrealistic.

## Round 2: Construction

- Where does the data come from? Licences of the sources.
- How was it collected, filtered and cleaned? Any manual steps?
- Annotation: who annotated, with what instructions, and what was the agreement?
- How were splits made? What was done to check for contamination?
- Dataset statistics: size, splits, label distribution, length distribution.

## Round 3: Protocol

- Which metrics, and why those? What do they miss?
- How were baselines chosen? How were they tuned, and with what budget?
- How many runs or seeds per configuration?
- Hardware and time per run.

## Round 4: Results and analysis

- The main results table in words: which baseline leads and by how much, with
  variance.
- Per-category or per-difficulty results worth reporting.
- Error categories observed, with one example each.
- Where do all methods fail?

## Round 5: Limits and release

- What can this benchmark not tell a user?
- Known biases in the data.
- How long before it saturates, and what would you do then?
- Release: URL, licence, evaluation harness, leaderboard plans.
