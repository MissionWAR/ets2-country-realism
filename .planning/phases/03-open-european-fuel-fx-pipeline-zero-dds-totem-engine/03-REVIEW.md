---
phase: 03-open-european-fuel-fx-pipeline-zero-dds-totem-engine
reviewed: 2026-11-21T22:57:00Z
depth: deep
files_reviewed: 51
files_reviewed_list:
  - .github/workflows/phase-a-release.yml
  - pyproject.toml
  - state/prices.lock.json
  - data/baselines/ets2_1.62_def/fuel_boards.json
  - data/baselines/ets2_1.62_def/manifest.json
  - src/ets2v2/baseline/extractor.py
  - src/ets2v2/baseline/models.py
  - src/ets2v2/cli.py
  - src/ets2v2/fetch/__init__.py
  - src/ets2v2/fetch/ec_bulletin.py
  - src/ets2v2/fetch/fx.py
  - src/ets2v2/fetch/http.py
  - src/ets2v2/fetch/models.py
  - src/ets2v2/fetch/national.py
  - src/ets2v2/fetch/pipeline.py
  - src/ets2v2/normalize/__init__.py
  - src/ets2v2/normalize/currencies.py
  - src/ets2v2/normalize/fuel.py
  - src/ets2v2/normalize/fx.py
  - src/ets2v2/normalize/lockfile.py
  - src/ets2v2/normalize/models.py
  - src/ets2v2/normalize/totem_catalog.py
  - src/ets2v2/normalize/totem_format.py
  - src/ets2v2/package/__init__.py
  - src/ets2v2/package/builder.py
  - src/ets2v2/package/metadata.py
  - src/ets2v2/package/totems.py
  - src/ets2v2/publish/changelog.py
  - src/ets2v2/publish/release.py
  - src/ets2v2/registry/snapshot.py
  - src/ets2v2/sii/sign_board.py
  - src/ets2v2/validate/__init__.py
  - src/ets2v2/validate/invariants.py
  - src/ets2v2/validate/workshop.py
  - tests/test_baseline_contracts.py
  - tests/test_cli_scaffold.py
  - tests/test_fetch_fuel.py
  - tests/test_fetch_fx.py
  - tests/test_fetch_pipeline.py
  - tests/test_normalize_fuel.py
  - tests/test_normalize_fx.py
  - tests/test_package_builder.py
  - tests/test_package_icons_metadata.py
  - tests/test_publish_release.py
  - tests/test_publish_workflow.py
  - tests/test_registry_snapshot.py
  - tests/test_sii_boards_locales.py
  - tests/test_totem_compiler.py
  - tests/test_totem_formatting.py
  - tests/test_validate_invariants.py
  - tests/test_validate_workshop.py
findings:
  critical: 0
  high: 4
  medium: 6
  low: 5
  warning: 11
  info: 3
  total: 18
status: resolved
resolved: 2026-11-22T10:02:00Z
---

# Phase 03: Code Review Report

**Reviewed:** 2026-11-21T22:57:00Z
**Depth:** deep (ASVS Level 2 + cross-file correctness & architecture audit)
**Files Reviewed:** 51 (plus AST import-graph verification across all `src/ets2v2/` layers, `# type: ignore` scan, clean-room `data/`/`state/` audit, live reproduction of parser/pipeline exceptions, and 460-board width-budget stress testing)
**Status:** issues_found

## Summary

Deep adversarial code and ASVS Level 2 security review of all Phase 3 changes (`git diff master..HEAD`, Plans `03-01`..`03-04`) covering the offline currency/FX/fuel/totem normalization layer (`normalize/`), online HTTPS/XML/OOXML collectors and fetch orchestrator (`fetch/`), Zero-DDS 460-board / 43-locale totem compiler (`package/totems.py` + `builder.py` + `metadata.py`), sign-board parser & baseline schema (`sii/sign_board.py`, `baseline/`), snapshot/changelog/release integration (`registry/snapshot.py`, `publish/`), Offline SCS Workshop Validator totem & zero-DDS invariants (`validate/`), CLI (`cli.py`), `state/prices.lock.json`, `pyproject.toml`, and `.github/workflows/phase-a-release.yml`.

Note on reference docs: `~/.gemini/antigravity/gsd-core/references/necessity-review.md` and `~/.gemini/antigravity/gsd-core/references/cicd-review-patterns.md` were unreadable due to sandbox path protection boundaries. Per review rules, `necessity:` is omitted from frontmatter, and CI/CD review used the built-in pipeline checklist.

**Key positive verifications:**
- **All 4 AST DAG isolation walls hold with zero violations:** `validate` has zero imports from `package`/`normalize`/`fetch`/`registry`/`publish`; `normalize` has zero imports from `fetch`/`registry`/`package`/`validate`/`publish`; `package` and `publish` have zero imports from `fetch`; `registry` has zero imports from `fetch`/`package`/`validate`/`publish`.
- **Strict typing discipline holds:** zero `# type: ignore` or `# pyright: ignore` suppressions anywhere under `src/ets2v2/`.
- **Clean-room JSON & LF boundary holds:** zero `.sii`/`.sui`/`.dds`/`.tobj`/`.scs` files under `data/` or `state/`, all 4 baseline SHA-256 checksums in `data/baselines/ets2_1.62_def/manifest.json` match byte-for-byte, and `state/prices.lock.json` covers all 39 European territories + 17 currencies with UTF-8 no-BOM LF hygiene.
- **Secret isolation in workflow & Tankerkönig collector is sound:** `TANKERKOENIG_API_KEY` is passed strictly via step-level `env:` (never interpolated into `run:`), scrubbed with both `redact_url_secrets()` and `.replace(resolved_key, "***")`, and zero GitHub Actions `${{ ... }}` expressions appear inside any `run:` block.
- **460-board classification & 43-locale sync on current seed prices are clean:** `gas_empty` spacer and 5 highway signs excluded, `fr_ca` present / `fr_qc` forbidden, `Decimal` `ROUND_HALF_UP` carry cases (`1.7996 -> 1.80<sup>0</sup>`, `RO 9.996 -> 10.0`, `MK 99.996 -> 100.0`) verified exact.

**Blocking defects requiring fixes before ship (0 CRITICAL, 4 HIGH):**
1. **`HI-01` (HIGH / BLOCKER):** `src/ets2v2/fetch/ec_bulletin.py:266-280` passes untrusted `.xlsx` bytes directly to `openpyxl.load_workbook()` without ZIP-bomb (uncompressed size / entry count) or OOXML `<!DOCTYPE`/`<!ENTITY` pre-inspection, letting a tiny compressed `.xlsx` (verified: 6.4 KB -> 5 MB, 773× ratio) bypass `EC_WOB_MAX_XLSX_BYTES` and `EC_WOB_MAX_ROWS`.
2. **`HI-02` (HIGH / BLOCKER):** `src/ets2v2/fetch/ec_bulletin.py:395-402,500,539-540,580-586` and `src/ets2v2/fetch/national.py:290,819` omit `zipfile.BadZipFile`, `ET.ParseError`, `OverflowError`/`OSError`, and `csv.Error` from collector exception handlers — verified that an HTTP 200 HTML error page on EC WOB or a millisecond `ts` on `fuel-prices.eu` crashes the entire `ets2v2 fetch` pipeline uncaught.
3. **`HI-03` (HIGH / BLOCKER):** `src/ets2v2/fetch/pipeline.py:312-395` merges all feeds into `merged_grades[iso2]` before bounds/WoW validation, allowing a single corrupt grade in a lower-precedence feed (e.g. EC WOB `lpg`) to invalidate valid Tier 1 national quotes (e.g. `de_tankerkoenig`) and preventing a rejected national quote from falling back to a healthy live EC WOB quote.
4. **`HI-04` (HIGH / BLOCKER):** `src/ets2v2/normalize/totem_format.py:251-281` lacks `< 100 -> XX.XX` / `>= 100 -> XXX.X` adaptive formatting for Turkey (`TR`) (and `CZ`), causing 10 of 18 Turkish fuel boards to exceed SDF width budgets and hard-crash `package build` / `publish release` as soon as TRY fuel crosses `100.00 TRY/L` (well within `CURRENCY_SANITY_BANDS["TRY"] = (15.0, 120.0)`).

## Narrative Findings (AI reviewer)

## High Issues

### HI-01: Missing OOXML ZIP-bomb and XML-declaration pre-validation in `parse_ec_wob_xlsx()` [HIGH / BLOCKER]

**File:** `src/ets2v2/fetch/ec_bulletin.py:266-280` (ASVS V12.1.2 / V5.5.2)
**Issue:** `parse_ec_wob_xlsx()` checks only the *compressed* `.xlsx` byte length (`len(raw_xlsx) > EC_WOB_MAX_XLSX_BYTES`, 20 MiB) and row count during `ws.iter_rows()` (`max_rows=5000`), then immediately invokes `openpyxl.load_workbook(io.BytesIO(raw_xlsx), read_only=True, data_only=True)`. Even in `read_only=True` mode, `openpyxl` fully decompresses and parses `xl/sharedStrings.xml`, `xl/styles.xml`, and `xl/workbook.xml` into memory before row iteration begins, and never enforces uncompressed size or archive entry caps. Directly reproduced: a 6,463-byte `.xlsx` containing a 5 MB `xl/sharedStrings.xml` (773× compression ratio) is fully decompressed by `parse_ec_wob_xlsx()` with `max_rows=10`. At the 20 MiB compressed cap, a malicious or compromised upstream `.xlsx` can expand to multi-gigabyte XML and OOM the CI runner. Furthermore, OOXML XML members are not pre-scanned for `<!DOCTYPE` / `<!ENTITY` declarations (unlike `parse_xml_safe()` in `fetch/http.py`).
**Fix:** Pre-validate the OOXML ZIP container before calling `openpyxl.load_workbook()`:
```python
EC_WOB_MAX_UNCOMPRESSED_BYTES: Final[int] = 67_108_864  # 64 MiB
EC_WOB_MAX_ZIP_ENTRIES: Final[int] = 256
_XML_FORBIDDEN_DECL_BYTES_RE: Final[re.Pattern[bytes]] = re.compile(
    rb"<!(?:DOCTYPE|ENTITY)\b",
    flags=re.IGNORECASE,
)

def _validate_ooxml_zip_safety(raw_xlsx: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_xlsx), "r") as zf:
            infos = zf.infolist()
            if len(infos) > EC_WOB_MAX_ZIP_ENTRIES:
                raise ValueError(f"OOXML archive entry count {len(infos)} exceeds cap")
            total_uncompressed = 0
            for info in infos:
                if info.flag_bits & 0x41:
                    raise ValueError(f"Encrypted OOXML entry {info.filename!r} is disallowed")
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise ValueError(f"Unsupported OOXML compression method {info.compress_type}")
                if info.file_size > EC_WOB_MAX_UNCOMPRESSED_BYTES:
                    raise ValueError(f"OOXML entry {info.filename!r} exceeds uncompressed byte cap")
                with zf.open(info, "r") as member:
                    # Stream-read with hard cap (do not trust ZipInfo.file_size header alone)
                    data = member.read(EC_WOB_MAX_UNCOMPRESSED_BYTES - total_uncompressed + 1)
                total_uncompressed += len(data)
                if total_uncompressed > EC_WOB_MAX_UNCOMPRESSED_BYTES:
                    raise ValueError("OOXML total uncompressed payload exceeds safety cap")
                if info.filename.lower().endswith((".xml", ".rels")) and _XML_FORBIDDEN_DECL_BYTES_RE.search(data):
                    raise ValueError(f"Forbidden DOCTYPE/ENTITY in OOXML member {info.filename!r}")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid OOXML ZIP archive: {exc}") from exc
```

---

### HI-02: Uncaught `zipfile.BadZipFile`, `ET.ParseError`, `OverflowError`/`OSError`, and `csv.Error` break feed fault isolation and crash `ets2v2 fetch` [HIGH / BLOCKER]

**File:** `src/ets2v2/fetch/ec_bulletin.py:395-402,500,539-540,580-586`, `src/ets2v2/fetch/national.py:290,819`
**Issue:** Fault-isolated collectors promise that any single malformed or unavailable upstream feed returns `RawFuelFeedResult(ok=False)` so fallback collectors and lockfile retention can proceed. Several collectors omit non-`ValueError` stdlib parser exceptions:
1. `fetch_ec_weekly_oil_bulletin()` (`ec_bulletin.py:395-402`) catches `(HttpFetchError, httpx.HTTPError, ValueError, KeyError, OSError, InvalidFileException)`, omitting `zipfile.BadZipFile` (inherits directly from `Exception`) and `xml.etree.ElementTree.ParseError` (inherits from `SyntaxError`). Directly reproduced: when EC's landing/download URL serves an HTTP 200 HTML maintenance/WAF page (`<html>503 Maintenance</html>`), `openpyxl.load_workbook()` raises an uncaught `zipfile.BadZipFile: File is not a zip file`, aborting the entire `ets2v2 fetch` run instead of falling back to `fionnhughes_ec_wob`.
2. `fetch_fuel_prices_eu()` (`ec_bulletin.py:539-540,580-586`) calls `datetime.fromtimestamp(float(ts_val), tz=UTC)` without checking `math.isfinite(ts_val)` or catching `(OverflowError, OSError)`. Directly reproduced: a Unix-millisecond timestamp (`"ts": 1763618400000`) raises an uncaught `OSError: [Errno 22] Invalid argument` (Windows) / `OverflowError` (Linux), crashing the entire pipeline.
3. `fetch_uk_desnz()` (`national.py:290`), `fetch_it_mimit()` (`national.py:819`), and `fetch_fionnhughes_fallback()` (`ec_bulletin.py:500`) omit `csv.Error` (inherits directly from `Exception`), which is raised on malformed CSV quoting or embedded NUL bytes (`\x00`) in raw CSV streams.
**Fix:**
- Add `zipfile.BadZipFile` and `ET.ParseError` to `fetch_ec_weekly_oil_bulletin()`'s `except` tuple (and convert `BadZipFile` to `ValueError` in `_validate_ooxml_zip_safety()`).
- In `fetch_fuel_prices_eu()`, validate `math.isfinite(ts_val) and 0 < ts_val < 4_102_444_800` (year 2100) before `datetime.fromtimestamp()`, and add `OverflowError`, `OSError` to its `except` tuple.
- Add `csv.Error` to the `except` tuples of `fetch_uk_desnz()`, `fetch_it_mimit()`, and `fetch_fionnhughes_fallback()`.

---

### HI-03: Cross-feed `merged_grades` contamination in `run_price_fetch()` lets corrupt grades poison valid Tier 1 data and blocks live fallback [HIGH / BLOCKER]

**File:** `src/ets2v2/fetch/pipeline.py:312-395`
**Issue:** `run_price_fetch()` merges all successful feeds into a single `merged_grades[iso2]` dictionary in ascending precedence order (`fuel_prices_eu` -> `fionnhughes_ec_wob` -> `ec_weekly_oil_bulletin` -> national Tier 1) *before* running `normalize_country_fuel_prices()`, while overwriting `winning_meta[iso2]` with only the highest-precedence feed's `(source, license, data_date, tier)`. This creates three defects:
1. **Lower-precedence corrupt grade invalidates valid Tier 1 anchor:** If `ec_weekly_oil_bulletin` has a corrupt out-of-bounds `lpg` value (e.g., `99.0 EUR/L`) for `DE`, and `de_tankerkoenig` returns valid `{"diesel": 1.66, "petrol_95": 1.76}`, `merged_grades["DE"]` still retains the corrupt `lpg` from EC WOB. `normalize_country_fuel_prices()` (`normalize/fuel.py:179-218`) rejects the entire country on `lpg`, discarding Germany's valid Tankerkönig prices!
2. **Higher-precedence bad quote blocks fallback to healthy live feed:** If `de_tankerkoenig`, `it_mimit`, or `es_miteco` returns a corrupted or `>25%` jumped quote, it overwrites valid `ec_weekly_oil_bulletin` prices in `merged_grades[iso2]` before validation. When `normalize_country_fuel_prices()` rejects it, the country falls back directly to the stale previous lockfile instead of using the healthy live `ec_weekly_oil_bulletin` quote already fetched in the same run.
3. **Provenance/staleness misattribution:** Supplemental grades kept from an older lower-precedence feed (e.g., an older EC WOB `lpg`) are stamped with today's national feed `source`, `license`, and `data_date`.
**Fix:** Store per-territory candidate quotes grouped by feed in *descending* precedence. For each `iso2`, try normalizing the highest-precedence feed's own grades first; if rejected (hard bounds or WoW jump), record the alert and fall back to the next highest-precedence live feed (e.g., `ec_weekly_oil_bulletin`) before falling back to `previous_entry`. Only merge supplemental grades (such as `lpg` from EC WOB when absent in `de_tankerkoenig`) *after* independently validating those supplemental grades against `[0.01, 5.00]` EUR/L and `±25%` WoW bounds so a bad supplemental grade is dropped individually rather than poisoning the primary Tier 1 quote.

---

### HI-04: `format_national_pump_price()` lacks `>= 100` compact formatting for Turkey (`TR`) (and `CZ`), crashing `package build` once TRY fuel reaches `100.00 TRY/L` [HIGH / BLOCKER]

**File:** `src/ets2v2/normalize/totem_format.py:251-281`
**Issue:** `format_national_pump_price()` implements adaptive width-safe formatting for `RO` (`< 10 -> X.XX`, `>= 10 -> XX.X`) and `MK` (`< 100 -> XX.XX`, `>= 100 -> XXX.X`), ensuring carry transitions (`9.996 -> 10.0`, `99.996 -> 100.0`) stay within 4-char / 5-char ETS2 1.62 totem box budgets. However, `TR` (Turkey) falls through to unconditional `:.2f` at line 280 even though **10 of 18 Turkish boards** (`gas_tr_filgas_*`, `gas_tr_petrin_*`, `gas_tr_primel_*`) have 5-character box budgets. Stress-testing all 460 boards directly proved that at `100.50 TRY/L` (e.g. `1.68 EUR/L × 60 TRY/EUR`, well inside `CURRENCY_SANITY_BANDS["TRY"] = (15.0, 120.0)` and `[0.01, 5.00]` EUR/L — `TR` is already `59.4–68.6 TRY/L` in the initial seed), `format_national_pump_price("TR", 100.50)` emits 6-character `"100.50"` (`width 1.1029 > budget 1.0184` on `gas_tr_filgas_diesel`), causing `resolve_totem_token_and_value()` to raise `ValueError` and abort every weekly `publish release` build. Similarly, 2 of 4 `CZ` boards (`gas_cz_big_95`, `gas_cz_big_diesel`) fail if `CZK` fuel ever crosses `100.00 CZK/L` (currently ~38 CZK, lower immediate risk).
**Fix:** Extend the `< 100 -> XX.XX` / `>= 100 -> XXX.X` carry-safe rule to `TR` (and clamp `CZ` to `:.1f` if `rounded_tenth >= _HUNDRED`):
```python
    if code in {"MK", "TR"}:
        q2 = dec.quantize(_QUANT_2DEC, rounding=ROUND_HALF_UP)
        if q2 < _HUNDRED:
            return f"{q2:.2f}"
        return f"{dec.quantize(_QUANT_1DEC, rounding=ROUND_HALF_UP):.1f}"

    if code == "CZ":
        rounded_tenth = dec.quantize(_QUANT_1DEC, rounding=ROUND_HALF_UP)
        if rounded_tenth < _HUNDRED:
            return f"{rounded_tenth:.2f}"
        return f"{rounded_tenth:.1f}"
```
Add a regression test in `tests/test_totem_formatting.py` verifying `TR` (`99.994 -> "99.99"`, `99.996 -> "100.0"`, `131.58 -> "131.6"`) and width-budget compliance across all 460 boards at elevated FX sanity-band rates.

---

## Medium Issues

### MD-01: IEEE-754 floating-point boundary precision errors spuriously trip exact `±25%` WoW and `2%`/`5%`/`10%` FX thresholds [MEDIUM / WARNING]

**File:** `src/ets2v2/normalize/fuel.py:248-263`, `src/ets2v2/normalize/fx.py:82-88,300,330`
**Issue:** Exact boundary comparisons use binary `float` subtraction and division against `MAX_WOW_JUMP_RATIO = 0.25` and `DIVERGENCE_REJECT_PCT = 10.0` / `MAJOR_DIVERGENCE_WARN_PCT = 2.0`:
- `normalize/fuel.py:248-249`: For `1.20 -> 1.50` (exact `+25.0%`), `abs(1.5 - 1.2) / 1.2 == 0.25000000000000006 > 0.25` evaluates `True` and spuriously triggers `price_jump_rejected`. Same for `1.40 -> 1.75` (`0.25000000000000006`) and `2.20 -> 1.65` (`0.2500000000000001`).
- `normalize/fx.py:88,300,330`: For `1.00` vs `1.10` (exact `10.0%`), `abs(1.10 - 1.00) / 1.00 * 100.0 == 10.000000000000009 > 10.0` evaluates `True` and spuriously triggers `fx_divergence_rejected`; `1.00` vs `1.02` (`2.0000000000000018 > 2.0`) spuriously triggers `fx_divergence_warning`.
**Fix:** Use exact `Decimal(str(...))` arithmetic for threshold checks:
```python
# normalize/fuel.py
def _exceeds_wow_jump(prev_val: float, new_val: float) -> tuple[bool, float]:
    prev_d = Decimal(str(prev_val))
    new_d = Decimal(str(new_val))
    ratio = abs(new_d - prev_d) / prev_d
    return ratio > Decimal(str(MAX_WOW_JUMP_RATIO)), float(ratio)

# normalize/fx.py
def compute_divergence_pct(rate_a: float, rate_b: float) -> float:
    ...
    da = Decimal(str(rate_a))
    db = Decimal(str(rate_b))
    pct = (abs(da - db) / min(da, db)) * Decimal("100")
    return float(pct)
```

---

### MD-02: `discover_ec_wob_xlsx_url()` silently downloads `"Prices without taxes"` ex-tax workbook when `"Prices with taxes"` link is absent [MEDIUM / WARNING]

**File:** `src/ets2v2/fetch/ec_bulletin.py:169-189,282-287`
**Issue:** `discover_ec_wob_xlsx_url()` applies only a `-8` penalty for `"without taxes"` against `.xlsx (+5) + /document/download/ (+4) + weekly/bulletin (+2) = +11`, yielding a positive net score of `+3`. Directly reproduced: when the landing page contains only the `"Prices without taxes"` link (e.g., during EC Drupal CMS updates), `discover_ec_wob_xlsx_url()` returns the ex-tax `.xlsx` URL instead of raising `ValueError` to trigger `fionnhughes_ec_wob` fallback. Similarly, `parse_ec_wob_xlsx()` (`ec_bulletin.py:282-287`) only sorts `"without"` worksheets behind `"price"` worksheets instead of skipping them, so an ex-tax sheet is parsed as consumer pump prices (~50% lower than real pump prices).
**Fix:** Hard-skip (`continue`) any anchor containing `"without tax"`, `"without_tax"`, `"excl"`, or `"net price"` in `discover_ec_wob_xlsx_url()`, and skip any worksheet whose lowercase name contains `"without"` or `"net"` in `parse_ec_wob_xlsx()`.

---

### MD-03: `validate_https_url()` permits non-443 ports and `fetch_bytes_with_retry()` can leak unredacted `httpx.DecodingError`/`httpx.StreamError` [MEDIUM / WARNING]

**File:** `src/ets2v2/fetch/http.py:49-62,160-167` (ASVS V13.2.5 / V7.1.1)
**Issue:**
1. `validate_https_url()` checks `parsed.scheme == "https"` and `parsed.hostname in allowed_hosts`, but does not check `parsed.port`. A redirect or HTML-discovered link like `https://energy.ec.europa.eu:8443/...` bypasses port restriction.
2. `fetch_bytes_with_retry()` catches `httpx.TransportError` at line 160, but `httpx.DecodingError` and `httpx.StreamError` inherit from `httpx.RequestError` (not `TransportError`). If an upstream endpoint returns malformed gzip/brotli framing, `httpx.DecodingError` escapes `fetch_bytes_with_retry()` without passing through `redact_url_secrets()` (which is defense-in-depth for `apikey=` query parameters).
**Fix:** Enforce `if parsed.port not in (None, 443): raise ValueError(f"Non-standard HTTPS port {parsed.port} is not permitted")` in `validate_https_url()`, and catch `(httpx.TransportError, httpx.DecodingError, httpx.StreamError)` in `fetch_bytes_with_retry()`, wrapping non-retryable decoding errors in `HttpFetchError(redact_url_secrets(str(exc))) from None`.

---

### MD-04: Offline Validator omits `<sup>` 7-segment font compatibility audit and allows rogue `locale/fuel_price_strings.sui` [MEDIUM / WARNING]

**File:** `src/ets2v2/validate/invariants.py:545-586,663-670`, `src/ets2v2/validate/workshop.py:1019-1100`
**Issue:**
1. `validate_totem_invariants()` validates `_TOTEM_VALUE_RE` on `local_module.ets2v2_fuel.sii` entries and validates board attributes independently, but never cross-checks that boards using the 2 non-`<sup>` fonts (`gas_segment_7_standard.font`, `gas_sign_digit.font`) do not reference a token whose value contains `<sup>`. A regression emitting `1.78<sup>9</sup>` onto a 7-segment board passes the Offline Validator cleanly while printing literal `"<sup>9</sup>"` markup on roadside totems in ETS2.
2. `_validate_package_contents()` in `validate/workshop.py` forbids `def/country.sii` (`_COUNTRY_SII_RE`), but permits `locale/fuel_price_strings.sui` or `locale/<lang>/localization.sui` (both match `.sui` in `ALLOWED_SCS_ASSET_EXTENSIONS` and fall through lines 1039-1100 silently), violating the Option 4b non-destructive isolation contract.
**Fix:** In `validate/invariants.py` (keeping Layer 7 isolated from `normalize`), map `canonical_token_values: dict[str, str]` from the validated reference locale and emit `ETS2V2-INV-TOTEM-BOARDS` if a board's `font_face` ends with `gas_segment_7_standard.font` or `gas_sign_digit.font` and its resolved token value contains `"<sup>"`. In `validate/workshop.py`, reject `locale/fuel_price_strings.sui` and any unexpected `locale/...` `.sii`/`.sui` file outside `locale/<lang>/local_module.ets2v2_fuel.sii` with SCS `00003`.

---

### MD-05: Unpinned GitHub Actions tags in write-scoped release workflow and unsanitized upstream `alert.detail` in Markdown PR/changelog rendering [MEDIUM / WARNING]

**File:** `.github/workflows/phase-a-release.yml:30,33,99,154-160`, `src/ets2v2/publish/changelog.py:76-79` (ASVS V14.2.1 / V5.2.1)
**Issue:**
1. `.github/workflows/phase-a-release.yml` holds `contents: write`, `pull-requests: write`, and `secrets.TANKERKOENIG_API_KEY`, yet references mutable major tags (`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/upload-artifact@v4`) rather than immutable 40-character commit SHAs.
2. Both `phase-a-release.yml:158-159` and `publish/changelog.py:78` interpolate raw `alert.detail` (populated from upstream HTTP/parser errors) directly into Markdown list items without collapsing `\r`/`\n` newlines, escaping backticks/HTML, or capping length. A crafted upstream error string can inject arbitrary Markdown headings, links, or `@mentions` into the automated Release PR body and `CHANGELOG_*.md`.
**Fix:** Pin `actions/checkout`, `astral-sh/setup-uv`, and `actions/upload-artifact` to verified full commit SHAs (with `# v4` / `# v5` comments) and update `tests/test_publish_workflow.py` accordingly. Add a single-line Markdown sanitizer (`" ".join(detail.split())[:240]`, escaping `<`/`>` or backticks) when rendering `alert.detail` in `changelog.py` and `phase-a-release.yml`.

---

### MD-06: `normalize_country_fuel_prices()` raises uncaught `ValueError` on anchorless grade maps instead of holding previous lockfile entry [MEDIUM / WARNING]

**File:** `src/ets2v2/normalize/fuel.py:220`, `src/ets2v2/fetch/pipeline.py:377-395`
**Issue:** When `live_local_prices` contains only a secondary grade (e.g., `{"lpg": 0.99}`, missing both `"diesel"` and `"petrol_95"`), lines 179-218 pass hard-bounds validation and line 220 calls `compute_secondary_grade_prices(live_local_prices)`, which raises an uncaught `ValueError("live_local_prices must contain at least 'diesel' or 'petrol_95'")` (reproduced directly). Inside `run_price_fetch()` (`pipeline.py:377-394`), catching that `ValueError` misclassifies it as `price_bounds_rejected` and **overwrites the valid `previous_entry` with `baseline_1.62_seeded`** instead of holding the previous live lockfile entry.
**Fix:** Before calling `compute_secondary_grade_prices()` in `normalize_country_fuel_prices()`, check:
```python
if "diesel" not in live_local_prices and "petrol_95" not in live_local_prices:
    alerts.append(
        LockAlert(
            severity="warning",
            code="price_anchor_missing",
            scope=canonical_iso2,
            detail=(
                f"Live quote for {canonical_iso2} from {source} lacks both diesel and "
                "petrol_95 anchors; retaining previous lockfile entry."
            ),
        )
    )
    return _hold_previous(
        previous_entry,
        alerts,
        fallback_error=f"Missing diesel/petrol_95 anchor for {canonical_iso2}",
    )
```

---

## Low Issues

### LO-01: `_parse_positive_float()` misparses mixed-separator European numbers (`"1.750,50"`) and duplicates HTML/date/number helpers across modules [LOW / WARNING]

**File:** `src/ets2v2/fetch/ec_bulletin.py:115-143,192-231`, `src/ets2v2/fetch/national.py:117-180`
**Issue:** `_parse_positive_float()` checks `if "," in cleaned and "." not in cleaned:` and otherwise strips all commas. On a European thousands-dot + decimal-comma string such as `"1.750,50"` (1,750.50 EUR/1000L), it strips `,` and parses `1.7505` (1000× off). On an English thousands-comma string `"1,750"` (no decimal point), it replaces `,` with `.` and parses `1.75` (1000× off before `/ 1000.0`). In addition, `_AnchorExtractor`/`_AnchorParser`, `_parse_positive_float`, and `_extract_iso_date` are duplicated across `ec_bulletin.py` and `national.py`.
**Fix:** Extract shared parsing helpers into `src/ets2v2/fetch/_parsing.py` and handle mixed separators by comparing `cleaned.rfind(",")` vs `cleaned.rfind(".")` (when both exist, whichever appears last is the decimal separator and the other is stripped as thousands grouping).

---

### LO-02: `cross_validate_fx_rates()` skips healthy live validators when primary FX provider fails sanity bounds [LOW / WARNING]

**File:** `src/ets2v2/normalize/fx.py:221-244`
**Issue:** If `frankfurter_v2` omits a currency, lines 269-283 promote the first healthy live validator (`ecb_xml` / `cbr_xml` / `fawazahmed0`). However, if `frankfurter_v2` returns an out-of-band/corrupted value for one currency, lines 225-244 immediately call `_resolve_fallback_or_missing()` and `continue`, skipping healthy live `ecb_xml`/`cbr_xml`/`fawazahmed0` quotes and falling back straight to the stale lockfile (or failing `ok=False` on a fresh lockfile).
**Fix:** After logging the `fx_sanity_rejected` alert for the primary provider, continue to lines 246-283 with `primary_data = None` so healthy live validators can still supply and cross-validate the currency before falling back to `previous_fx`.

---

### LO-03: `parse_xml_safe()` fails on UTF-8 BOM-prefixed XML payloads [LOW / WARNING]

**File:** `src/ets2v2/fetch/http.py:173-186`
**Issue:** `parse_xml_safe()` decodes with `raw.decode(encoding)` (default `"utf-8"`). If an upstream XML feed (such as ECB or a proxy) prepends a UTF-8 BOM (`0xEF 0xBB 0xBF`), `\ufeff` remains at index 0; Python's regex `\s` does not match `\ufeff`, so `_XML_PROLOG_RE` fails to strip `<?xml ...?>` and `ET.fromstring()` raises `ParseError`.
**Fix:** Strip a leading BOM after decoding (`text = text.removeprefix("\ufeff")`) or decode using `"utf-8-sig"` when `encoding.lower() in {"utf-8", "utf8"}`.

---

### LO-04: Predictable `.tmp` filename in `write_prices_lockfile()` and missing calendar validation on `data_date` regex [LOW / WARNING]

**File:** `src/ets2v2/normalize/lockfile.py:83-90,98`, `src/ets2v2/normalize/models.py:38`, `src/ets2v2/fetch/national.py:406,874`
**Issue:**
1. `write_prices_lockfile()` writes to a fixed sibling name `path.with_name(f"{path.name}.tmp")` without `try/except` cleanup or unique suffix, risking temp-file collision under concurrent invocations or orphaned `.tmp` files on replace failure.
2. `_ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"` accepts invalid calendar dates (e.g., `"2026-99-01"` from malformed SSB `2026M99` or CBS `20269999`), which pass Pydantic validation and later crash `date.fromisoformat(entry.data_date)` in `evaluate_lockfile_staleness()` (`lockfile.py:98`).
**Fix:** Use `tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False)` with `os.unlink` cleanup on error before `os.replace()`. Add a `@field_validator("data_date")` calling `date.fromisoformat()` in `normalize/models.py` and `fetch/models.py`.

---

### LO-05: Missing `--timeout` bounds validation & stderr redaction in `_handle_fetch()`; `round_eur_per_liter()` can underflow to `0.0` [LOW / WARNING]

**File:** `src/ets2v2/cli.py:497-513`, `src/ets2v2/normalize/fx.py:55-60`
**Issue:**
1. `_handle_fetch()` in `cli.py:497-513` forwards `--timeout` without checking `math.isfinite(timeout) and timeout > 0.0` (accepting `0`, `-1`, `nan`, `inf`), and prints `str(exc)` to `stderr` without `redact_url_secrets()` as defense-in-depth.
2. `round_eur_per_liter(0.0004)` in `normalize/fx.py:55-60` passes `value > 0.0` yet quantizes to `0.0`, causing downstream `NormalizedCurrencyPrice(eur_per_liter=gt 0.0)` to fail with a Pydantic `ValidationError` instead of a clean `ValueError`.
**Fix:** Validate `math.isfinite(timeout) and timeout > 0.0` in `_handle_fetch()` and `create_http_client()`; wrap `str(exc)` with `redact_url_secrets()` in `_handle_fetch()`; raise `ValueError` in `round_eur_per_liter()` if `quantized <= 0`.

---

## Info

### IN-01: `fetch_no_ssb_09654()` assumes non-time/non-product JSON-stat2 dimensions are indexed at `0` [INFO]

**File:** `src/ets2v2/fetch/national.py:384-446`
**Issue:** `flat_idx = p_pos * strides[product_dim_pos] + t_pos * strides[time_dim_pos]` implicitly fixes every other dimension (e.g., `ContentsCode`) to index `0`. If SSB adds a leading metric to `ContentsCode` before average price, the collector will silently read the wrong series.
**Fix:** Verify all remaining dimensions have `size == 1` or explicitly resolve the price index in `ContentsCode`.

---

### IN-02: Changelog fuel price summary table omits currency / unit column [INFO]

**File:** `src/ets2v2/publish/changelog.py:25-56`
**Issue:** `_render_fuel_summary_table()` renders `| ISO2 | EUR/L Diesel | Local Diesel | Local 95 | Source | Freshness |`, displaying `142.9` (`GB` pence/L), `776` (`HU` HUF), and `10.1` (`RO` RON) without showing the currency or unit (`p/L` vs local currency code).
**Fix:** Add a `Currency` column (e.g. `GBP (p/L)` for `GB`, `country.fuel.currency` for all others).

---

### IN-03: `phase-a-release.yml` discards `dist/fetch_summary.json` alerts on canonical-hash no-op runs [INFO]

**File:** `.github/workflows/phase-a-release.yml:97-129`
**Issue:** When `ets2v2 fetch` succeeds with staleness or FX divergence alerts but rounded fuel prices do not change the canonical Workshop SHA-256, `any_changed` is `false` and both artifact upload and PR update are skipped, leaving alerts visible only in raw step logs.
**Fix:** Append alert summaries to `$GITHUB_STEP_SUMMARY` unconditionally (or upload `dist/fetch_summary.json` as a lightweight diagnostic artifact even on no-op runs).

---

## Resolution Summary (2026-11-22)

All 18 review findings (`4` HIGH, `6` MEDIUM, `5` LOW, `3` INFO) were addressed across 7 atomic commits on `gsd/phase-03-open-european-fuel-fx-pipeline-zero-dds-totem-engine` with targeted regression tests:

- `048b93f` — `HI-01`, `HI-02`, `MD-02`, `LO-01`, `IN-01` (OOXML ZIP-bomb & DOCTYPE/ENTITY pre-validation, collector fault isolation for `BadZipFile`/`ParseError`/`OverflowError`/`OSError`/`csv.Error`, ex-tax link & sheet rejection, shared `fetch/_parsing.py`, SSB dimension verification)
- `b7b5e8f` — `MD-03`, `LO-03`, `LO-05` (HTTPS port 443 restriction, `DecodingError`/`StreamError` redaction, XML BOM stripping, CLI/client `--timeout` validation & stderr redaction)
- `a3be867` — `MD-01`, `MD-06`, `LO-02`, `LO-04`, `LO-05` (`Decimal` exact WoW/FX threshold comparisons, `price_anchor_missing` lockfile hold, primary-sanity-rejection validator fallback, `NamedTemporaryFile` atomic lockfile writes, real calendar `date.fromisoformat()` validation, `round_eur_per_liter` underflow guard)
- `0a15987` — `HI-03` (per-feed descending-precedence candidate validation & isolated supplemental-grade validation in `run_price_fetch()`)
- `603c860` — `HI-04` (carry-safe `< 100 -> XX.XX` / `>= 100 -> XXX.X` formatting for `TR` and `CZ` + all-460-board elevated-FX stress sweep)
- `c095b34` — `MD-04` (non-`<sup>` 7-segment font cross-check in `validate/invariants.py` + rogue `locale/` `.sii`/`.sui` rejection in `validate/workshop.py`)
- `a5291e1` — `MD-05`, `IN-02`, `IN-03` (single-line Markdown `alert.detail` sanitization in `changelog.py` & `phase-a-release.yml`, `Currency` column in changelog fuel table, unconditional `$GITHUB_STEP_SUMMARY` alert output)

**Deferred Ops Note:** `MD-05` GitHub Actions commit-SHA pinning keeps `actions/checkout@v4`, `astral-sh/setup-uv@v5`, and `actions/upload-artifact@v4` aligned with `.github/workflows/ci.yml` rather than guessing unverified SHAs.

**Post-Fix Final Verification:** `ets2v2 baseline extract --check` (`0`), `ruff check` (`All checks passed!`), `ruff format --check` (`86 files already formatted`), `basedpyright` (`0 errors, 0 warnings, 0 notes`), and full `pytest -q --tb=short` (**390 passed**, including both `@pytest.mark.local_ets2` tests).

---

_Reviewed: 2026-11-21T22:57:00Z_
_Resolved: 2026-11-22T10:02:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
