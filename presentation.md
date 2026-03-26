# KYC Pipeline Refactoring: main vs old_main

## Overview

The `main` branch represents a significant architectural refactoring of the KYC compliance pipeline. The core change is a shift from a single shared mutable dictionary flowing through the entire pipeline to a flat, typed state structure where each compliance check is an independent field. This change was motivated by the LangGraph state management model and improves clarity, debuggability, and correctness.

---

## 1. State Architecture

### What changed
**old_main** passed a single `kyc_checks_output` dictionary through every node and every section function. All checks were nested inside it:

```python
# old_main
kyc_checks_output["purpose_of_business_relationships"]["status"] = False
kyc_checks_output["family_situation"]["reason"] += "..."
```

**main** flattens this into individual typed fields at the top level of `KycState`:

```python
# main
purpose_of_business_relationships: CheckResult
origin_of_asset: CheckResult
family_situation: CheckResult
consistency_checks_within_kyc_contradiction_checks: CheckResult
scap_flags: CheckResult
siap_flags: CheckResult
# ...
```

### Why it changed
LangGraph's state management works best when state fields are explicit and independently addressable. A monolithic nested dict means every node technically "touches" the entire output object, making it impossible to reason about which node is responsible for which part of the state. Flattening makes ownership clear.

### Benefits
- **Explicit ownership**: each graph node returns only the field it is responsible for — no accidental mutations of other checks.
- **Type safety**: `CheckResult` is a typed structure (`status: bool`, `reason: str`), so Pyright and mypy can catch type errors at development time rather than at runtime.
- **Easier debugging**: when a check fails, the relevant field is immediately identifiable in the state snapshot without navigating a nested dict.
- **Parallelism-ready**: independent flat fields can be computed in parallel graph branches without shared-state conflicts.

### Cons / Trade-offs
- **OutputWriter compatibility**: the OutputWriter still expects the old nested dict format. A `_build_kyc_checks_output()` reconstruction step was added to bridge the two formats, which adds a layer of indirection.
- **More boilerplate in node wrappers**: each node function must explicitly extract and return its specific state field.

---

## 2. Section Function Signatures

### What changed
Every section runner function changed its primary parameter from `kyc_checks_output: dict` (the full nested output dict) to `check: dict` (a single isolated check object).

```python
# old_main
def run_section_family_situation(
    ..., kyc_checks_output: dict, ...
):
    kyc_checks_output["family_situation"]["status"] = False

# main
def run_section_family_situation(
    ..., check: dict, ...
):
    check["status"] = False
```

### Why it changed
Passing the full output dict to every function allowed any function to accidentally read or write any other check's data. Passing only the relevant `check` object enforces a clear contract: this function only touches this check.

### Benefits
- **Reduced coupling**: functions are self-contained and do not depend on the structure of the full output dict.
- **Easier testing**: a section function can be unit-tested by passing a simple `{"status": True, "reason": ""}` dict without constructing the entire pipeline state.
- **Cleaner function signatures**: the intent of each parameter is unambiguous.

### Cons
- Minor refactoring cost; all call sites had to be updated.

---

## 3. Agent Orchestrator

### What changed
- `_init_kyc_checks_output()` was renamed to `_init_check_fields()` and now initialises individual state fields spread into the graph state.
- `_build_kyc_checks_output()` was added to reconstruct the legacy dict at the end of the pipeline for OutputWriter.
- EDD (Enhanced Due Diligence) analysis is now **optional**: if no `DD-*.txt` file is found, the pipeline logs a warning and continues in KYC-only mode. In old_main, a missing EDD file would raise an error and halt the pipeline.
- Scenario handling is now explicit: `"EDD + KYC"`, `"EDD only"`, `"KYC only"`, `"nothing to process"`.

### Why it changed
In practice, not all cases come with an EDD document. Making EDD optional avoids hard failures on valid KYC-only inputs and makes the pipeline more robust in production.

### Benefits
- **Resilience**: the pipeline no longer crashes on missing EDD files; it degrades gracefully.
- **Explicit scenarios**: the four processing scenarios are named and handled separately, making the orchestration logic easier to read and extend.
- **Separation of concerns**: initialisation and reconstruction are clearly separated steps.

### Cons
- The reconstruction step (`_build_kyc_checks_output`) is a compatibility shim that should eventually be removed by updating OutputWriter to consume the flat state directly.

---

## 4. File Organisation

### What changed
Processing utilities (`sow2json.py`, `total_assets.py`, `total_income.py`) were moved from the root directory into a dedicated `processing/` subdirectory in `main/`.

### Why it changed
Root-level clutter makes it harder to understand the project structure at a glance. Grouping related processing scripts into a subdirectory signals their shared purpose.

### Benefits
- Cleaner project layout.
- Easier to find processing logic without scanning all root-level files.

---

## 5. What Did Not Change

The following files are identical between `main` and `old_main`:
- `kyc_pydantic_schemas.py` — Pydantic output models unchanged.
- `kyc_prompts.py` — All LLM prompts unchanged.
- `kyc_agent_output.py` — The LangGraph agent graph structure unchanged.
- `output_writer.py` — Report generation logic unchanged.

The business logic (what is checked and how LLM calls are structured) is fully preserved. The refactoring is purely architectural.

---

## Summary

| Area | old_main | main | Verdict |
|------|----------|------|---------|
| State structure | Single nested dict | Flat typed fields | Better |
| Function signatures | Full output dict passed everywhere | Isolated check dict per function | Better |
| EDD handling | Required, crashes if missing | Optional, graceful fallback | Better |
| OutputWriter compatibility | Native | Requires reconstruction shim | Neutral (temporary) |
| File organisation | Flat root directory | `processing/` subdirectory | Better |
| Business logic | Unchanged | Unchanged | Neutral |

The `main` architecture is strictly better for maintainability, testability, and correctness. The only short-term cost is the `_build_kyc_checks_output()` shim, which is a known technical debt item to resolve by updating the OutputWriter.
