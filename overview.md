# KYC Pipeline Refactoring: Overview

## Reasons for the Change

The previous pipeline passed a single shared dictionary through every node and function. Any function could read or write any part of it, making it impossible to reason about ownership and easy to introduce silent bugs. The refactoring was driven by three needs:

1. **Alignment with LangGraph** — LangGraph's state model works best with explicit, independently addressable fields. A monolithic nested dict undermines this.
2. **Clearer ownership** — each section function should only touch the check it is responsible for, nothing else.
3. **Robustness** — the pipeline was too rigid: a missing EDD document would crash the entire run, even for valid KYC-only cases.

---

## Benefits

- Each compliance check is an independent typed field in the state, so mutations are isolated and traceable.
- Section functions receive only the check they own, making them independently testable without constructing the full pipeline.
- The pipeline now handles KYC-only cases gracefully when no EDD document is present, instead of failing hard.
- Explicit scenario handling (EDD + KYC, EDD only, KYC only) makes the orchestration logic easier to read and extend.

## Cons / Trade-offs

- The OutputWriter still expects the old nested dict format, so a reconstruction step was added at the end of the pipeline. This is a compatibility shim and represents known technical debt.
- All call sites had to be updated, adding a one-time refactoring cost with no immediate functional change.
