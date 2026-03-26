# KycState Flattening — Code Changes

---

## 1. `kyc_agent/kyc_state.py`

### Before
```python
class KycState(TypedDict, total=False):
    ...
    kyc_checks_output: Dict        # all check results nested inside one dict
    activity: Dict                 # untyped
    family_situation: Dict         # untyped
    purpose_of_business_relationships: Dict
    origin_of_asset: Dict
    total_assets: Dict
    remarks_on_total_assets_and_composition: Dict
    consistency_checks_within_kyc_contradiction_checks: Dict
    scap_flags: Dict
```

### After
```python
class CheckResult(TypedDict, total=False):
    status: bool
    reason: str

class KycState(TypedDict, total=False):
    ...
    purpose_of_business_relationships: CheckResult
    origin_of_asset: CheckResult
    total_assets: CheckResult
    remarks_on_total_assets_and_composition: CheckResult
    activity: CheckResult
    family_situation: CheckResult
    consistency_checks_pep_asm: CheckResult      # was missing before
    consistency_checks_within_kyc_contradiction_checks: CheckResult
    scap_flags: CheckResult
    siap_flags: CheckResult                      # was missing before
    siap_checks: Dict
```

**Why:** `kyc_checks_output` is gone. Each check is a first-class typed field. `consistency_checks_pep_asm`, `siap_flags`, and `siap_checks` were returned by nodes but absent from the state definition — now they are declared. `display_name` was removed entirely (see section 4).

---

## 2. `kyc_agent/kyc_checks_nodes.py`

### `run_section_*` functions — signature change

**Before:** every function received the full `kyc_checks_output` dict and accessed the nested key.
```python
def run_section_purpose_of_business_relationship(
    ..., kyc_checks_output: dict, ...
):
    kyc_checks_output["purpose_of_business_relationships"]["status"] = False
    kyc_checks_output["purpose_of_business_relationships"]["reason"] += "..."
```

**After:** each function receives only the dict it writes to.
```python
def run_section_purpose_of_business_relationship(
    ..., check: dict, ...
):
    check["status"] = False
    check["reason"] += "..."
```

The same pattern applies to all sections: 4, 6, 7, 8, 10, 11.1, 11.2, 13.

### `run_siap_check` — special case

**Before:**
```python
def run_siap_check(partner_info, partner_name, kyc_checks_output: dict):
    kyc_checks_output["siap_flags"]["raw_data"].update({partner_name: siap_results})
```

**After:**
```python
def run_siap_check(partner_info, partner_name, siap_checks: dict):
    siap_checks.update({partner_name: siap_results})
```

`siap_checks` in state directly holds the raw data — no intermediate `siap_flags["raw_data"]` wrapping.

### `node_section_*` functions — call site change

**Before:** passed `kyc_checks_output=state["kyc_checks_output"]`, then extracted the specific field on return.
```python
def node_section3_purpose_of_br(state, llm):
    run_section_purpose_of_business_relationship(
        ..., kyc_checks_output=state["kyc_checks_output"], ...
    )
    return {
        **state,
        "purpose_of_business_relationships": state["kyc_checks_output"]["purpose_of_business_relationships"],
    }
```

**After:** passes the specific check field directly; return is symmetrical.
```python
def node_section3_purpose_of_br(state, llm):
    run_section_purpose_of_business_relationship(
        ..., check=state["purpose_of_business_relationships"], ...
    )
    return {**state, "purpose_of_business_relationships": state["purpose_of_business_relationships"]}
```

### `run_section_activity` — guard removed

The old code checked `if "activity" in kyc_checks_output` as a defensive guard. This was only needed because `kyc_checks_output` was a shared mutable dict that might not have been initialised yet. With individual state fields this guard is meaningless and was removed.

---

## 3. `agent_orchestrator.py`

### `_init_kyc_checks_output()` → `_init_check_fields()`

**Before:** built a nested dict keyed by check names, each with `status`, `reason`, `display_name`.
```python
def _init_kyc_checks_output(self) -> dict:
    kyc_checks_output = {}
    for check_name, display_name in DICT_KYC_CHECKS_NAME_DISPLAY.items():
        kyc_checks_output[check_name] = {
            "status": True, "reason": "", "display_name": display_name,
        }
    kyc_checks_output["siap_flags"].update({"raw_data": {}})
    return kyc_checks_output
```

**After:** builds a flat dict keyed by state field names, each with only `status` and `reason`. Handles the `percentage_total_assets_explained` → `total_assets` name mismatch explicitly.
```python
def _init_check_fields(self) -> dict:
    check_name_to_state_key = {"percentage_total_assets_explained": "total_assets"}
    check_fields = {}
    for check_name in DICT_KYC_CHECKS_NAME_DISPLAY:
        state_key = check_name_to_state_key.get(check_name, check_name)
        check_fields[state_key] = {"status": True, "reason": ""}
        if check_name in OUT_OF_SCOPE_CHECKS:
            check_fields[state_key]["reason"] = "Out of scope currently."
    check_fields["siap_checks"] = {}
    return check_fields
```

### Added `_build_kyc_checks_output()`

Reconstructs the legacy `{check_name: {status, reason}}` dict that `OutputWriter` expects, from the flat `final_kyc_state`. This preserves backward compatibility without leaking the old structure into the state.
```python
def _build_kyc_checks_output(self, final_kyc_state: dict) -> dict:
    check_name_to_state_key = {"percentage_total_assets_explained": "total_assets"}
    result = {}
    for check_name in DICT_KYC_CHECKS_NAME_DISPLAY:
        state_key = check_name_to_state_key.get(check_name, check_name)
        result[check_name] = final_kyc_state.get(state_key, {})
    if "siap_flags" in result:
        result["siap_flags"] = {
            **result.get("siap_flags", {}),
            "raw_data": final_kyc_state.get("siap_checks", {}),
        }
    return result
```

### Partner loop — state init and result collection

**Before:** passed a single `kyc_checks_output` object (shared reference, mutated in-place across partners).
```python
kyc_checks_output = self._init_kyc_checks_output()
for partner_name_edd in edd_partner_names:
    initial_kyc_state = {..., "kyc_checks_output": kyc_checks_output}
    final_kyc_state = kyc_agent.invoke(initial_kyc_state)
    self.kyc_results[partner_name_edd] = copy.deepcopy(final_kyc_state["kyc_checks_output"])
```

**After:** spreads individual check fields; carries them forward explicitly after each partner.
```python
current_check_fields = self._init_check_fields()
for partner_name_edd in edd_partner_names:
    initial_kyc_state = {..., **current_check_fields}
    final_kyc_state = kyc_agent.invoke(initial_kyc_state)
    current_check_fields = {k: final_kyc_state[k] for k in current_check_fields if k in final_kyc_state}
    self.kyc_results[partner_name_edd] = copy.deepcopy(self._build_kyc_checks_output(final_kyc_state))
```

Accumulation across partners is preserved: each partner's graph run receives the check fields as updated by the previous partner.

---

## 4. `output_writer.py` — `display_name` moved here

**Before:** `display_name` was read out of the check dict (where it had been stored at init time).
```python
display_name = value.get("display_name", key.replace("_", " ").capitalize())
```

**After:** looked up directly from `DICT_KYC_CHECKS_NAME_DISPLAY` at render time.
```python
from main.constants import DICT_KYC_CHECKS_NAME_DISPLAY, OUTPUT_FOLDER
...
display_name = DICT_KYC_CHECKS_NAME_DISPLAY.get(key, key.replace("_", " ").capitalize())
```

`display_name` never enters the state at all. `CheckResult` stays clean: only `status` and `reason`.
