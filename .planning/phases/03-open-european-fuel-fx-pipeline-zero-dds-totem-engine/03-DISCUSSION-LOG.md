# Phase 3: Open European Fuel/FX Pipeline & Zero-DDS Totem Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-21
**Phase:** 03-Open European Fuel/FX Pipeline & Zero-DDS Totem Engine
**Areas discussed:** Non-EU vanilla countries, missing fuel grades & API key fallbacks; Circuit breaker, prices.lock.json lifecycle & Friday CI wiring; Zero-DDS totem board coverage, native currency formatting & <sup>9</sup> rules; Snapshot v1 contract, .sui precision & weekly price changelogs

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Non-EU vanilla countries, missing fuel grades & API key fallbacks | How to price the 10 non-EU vanilla countries, derive missing grades (98/100/LPG/E85), and handle optional DE Tankerkönig key | ✓ |
| Circuit breaker, prices.lock.json lifecycle & Friday CI wiring | Fetch vs offline-build separation, lockfile PR updates, FX divergence / ±25% jump / staleness thresholds | ✓ |
| Zero-DDS totem board coverage, native currency formatting & `<sup>9</sup>` rules | Mapping all 461 boards (incl. 47 placeholder + 41 blank), pence/eurocents/`<sup>9</sup>`/decimal conventions, and validator checks | ✓ |
| Snapshot v1 contract, `.sui` precision & weekly price changelogs | Keeping `RealismSnapshot` `schema_version=1`, canonical `local_prices` grade keys, `fuel_price` rounding, and changelog fuel diffs | ✓ |

**User's choice:** Selected all 4 gray areas.

---

## Non-EU vanilla countries, missing fuel grades & API key fallbacks

### Question 1: Fuel pricing for the 10 non-EU/EEA vanilla ETS2 countries (`AL`, `BA`, `CH`, `IS`, `ME`, `MK`, `RS`, `RU`, `TR`, `XK`)

| Option | Description | Selected |
|--------|-------------|----------|
| Use `fuel-prices.eu` where covered + seed remaining from `1.62` baseline in `prices.lock.json` | Keeps all 36 vanilla countries coherent with live/lockfile EUR + local totem prices immediately, ready for Phase 5 Tier 2 upgrades | ✓ |
| Keep all 10 non-EU countries on ETS2 `1.62` baseline `fuel_price` in `prices.lock.json` until Phase 5 | Strict Tier 1 scope (EU27 + UK + NO live only), converting `1.62` EUR baseline via live FX for local totems | |
| You decide | Let me pick the cleanest balance for Phase 3 coverage vs Phase 5 handoff | |

**User's choice:** Use `fuel-prices.eu` where covered + seed remaining from `1.62` baseline in `prices.lock.json`.

### Question 2: Deriving missing secondary fuel grades (`98`, `100`, `Diesel+`, `E85`, `LPG`, `92`, `MPO`)

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic market spread ratios from live `95`/`Diesel` + EC `LPG` where reported | Use live multi-grade feeds (`FR`/`DE`/`ES`/`IT`/`NL`) + EC `LPG` directly, and apply small documented per-grade multipliers everywhere else so totems track weekly swings realistically | ✓ |
| Use ETS2 `1.62` baseline grade ratios (`fp_xx_98 / fp_xx_95`) applied to live `95`/`Diesel` | Anchor each country's spread to whatever ratio SCS shipped in `1.62` `locale.scs` | |
| Fall back to the nearest live base grade (`95` or `Diesel`) without spreads | Never synthesize secondary grades; show base `95` for `98`/`100` and base `Diesel` for `Diesel+` | |
| You decide | Pick the cleanest deterministic strategy for secondary grades | |

**User's choice:** Deterministic market spread ratios from live `95`/`Diesel` + EC `LPG` where reported.

### Question 3: Germany's optional `Tankerkönig` API key (`TANKERKOENIG_API_KEY`)

| Option | Description | Selected |
|--------|-------------|----------|
| Optional enrichment with keyless EC fallback | Use `Tankerkönig` when `TANKERKOENIG_API_KEY` is present in env/CI secrets (sampling a deterministic set of German cities/stations); silently fall back to EC Weekly Oil Bulletin + grade spreads when unset | ✓ |
| Skip `Tankerkönig` in Phase 3 and use EC Weekly Oil Bulletin for Germany | Avoid station-sampling variance and key management altogether | |
| Require `TANKERKOENIG_API_KEY` on live fetches (fail loudly if missing unless `--offline`) | Guarantee Germany always uses live MTS-K multi-grade data | |
| You decide | Choose the best default for zero-secret open-source CI and optional maintainer enrichment | |

**User's choice:** Optional enrichment with keyless EC fallback.

### Question 4: Territory scope in `prices.lock.json` (`36` vanilla vs `IE`/`CY`/`MT` from EU-27 EC Bulletin)

| Option | Description | Selected |
|--------|-------------|----------|
| Store all 39 European entries (36 vanilla + `IE`/`CY`/`MT` from EC) in `prices.lock.json` | Powers `gas_ie_*` totems with live official EC Ireland prices immediately and pre-warms `IE`/`CY`/`MT` for Phase 4 ProMods, while Core `def/country/*.sui` stays strictly 36 countries | ✓ |
| Store 37 entries (36 vanilla + `IE` only) in `prices.lock.json` | Include `IE` strictly because `1.62` has `gas_ie_*` boards, omitting `CY`/`MT` until Phase 4 ProMods | |
| Strictly 36 vanilla countries only in `prices.lock.json` | Keep `gas_ie_*` totems on a fallback/UK-adjacent price until `IE` enters `def/country/` | |
| You decide | Choose the cleanest scope boundary for `prices.lock.json` | |

**User's choice:** Store all 39 European entries (36 vanilla + `IE`/`CY`/`MT` from EC) in `prices.lock.json`.

---

## Circuit breaker, `prices.lock.json` lifecycle & Friday CI wiring

### Question 1: Lockfile placement and fetch vs. offline build coupling

| Option | Description | Selected |
|--------|-------------|----------|
| Two-stage decoupled flow with `state/prices.lock.json` | Online `ets2v2 fetch` updates `state/prices.lock.json`, while `build` and `publish release` stay strictly offline reading `state/prices.lock.json`; Friday CI runs `fetch` then `publish release` and includes `state/prices.lock.json` in the persistent Release PR | ✓ |
| Integrated `--live` flag on `publish release` with `prices.lock.json` at repo root | Single command fetches and builds together when `--live` is passed, defaulting to offline locally | |
| Ephemeral CI cache only (don't commit `prices.lock.json` to Git) | Store `prices.lock.json` only in GitHub Actions cache / release artifacts, never tracked in Git | |
| You decide | Pick the cleanest architecture for reproducibility and Phase A Release PR handoff | |

**User's choice:** Two-stage decoupled flow with `state/prices.lock.json`.

### Question 2: Price circuit-breaker behavior (`0.01–5.00 EUR/L` bounds and `±25%` WoW jumps)

| Option | Description | Selected |
|--------|-------------|----------|
| Reject & hold lockfile on both bounds and `>25%` jumps, with CLI override | Automatically retain the last-known-good price in `state/prices.lock.json` and record a structured alert in the Release PR/changelog whenever a price is out of `0.01–5.00 EUR/L` OR exceeds `±25%` WoW (with a manual `--allow-jump ISO2` flag for genuine tax/currency shocks) | ✓ |
| Reject only out-of-bounds (`0.01–5.00 EUR/L`); accept `>25%` jumps with loud warning | Only block impossible prices, letting `>25%` swings flow through into the build with a changelog alert | |
| Hard-fail CI on any circuit-breaker trip | Abort the Friday workflow immediately so the maintainer must inspect and re-run manually | |
| You decide | Pick the safest default against upstream unit bugs without silently missing real shocks | |

**User's choice:** Reject & hold lockfile on both bounds and `>25%` jumps, with CLI override (`--allow-jump ISO2`).

### Question 3: Multi-provider FX cross-validation divergence tolerance

| Option | Description | Selected |
|--------|-------------|----------|
| Tiered tolerances (`2%` major/ECB pairs, `5%` volatile/non-ECB like `TRY`/`RUB`) + hold lockfile FX on extreme (`>10%`) split | Warn when primary vs validator diverges `>2%` (or `>5%` for non-ECB/volatile), and fall back to lockfile FX with an alert if divergence exceeds `10%` or a currency-split sanity check fails | ✓ |
| Uniform `5%` tolerance across all currencies | Warn and prefer ECB/CBR over Frankfurter if `>5%` apart, holding lockfile FX only when all providers fail | |
| Strict `1%` fail-closed for all ECB currencies | Reject any FX update that differs `>1%` from ECB reference rates | |
| You decide | Pick the most resilient cross-validation tolerance for weekly European FX | |

**User's choice:** Tiered tolerances (`2%` major/ECB, `5%` volatile/non-ECB) + hold lockfile FX on `>10%` or currency-split failure.

### Question 4: Staleness alerts and partial vs. total upstream outages in Friday CI

| Option | Description | Selected |
|--------|-------------|----------|
| Partial outage = warn & fallback; Total outage (`0` live Tier 1 feeds) = fail `fetch` loudly; Staleness alert `>14d` (Tier 1) / `>30d` (fallback) | Single broken feed never blocks Friday builds, stale countries get flagged in the Release PR/changelog, and total network/DNS failure alerts via failed CI instead of silent no-op | ✓ |
| Always succeed even on total outage (degrade to no-op using `prices.lock.json`) | Never turn Friday CI red due to external API downtime; log warnings only | |
| Fail CI if EC Weekly Oil Bulletin (plus its `FionnHughes`/`fuel-prices.eu` fallback) is unreachable, regardless of UK/NO | Treat EU-27 core feed availability as mandatory for a Friday run | |
| You decide | Pick the right balance between CI reliability and outage visibility | |

**User's choice:** Partial outage = warn & fallback; Total outage (`0` live Tier 1 feeds) = fail `fetch` loudly; Staleness alert `>14d` (Tier 1) / `>30d` (fallback).

---

## Zero-DDS totem board coverage, native currency formatting & `<sup>9</sup>` rules

### Question 1: Handling the `47` placeholder and `41` blank fuel boards in `fuel_boards.json`

| Option | Description | Selected |
|--------|-------------|----------|
| Populate every identifiable country/city + grade board; preserve structural blanks like `gas_empty` | Map all `373` active + all identifiable placeholder/blank boards (incl. city aliases like `dortmund`->`DE`, `gas_ie_*`, `gas_bi_*`, `*_lpg`, `*_98`, fixing `gas_is_yokull` 95/diesel swap + `gas_is_ip1_98`), leaving only intentionally empty structural spacers like `gas_empty` untouched | ✓ |
| Populate active + numeric placeholders only; leave all 41 blank (`" "`) boards blank | Avoid lighting up blank rows on roadside signs that SCS intentionally left empty | |
| Populate every single one of the 461 boards without exception | Even generic/blank boards get a default price token | |
| You decide | Inspect all 88 placeholder/blank boards during research and pick the cleanest per-board rule | |

**User's choice:** Populate every identifiable country/city + grade board; preserve structural blanks like `gas_empty`.

### Question 2: Native currency & sub-unit display conventions (`GB` pence, `NL`/Eurozone `<sup>9</sup>`, integer currencies)

| Option | Description | Selected |
|--------|-------------|----------|
| Authentic real-world national pump conventions, gated by `1.62` font/width verification | UK in pence (e.g. `142.9`), DE/AT/FR/NL/etc. in EUR with `<sup>9</sup>` tenth-cent where `1.62` fonts support it (falling back cleanly to 3-decimal `1.789` or 2-decimal `1.79` on narrow/7-segment boards), BG in EUR (`1.34`), integer-unit currencies (`HUF`/`ISK`/`ALL`/`RSD`) as whole integers | ✓ |
| Match ETS2 `1.62` vanilla `fuel_price_strings.sui` per-country unit/decimal templates | Keep the exact unit/digit layout SCS chose for each country's `1.62` sign boards | |
| Match `3249064596` (`kworey`) conventions | UK in pence (`197.0`), NL in eurocents (`252.5`), 2–3 decimals elsewhere without `<sup>9</sup>` on base boards | |
| You decide | Let Phase 3 research inspect `1.62` `fuel_price_strings.sui` + `.font` metrics and choose the most authentic convention | |

**User's choice:** Authentic real-world national pump conventions, gated by `1.62` font/width verification.

### Question 3: Decimal separator convention (`.` vs `,`)

| Option | Description | Selected |
|--------|-------------|----------|
| Uniform dot (`.`) decimal separator across all boards | Matches LED/7-segment roadside totems and vanilla `1.62` `fuel_price_strings.sui`, guaranteeing zero missing-glyph boxes on all 6 gas fonts | ✓ |
| Country-native separator (`.` or `,`) where the board's `1.62` `.font` contains a comma glyph, falling back to `.` otherwise | Uses comma in DE/FR/PL/etc. on non-7-segment fonts after verifying `.font` glyph tables | |
| You decide | Verify what vanilla `1.62` `fuel_price_strings.sui` and the 6 `.font` files actually use during research | |

**User's choice:** Uniform dot (`.`) decimal separator across all boards.

### Question 4: Offline SCS Validator (`validate workshop` / `validate local`) totem checks

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-fail totem invariants in the Offline SCS Validator | Fail validation on any `.dds`/`.tobj` file, missing/extra locale (exact 43 active locales, zero `fr_qc`, identical key/val sets), orphan/unresolved `@@fp_*_ets2v2@@` token between `def/sign/board/*.sii` and `local_module.ets2v2_fuel.sii`, or board SII hygiene/geometry drift | ✓ |
| Basic SII syntax & Zero-DDS checks only (keep locale/board cross-reference checks in pytest unit tests) | Keeps runtime validator lighter while tests catch cross-reference drift | |
| You decide | Wire the right split between runtime validator checks and pytest contract tests | |

**User's choice:** Hard-fail totem invariants in the Offline SCS Validator.

---

## Snapshot v1 contract, `.sui` precision & weekly price changelogs

### Question 1: `RealismSnapshot` schema version & provenance placement

| Option | Description | Selected |
|--------|-------------|----------|
| Keep `RealismSnapshot` strictly at `schema_version: 1` | Preserve Phase 2's one-way D-11 contract unchanged (populating live `eur_per_liter`, `local_prices`, and `source`), and keep rich FX/timestamp/fallback/alert provenance inside `state/prices.lock.json` | ✓ |
| Bump `RealismSnapshot` to `schema_version: 2` with embedded FX & staleness metadata | Put FX rates, `fetched_at` dates, and alert lists directly inside `realism-snapshot-{summer,winter}.json` | |
| You decide | Keep contract stability aligned with Phase 4 `compose-local` needs | |

**User's choice:** Keep `RealismSnapshot` strictly at `schema_version: 1` (provenance stored in `state/prices.lock.json`).

### Question 2: Canonical grade key naming in `local_prices` and `state/prices.lock.json`

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical domain grade keys (`diesel`, `diesel_plus`, `petrol_95`, `petrol_98`, `petrol_100`, `petrol_92`, `e85`, `lpg`, `mpo`) | Clean, game-agnostic schema for Phase 3–5 global collectors, with a deterministic adapter mapping aliases (`natural95`/`unleaded`->`petrol_95`, `super`->`petrol_98`, `diesel5`->`diesel_plus`) when emitting `@@fp_*_ets2v2@@` totems | ✓ |
| Mirror ETS2's raw `fp_*` grade names (`diesel`, `natural95`, `natural98`, `natural100`, `diesel_plus`, `diesel5`, `e85`, `lpg`, `mpo`, `super`, `unleaded`) | Direct 1:1 key match with `locale.scs` without an alias table | |
| You decide | Pick the cleanest schema for Phase 3 totems and Phase 4/5 global snapshots | |

**User's choice:** Canonical domain grade keys (`diesel`, `diesel_plus`, `petrol_95`, `petrol_98`, `petrol_100`, `petrol_92`, `e85`, `lpg`, `mpo`) with deterministic ETS2 alias mapping.

### Question 3: `.sui` `fuel_price` decimal precision

| Option | Description | Selected |
|--------|-------------|----------|
| 3 decimal places (`0.001 EUR/L`, e.g., `1.642`) | Matches ETS2 `1.62` & `3249064596` convention and preserves tenth-cent accuracy between dashboard refueling and roadside `1.789`/`1.78<sup>9</sup>` totems | ✓ |
| 2 decimal places (`0.01 EUR/L`, e.g., `1.64`) | Coarser rounding reduces tiny `0.001 EUR` FX-noise rebuilds in the weekly SHA-256 diff gate | |
| You decide | Match ETS2 `1.62` conventions cleanly | |

**User's choice:** 3 decimal places (`0.001 EUR/L`).

### Question 4: Fuel & provenance reporting in `CHANGELOG_SUMMER.md` / `CHANGELOG_WINTER.md` and `description.txt`

| Option | Description | Selected |
|--------|-------------|----------|
| Full 36-country fuel table + source attribution + active circuit-breaker/staleness alerts | Include a compact Markdown table (`ISO2`, `EUR/L` diesel, local diesel & 95 display, source, freshness), explicit `CC BY 4.0` / `OGL v3` / *Licence Ouverte* / `IODL 2.0` attributions in both changelogs and `description.txt`, and a highlighted alerts section when any country fell back to `prices.lock.json` | ✓ |
| Delta-only fuel changes + alerts section (no full 36-row table) | Keep changelogs short by listing only countries whose prices changed plus any circuit-breaker alerts and attribution links | |
| Keep Phase 2 changelog format unchanged; emit fuel/alert details only in a separate `fetch_report.json` | Avoid growing `CHANGELOG_*.md` files | |
| You decide | Balance weekly maintainer reviewability with clean open-data attribution | |

**User's choice:** Full 36-country fuel table + source attribution + active circuit-breaker/staleness alerts in `CHANGELOG_*.md` and open-data attribution in `description.txt`.

---

## Claude's Discretion

- Phase 3 Python subpackage layout (`src/ets2v2/fetch/`, `src/ets2v2/normalize/`, totem module placement) and updating `tests/test_cli_scaffold.py` while keeping Phase 4's `merge/` blocked.
- Adding `httpx>=0.28,<0.29` and `openpyxl>=3.1,<4` to `pyproject.toml` / `uv.lock` under permissive licensing.
- Exact `ets2v2 fetch` CLI subcommand/flag names, HTTP retry/timeout parameters, deterministic German station set for optional `Tankerkönig` sampling, and `state/prices.lock.json` schema keys.

## Deferred Ideas

None — discussion stayed within Phase 3 boundaries. ProMods `pm_*_fuel` totems and `compose-local` remain mapped to Phase 4 (`MAP-01`..`MAP-05`); non-EU Tier 1/2/3 global collectors and CI-only OSM speed-limit drift audits remain mapped to Phase 5 (`GLB-01`..`GLB-04`).
