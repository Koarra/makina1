# KycState Flattening — Overview

## What changed

- **Removed** `kyc_checks_output: Dict` from `KycState` — a single opaque dict that held all check results nested two levels deep.
- **Added** `CheckResult` TypedDict (`status: bool`, `reason: str`) — a typed, minimal container for each check result.
- **Each check section** is now a direct, typed field on `KycState` (e.g. `purpose_of_business_relationships: CheckResult`).
- **`display_name`** was removed from `CheckResult` and moved into `OutputWriter`, where it belongs.
- **`_init_kyc_checks_output()`** in the orchestrator was replaced by `_init_check_fields()` and `_build_kyc_checks_output()` to separate initialisation from output reconstruction.

## Why it is better

- **Type safety** — every check field is now `CheckResult`, not an untyped `Dict`. IDEs and type checkers can catch wrong field names and missing keys.
- **No hidden nesting** — previously, reading or writing a check required knowing two levels of keys (`state["kyc_checks_output"]["purpose_of_business_relationships"]["status"]`). Now it is one level (`state["purpose_of_business_relationships"]["status"]`).
- **Separation of concerns** — `run_section_*` functions now receive only the dict they actually need (`check: dict`) instead of the entire `kyc_checks_output`. Each function has a clear, minimal interface.
- **Consistent with `EddState`** — `EddState` was already flat. `KycState` now follows the same pattern, making the two states easier to understand side by side.
- **Display metadata out of state** — `display_name` was a static UI label stored in runtime state. Moving it to `OutputWriter` keeps the state layer free of presentation concerns.
- **Easier to extend** — adding a new check section now means adding one typed field to `KycState`, one initialisation entry, and one `run_section_*` function. Nothing else needs to know about a central `kyc_checks_output` dict.
