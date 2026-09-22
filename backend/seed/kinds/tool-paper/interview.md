# Interview rounds

Each round produces a handful of concrete questions. The model reads the system spec,
skips what the spec already answers, and asks only what is missing. Every answer becomes
a paragraph in `interview.md` and, where it contains a name or number, a line in
`facts.md`.

## Round 1: Users and problem

- Who uses the tool? Role, expertise, context of use.
- What do they do today without it? Which step hurts most, and how often?
- One concrete scenario, with a realistic input and the outcome the user wants.
- What would make a user abandon the tool?

## Round 2: Existing approaches

- Which tools or methods come closest? Name them.
- What does each do well, and where exactly does it fall short for these users?
- Is there a reason nobody built this before? A new enabling technology, a new need?

## Round 3: Design decisions

- The two or three decisions that define the tool. For each: what was the alternative,
  why was it rejected?
- What was surprisingly hard to get right?
- Which parts are generic and which are specific to this domain?

## Round 4: Evaluation

- What was actually done to test the tool? Users, cases, benchmarks, expert review,
  or nothing beyond demos. Be exact.
- How many participants or cases? Who were they and how were they recruited?
- What was measured and how? Time, correctness, satisfaction, adoption?
- The headline result in one sentence with a number.
- What did not work or gave mixed results?

## Round 5: Limitations, availability and claims

- What can the tool not do that a reader would assume it does?
- Threats to validity: who might the results not generalise to, and why?
- Where is the tool available? Licence, version, dependencies.
- The single sentence a reader should remember after reading the paper.
