# Domain Pitfalls & Steam Workshop Publishing Automation

**Domain:** Euro Truck Simulator 2 (`AppID 227300`) — Dual-Edition Data Mod (`Summer` + `Winter`) & Automated Steam Workshop Pipeline  
**Target Game Baseline:** ETS2 `1.62.3.3s` (rev. `7173c707daa0`)  
**Researched:** 2026-11-15  
**Overall Confidence:** **HIGH** (primary verification against local ETS2 `1.62.3.3s` `def.scs`/`locale.scs`, installed Workshop mods `3668352310`/`3668351598`/`3249064596`/`1820303287`/`3002586900`, SCS Modding Wiki local mirror + live `modding.scssoft.com`, and `m00nl1ght-dev/steam-workshop-deploy` / `game-ci/steam-deploy` source code).

---

## Executive Verdict on Automated Steam Workshop Publishing

1. **SCS Workshop Uploader (`AppID 421800`) has NO CLI, headless, or batch mode.** Verified against both the local SCS Modding Wiki mirror (`2026-06-29`) and live `modding.scssoft.com` changelog through `1.62.0` (`e3f33c1d8ed3`, `20.10.2026`). Furthermore, `SCS Workshop Uploader` (`421800`), `steamcmd`, `scs_extractor.exe`, and `scs_packer.exe` are **not installed** on this workstation (`C:\Program Files (x86)\Steam` and `D:\SteamLibrary`).
2. **Automated CI publishing MUST use SteamCMD (`+workshop_build_item`), NOT GUI automation.** However, because `steamcmd` bypasses SCS's `package_content_validator`, our build pipeline must enforce strict offline validation (mirroring SCS error codes `00001`–`00010`) before any upload.
3. **Never rely on `STEAM_CONFIG_VDF` (`ConnectCache`) alone on ephemeral GitHub Actions runners.** Valve changed SteamCMD session handling so Linux often omits SSFN files and machine tokens rot/fail across rotating runner IPs with `FAILED (Invalid Login Auth Code)` / `Cached credentials not found` (`game-ci/steam-deploy#56`, re-confirmed Aug 2026). Full automation (**Phase B**) requires **`STEAM_USERNAME` + `STEAM_PASSWORD` + live 30s TOTP from `STEAM_SHARED_SECRET`** minted immediately before `+login`, OR a persistent single-IP self-hosted runner.
4. **Ship Phase A (Semi-Auto) first, then graduate to Phase B (Full-Auto) via an explicit hidden-item verification spike.** Phase A requires zero Steam secrets in CI and produces ready-to-upload Workshop directories/ZIPs + changelogs for one-click upload in SCS Workshop Uploader.

---

## Critical Pitfalls

Mistakes that cause broken builds, hijacked/corrupted Workshop listings, subscriber backlash, or silent gameplay bugs.

### Pitfall 1: Relying on `config.vdf` Session Blobs on Ephemeral GitHub Runners (`Invalid Login Auth Code`)
- **What goes wrong:** Following legacy `game-ci/steam-deploy` guides, you log in locally with SteamCMD, base64-encode `config/config.vdf` (`ConnectCache` + `Accounts`), and store it as `STEAM_CONFIG_VDF`. It works once (or only on the machine that minted it) and then fails on GitHub Actions Linux runners with:
  ```text
  Logging in user '***' to Steam Public...FAILED (Invalid Login Auth Code)
  ```
  or `Cached credentials not found` / `FAILED (License expired)` / `ERROR (Access Denied)`.
- **Why it happens:** Valve tightened SteamCMD machine-token / `ConnectCache` validation (`game-ci/steam-deploy#56`, verified again in August 2026 in `neddonovan1-crypto/duty_guvnor@743bf12`): SteamCMD on Linux frequently generates no `ssfn*` sentry file at all, `config.vdf` tokens expire or get invalidated by logging in elsewhere, and rotating Azure datacenter IPs on GitHub-hosted `ubuntu-latest` trigger fresh Steam Guard prompts despite a seeded `config.vdf`. Moreover, `m00nl1ght-dev/steam-workshop-deploy` runs inside a stateless Docker container and does not persist updated `config.vdf` back to secrets.
- **Consequences:** Weekly Thursday/Friday automated fuel updates silently break at the final deploy step until a maintainer manually re-mints `config.vdf` locally.
- **Prevention:**
  - **In Phase A (Semi-Auto):** Use zero Steam secrets in GitHub Actions; CI builds validated `summer/` and `winter/` Workshop packages and attaches them as GitHub Release/Workflow artifacts.
  - **In Phase B (Full-Auto):** Authenticate with **Steam Guard Mobile Authenticator TOTP** (`STEAM_USERNAME`, `STEAM_PASSWORD`, `STEAM_SHARED_SECRET`), generating the 30-second TOTP code **inside the same job/container immediately before `steamcmd +login`** (after `steamcmd` finishes self-updating!) using `steam-totp` (or `CyberAndrii/steam-totp@v1` only if `steamcmd` update latency cannot push past the 30s boundary). Alternatively, run `config.vdf` persistence on a static-IP self-hosted runner.
- **Confidence:** **HIGH** (verified in `game-ci/steam-deploy#56` and `duty_guvnor@743bf12`).

---

### Pitfall 2: Dual-Edition Cross-Contamination in `m00nl1ght-dev/steam-workshop-deploy` (`rsync` Without `--delete`)
- **What goes wrong:** Deploying both **Summer** and **Winter** Workshop items sequentially in the same GitHub Actions job using `m00nl1ght-dev/steam-workshop-deploy@v4` leaks Summer files into the Winter upload (or stale deleted country `.sui` files across updates).
- **Why it happens:** Direct inspection of `m00nl1ght-dev/steam-workshop-deploy/master/action.yml` and `steam_deploy.sh` shows:
  1. `stagingPath` defaults to `/tmp/steam_deploy/` and `concurrentStaging` defaults to `'false'`.
  2. `steam_deploy.sh` copies content via `rsync -a "${RSYNC_EXCLUDE_PARAMS[@]}" "$contentroot/" "$stagingPath"` **without `--delete`**!
  3. Any file written during step 1 (`summer`) that does not exist at the exact same relative path in step 2 (`winter`) — e.g., Summer-specific packages or deleted countries — remains inside `/tmp/steam_deploy/` when `workshop_build_item` uploads Winter.
- **Consequences:** Silent package bloat, mixed Summer/Winter defs inside the wrong Workshop item, or phantom leftover files overriding base ETS2 assets.
- **Prevention:**
  - Run Summer and Winter deployments in **separate matrix jobs** (`strategy.matrix.edition: [summer, winter]`) so each gets a fresh ephemeral container and workspace, **and** explicitly set unique `stagingPath: /tmp/steam_deploy_summer/` vs `/tmp/steam_deploy_winter/` (or invoke `steamcmd` directly against an isolated clean staging directory).
  - Never use `path: .` (repo root) when deploying; pass only the clean pre-built `dist/workshop/<edition>/` folder. Even though `.deployignore` excludes `.git/`, `.github/`, `.env*`, and `config.vdf`, deploying from a dedicated `dist/` artifact directory eliminates all risk of accidentally shipping scrapers, tests, or `.planning/` files to Steam subscribers.
- **Confidence:** **HIGH** (observed directly in `action.yml` & `steam_deploy.sh`).

---

### Pitfall 3: Steam Account Ownership, Limited-Account Blocks, and Blast Radius
- **What goes wrong:** Automated `steamcmd +workshop_build_item` fails with `Access Denied` / `Fail` (`k_EResultFail`), OR storing CI credentials exposes an entire personal Steam account (inventory, games, friends, Workshop catalog) to supply-chain/PR token exfiltration.
- **Why it happens:**
  1. **No scoped Workshop API token exists in Steam:** `STEAM_CONFIG_VDF` or `STEAM_PASSWORD` + `STEAM_SHARED_SECRET` grants full non-payment login access to that Steam account.
  2. **AppID `227300` ownership + unrestricted status required:** Valve rejects `workshop_build_item` from anonymous logins, **Limited User Accounts** (<$5 USD Steam store spend), and **Steam Family Sharing / temporary licenses**. Unlike Steamworks partner apps that grant "Build/Upload" roles to limited sub-accounts in a developer org, mod Workshop items for `227300` must be uploaded by a non-limited account that directly owns ETS2.
  3. **Contributor vs Owner mismatch:** Using a secondary "contributor" bot account to update a Workshop item created by a primary personal account risks `Access Denied` / `Invalid Parameter` if SteamUGC rejects non-creator CLI updates for that app integration.
  4. **Historical Secret-Leak CVE (`GHSA-mj96-mh85-r574`, CVSS 8.7):** `buildalon/setup-steamcmd < 1.1.0` printed `config/config.vdf` and `localconfig.vdf` to public workflow logs during cleanup. Meanwhile `m00nl1ght-dev/steam-workshop-deploy` (`master` as of Aug 2025, 4 stars / 6 forks) sets `chmod 777 "$steamdir/config/config.vdf"` and dumps `for f in "$steamdir"/logs/*; do cat "$f"` on failure while relying on floating `FROM steamcmd/steamcmd:ubuntu-22`.
- **Prevention:**
  - Create a **dedicated publisher Steam account** (unrelated to personal library/inventory, $5+ spend unlocked, owns ETS2 `227300`, Mobile Guard enabled only for its CI TOTP seed) OR accept manual Phase A upload with personal account until a dedicated publisher account owns both V2 Workshop items from Day 1.
  - **NEVER run deploy workflows on `pull_request` / `pull_request_target` / fork commits.** Restrict Phase B publish jobs to `workflow_dispatch`, scheduled cron, or protected `main` commits, gated by a **GitHub Environment** (e.g., `steam-workshop-prod`).
  - **Pin third-party actions and Docker images by immutable 40-char commit SHA / image digest** (e.g., never floating `@v4`), or invoke Valve's `steamcmd` directly inside a small audited wrapper step without dumping `$HOME/Steam/logs` blindly to stdout.
- **Confidence:** **HIGH** (`GHSA-mj96-mh85-r574`, Steamworks Workshop docs, `m00nl1ght-dev/steam-workshop-deploy`).

---

### Pitfall 4: Bypassing SCS Workshop Uploader Validation & `versions.sii` / `manifest.sii` Violations
- **What goes wrong:** `steamcmd +workshop_build_item` blindly uploads whatever directory you hand it without checking any SCS engine rules. Subscribers download a mod that fails to mount or crashes Mod Manager/game startup.
- **Why it happens:** Only `mod_tools.exe` (`SCS Workshop Uploader`) runs SCS's `package_content_validator`. Raw `.vdf` only verifies Steam Workshop VDF fields.
- **Consequences:** ETS2 refuses to read units (`Unable to read units from file`), rejects malformed `manifest.sii`/`versions.sii`, or warns on every player load.
- **Preventive Validation Rules (Verified Directly from `warning_and_error_codes.md`, `validation_errors_and_solutions_for_them.md`, `versions.sii.md`, `mod_manager.md`, `units.md`):**

  | Rule / Code | What Breaks | V2 Pipeline Enforcement |
  |---|---|---|
  | `00003` (Not allowed) | Uploading a ZIP file renamed to `.scs` (e.g., legacy `Country_Speed_Fuel_Merge.scs` uses `PK\x03\x04` inside `.scs` — works locally in `mod/`, **forbidden** on Steam Workshop!). Allowed formats: unpacked folder (`universal/`), `.zip` (`universal.zip`), or genuine **HashFS v2** `.scs` (`SCS#\x02`). | Ship `universal/` folder or `universal.zip` (zero `scs_packer.exe` Windows binary dependency on Linux CI). Never ship ZIP-as-`.scs` to Workshop. |
  | `00003` (Not allowed) | `versions.sii` missing a universal package, OR defining **two** universal packages (packages lacking `compatible_versions[]` and not `informational: true`). | Emit **strictly one** `package_version_info : .universal { package_name: "universal" }`. Keep `summer/` and `winter/` as **two completely separate Workshop roots/items**, never two `.universal` entries in one `versions.sii`! |
  | `00003` (Not allowed) | Extra files in Workshop mod root besides `versions.sii` and declared packages (`README.md`, `.gitkeep`, preview images outside `universal/`). Also unreferenced `.txt` or `.jpg` files inside a package! | Stage clean `dist/workshop/<edition>/` containing *only* `versions.sii` and `universal/` (or `universal.zip`). Every `.txt`/`.jpg` in `universal/` must be `icon` or `description_file` (+ valid `description.<locale>.txt`). |
  | `00003` (Not allowed) | Package names outside `[a-z0-9_]` or `> 256` chars; Windows `\` separators or `..` anywhere in paths/includes. | Enforce lowercase `universal` and POSIX `/` paths exclusively. |
  | `00001` / `00002` / `00009` | Missing/misplaced `icon` or `description_file`; icon not `.jpg` or not **`276x162 px`** or `> 1 MB`; description `> 1 MB`. | CI image assertion (`276x162`, JPEG header, `< 1 MB`) + co-located in package root beside `manifest.sii`. |
  | `00004` (Malformed) | Missing `SiiNunit { ... }` magic header, or `description_file` not valid UTF-8 (Windows-1252 quotes/accents fail). | Validate UTF-8 (no BOM on `.sii`/`.sui`/`.txt`), LF (`\n`) endings, balanced braces, valid `SiiNunit` header. |
  | `00010` / `WARN 00002` | `compatible_versions[]` placed inside Workshop `manifest.sii` (`mod_package`), which is **only** for standalone mods (`difference_between_workshop_mod_and_the_standard_mod.md`). Note SCS wiki lists `00010` as both *Unused field set* (`warning_and_error_codes.md`) and *IO Error* (`validation_errors_and_solutions_for_them.md`). | **Omit `compatible_versions[]` completely** from Workshop `manifest.sii`. Version targeting lives solely in `versions.sii`. |
  | `WARN 00001` | Including `display_name:` in Workshop `manifest.sii` triggers warning because Workshop Uploader fetches title from Steam (`3668352310`, `3668351598`, `3249064596` all still carry it; `1820303287` cleanly omits it). | **Omit `display_name:`** from Workshop `manifest.sii` (or only include in standalone local `.scs`/`.zip` builds if distributing outside Workshop). |
  | `Mod Manager` & `game.log.txt` | `> 2` `category[]` entries in `manifest.sii` triggers `[mods] Too many categories defined ... - limit 2. Using first 2.`; unit token segments `> 12` chars or invalid chars (observed in `game.log.txt`: `_nameless.heavy_ratio_merge` rejected in `manifest.sii`!). | Limit `category[]:` to max 2 valid tokens from SCS's 18-category enum (`other`, `ai_traffic`); keep all dot-separated unit tokens `<= 12` chars `[a-z0-9_]` (e.g., `.package_name` -> `package_name` is 12 chars!). |
  | Convoy Multiplayer | Missing `mp_mod_optional: true` blocks Convoy sessions with friends who haven't subscribed. | Always set `mp_mod_optional: true` in `manifest.sii`. |

- **Confidence:** **HIGH** (all codes and limits verified directly in local + live SCS Modding Wiki and `game.log.txt`).

---

### Pitfall 5: Inheriting Bugs from Reference Mods (`3668352310` `3nK`, `3249064596` Data Corruption)
Direct inspection of installed Workshop mods and ETS2 `1.62.3.3s` `def.scs` uncovered concrete traps in both legacy inspiration mods:

1. **`3668352310` & `3668351598` (`neuhr` WINTER / SUMMER) — `3nK` Obfuscated `speed_limits.sii`:**
   - **Observed:** Both HashFS v1 archives ship **36 plaintext `def/country/*.sui` files** and **36 `3nK\x01\x00`-encrypted `speed_limits.sii` files** (`33 6e 4b 01 00...`, 1,389–1,473 bytes).
   - **Verified Reality in ETS2 1.62:** All 37 `speed_limits.sii` files inside vanilla ETS2 `1.62.3.3s` `def.scs` are **100% plaintext `SiiNunit`** containing `vehicle_speed_class` blocks for `car`, `truck`, **`bus`**, `train`, and `tram`. `3nK` is purely third-party obfuscation/legacy binary encoding and **breaks SCS Workshop Uploader's SII text parser validation** (plus prevents code review, diffing, or preserving ETS2 `1.62` `bus`/`train`/`tram` rules).
   - **Rule:** Ship **plaintext `SiiNunit`** `speed_limits.sii` files derived from ETS2 `1.62` `def.scs`, preserving `bus`, `train`, and `tram` blocks unchanged when patching `car` and `truck` limits.

2. **`3249064596` (`kworey` Real Life Fuel Prices, HashFS v2, 75 countries) — Silent Country-Def Bugs:**
   - **Armenia `leftside_traffic: true`:** Directly observed in `country.data.armenia` (`country_id: 47`) inside `3249064596/universal.scs` — flips Armenian AI traffic and road rules to left-hand drive (wrong; Armenia drives on the right!).
   - **Estonia `name: "@@tz_eest@@i"`:** Directly observed in `country.data.estonia` (`country_id: 22`) inside `3249064596/universal.scs` — broken regex/string replace turned `"Eesti"` into `"@@tz_eest@@i"` while updating timezones!
   - **Stale hardcoded winter timezones & third-party map leak:** `3249064596` overwrites vanilla DST timezones (`time_zone: 120`, `"@@tz_cest@@"`) with commented-out Portuguese `# verão`/`# inverno` winter offsets and bakes ProMods/RusMap/Sibir/Altai `secondary_time_zone_area[]` edits into `russia.sui`.
   - **Overwriting `regions[]` / `region_areas[]` risk:** Correction from direct inspection — current `3249064596` (and `Country_Speed_Fuel_Merge.scs`) *does* still retain `regions[]` on the 5 vanilla `1.62` countries that use them (`bosnia`: `rep_srpska`; `norway`: `rc_train`, `the_north`; `finland`: `the_north`; `sweden`: `rc_train`, `the_north`, `inland`; `spain`: `catalonia`, `navarre`, `basque`). **However**, building `.sui` files from scratch or stale templates (or stripping unknown attributes) silently drops `regions[]`/`region_areas[]`, breaking regional license plates, train crossings, and Nordic Horizons triggers, OR drops newly added vanilla countries like `iceland.sui` (`country_id: 26` in `1.62`)!
   - **396 `def/sign/board/*.sii` overrides for `@@fp_*_kwo@@`:** Vanilla ETS2 `1.62` `def.scs` *already* has 375 `@@fp_<iso>_<fuel>@@` gas station sign boards mapped inside `locale.scs`. Modifying all 396 `sign_board_template` files creates heavy mod conflicts with any map/sign overhaul unless carefully isolated (or if totems are deferred/scoped properly).

- **Prevention:** Never copy `.sui`/`.sii` files blindly from third-party Workshop mods. Vendor clean, pinned baselines extracted from **ETS2 `1.62.3.3s` `def.scs`** (and verified map-mod baselines only in scoped map-compatibility layers), and apply **surgical AST/line-level attribute patching** that asserts `leftside_traffic`, `name`, `name_localized`, `country_id`, `regions[]`, `region_areas[]`, `mass_limit_per_axle_count[]`, and `bus`/`train`/`tram` speed blocks remain untouched (unless explicitly intended, e.g. seasonal DST `time_zone` toggle for Summer vs Winter).
- **Confidence:** **HIGH** (all files directly inspected on disk).

---

### Pitfall 6: Currency Mismatch Between `fuel_price` (EUR/L) and Station Totems (Local Currency + ECB Feed Gaps)
- **What goes wrong:** Setting gas station totem prices (`@@fp_*@@` in `locale/*/local_module.*.sii`) from `fuel_price` (or vice versa) displays €1.90 on a Hungarian, Czech, Icelandic, Polish, or UK pump sign where drivers expect HUF (`708.81`), CZK (`48.10`), ISK (`316.1`), PLN, or GBP/pence (`210.3`). Worse, relying exclusively on the European Central Bank daily XML feed (`eurofxref-daily.xml`) fails for ~15–20+ non-Eurozone / CIS / MENA / Caucasus currencies!
- **Verified Realities from ETS2 `1.62` `locale.scs` & ECB Documentation:**
  1. **`country_data.fuel_price` is strictly EUR per litre** across *every* country (`def/country/germany.sui`: `2.244`, `turkey`: `1.628`, `iceland`: `2.307`, `norway`: `2.616`, `russia`: `0.908`).
  2. **Vanilla `locale.scs` `fp_*` totem values are in LOCAL currency** with country-specific decimal/unit formatting (`fp_al_diesel: "211"` ALL, `fp_cz_natural95: "48.10"` with comment `# always ends with .X0`, `fp_hu_diesel: "708.81"` HUF, `fp_is_diesel: "316.1"` ISK, `fp_dk_diesel: "19.79"` DKK, `fp_bg_natural95: "1.67"` EUR following Bulgaria's Jan 1, 2026 Euro adoption!).
  3. **`kworey` (`3249064596`) uses `v1`–`v4` variants and `<sup>0</sup>` HTML-like micro-tags** (`"2.10<sup>0</sup>"`, `"210.3"`) matching specific UK/EU totem sign fonts (`gas_segment_7_standard.font`, `gas_karnivore_lite.font`), which break display alignment if formatted with wrong precision or characters unsupported by the `.font` glyph set.
  4. **ECB `eurofxref-daily.xml` coverage gaps:**
     - **RUB suspended** by ECB since March 1, 2022 (`EUR/RUB` absent).
     - **Never included in ECB feed:** `EGP`, `DZD`, `AMD`, `GEL`, `BYN`, `AZN`, `KZT`, `RSD`, `BAM`, `MKD`, `MDL`, `UAH`, `ALL`, `MAD`, `TND`, `SAR`, `AED`, `IRR`, etc.
     - **No updates on weekends or TARGET2 holidays:** `eurofxref-daily.xml` freezes on Friday ~16:00 CET until the next business day.
- **Prevention:**
  - Treat `country_data.fuel_price` (always **EUR/L diesel**, converted to EUR using source-currency FX at fetch time) and station totem strings (`fp_*` in **local currency** formatted per country totem spec) as two explicitly typed schema fields (`eur_per_liter` vs `local_display_price`).
  - Use a multi-tier FX resolver (`ECB XML` for ~30 major/EU currencies -> secondary central-bank/FX API such as `open.er-api.com` / `fawazahmed0/exchange-api` / NBU/NBR/CBR/CBA for CIS/MENA/Balkan currencies -> cached last-good rate with age warning), and keep **Euro-zone status configurable** (e.g., Bulgaria `EUR` since 2026) so `fuel_price` never double-converts.
- **Confidence:** **HIGH** (observed directly in ETS2 `1.62` `locale.scs` / `def.scs` and ECB official docs).

---

### Pitfall 7: EC Weekly Oil Bulletin Schedule Drift, Messy Excel Layouts, and Scraper Blocking
- **What goes wrong:** A rigid Thursday morning cron job or naive `requests.get()` scraper against EC Bulletin + non-EU portals (`GlobalPetrolPrices`, `Tolls.eu`, `Autotraveler.ru`, `Cargopedia`) intermittently hits HTTP `403 Forbidden` (Cloudflare), HTTP `429`, shifted Excel column indices, or stale data from the previous week.
- **Why it happens:**
  1. **EC Weekly Oil Bulletin Timing:** Member states submit Wednesday; the European Commission publishes/emails the bulletin **Thursday afternoon** (typically ~17:00 CET, shifting around EU public holidays). URL slugs and XLSX filenames on `energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en` can shift, the workbook contains `200+` columns and multi-row headers, uses `EL` instead of `GR` for Greece in Eurostat/EC conventions, and reports `EUR per 1,000 litres` (`/1000` -> EUR/L) for automotive gas oil (diesel) and Euro-super 95.
  2. **Non-EU / CIS / MENA / Africa / Asia Anti-Bot Reality:** Sites like `globalpetrolprices.com`, `cargopedia.net`, `tolls.eu`, and `autotraveler.ru` protect HTML tables with Cloudflare WAF, TLS/HTTP2 fingerprinting (`JA3`/`JA4`), and datacenter IP throttling—meaning scrapers that pass locally on residential Windows broadband frequently return `403` from GitHub-hosted Azure runners! Moreover, GlobalPetrolPrices explicitly restricts automated scraping of its compiled datasets in its Terms of Service (offering a paid XML/Excel API instead).
- **Prevention:**
  - **Schedule weekly automation for Friday UTC** (e.g., `06:00 UTC` Friday, safely past Thursday 17:00 CET publication + holiday buffer), and validate that the EC workbook's latest reporting date is monotonic/fresh without failing fatally during holiday delays.
  - **Discover the XLSX download link dynamically** from the EC bulletin landing page rather than hardcoding fragile date-stamped filenames; parse by **header/country-code matching** (`EL` -> `greece`), never hardcoded Excel column numbers.
  - **Prefer official free national APIs/open-data endpoints first** (EC Oil Bulletin for EU-27; UK DESNZ weekly road fuel stats; Switzerland BFS/TCS; Norway Drivstoff/SSB; France `prix-carburants.gouv.fr`; Spain `geoportalgasolineras`; Italy MIMIT) over commercial scraped aggregators.
  - **Circuit-breaker & partial-failure resilience:** If a non-EU source returns `403`/`429` or breaks HTML layout on one run, **preserve the last committed good price in `prices.lock.json`** (emitting a CI warning / opening an issue if staleness exceeds `N` weeks) rather than writing `0.0`, `NaN`, or aborting updates for the 40 countries that succeeded. Enforce strict range assertions (`0.02 <= fuel_price <= 5.00` EUR/L; alert on `>25%` week-over-week jump).
- **Confidence:** **HIGH** (verified via EC Weekly Oil Bulletin documentation, Cloudflare `403` behavior, and GlobalPetrolPrices access/ToS pages).

---

### Pitfall 8: Fake No-Op Updates Spamming Workshop Subscribers (and Broken Metadata on Initial SteamCMD Publish)
- **What goes wrong:** Running a scheduled GitHub Action every Friday blindly executes `steamcmd +workshop_build_item` even when no prices/speed rules changed — OR zips files with fresh `mtime` timestamps so git/ZIP SHA256 changes every run. Subscribers receive phantom 100 KB–5 MB Workshop updates every week, Mod Manager flags "mod updated", and Convoy friends get forced into out-of-sync downloads.
- **Why it also breaks initial creation:** Using `m00nl1ght-dev/steam-workshop-deploy` (or minimal `workshop.vdf`) omits `"title"`, `"description"`, `"previewfile"`, `"visibility"`, and `"tags"`. While omitting those fields is a **feature for updates** (preserving existing Steam Workshop titles, descriptions, tags, screenshots, and visibility), creating an item from scratch with `"publishedfileid" "0"` leaves it **hidden** until the publisher manually accepts the Steam Workshop Legal Agreement on the web page, and SteamCMD cannot reliably populate ETS2's SCS category checkboxes cleanly on its own.
- **Prevention:**
  - **Canonical content-hash diff gate:** Compute a deterministic SHA-256 over the sorted `(relative_path, normalized_bytes)` payload of `dist/workshop/<edition>/` (**excluding** volatile dates/timestamps, normalized `ZIP` epoch `1980-01-01` if zipped, and **before** stamping build timestamp into `package_version`!). Store the last-published hash in `state/published.json` (committed on deploy) or compare against a cached build tag. **Skip `+workshop_build_item` entirely when `payload_sha256` is unchanged.** Only bump `package_version` (e.g., `2026.46` / `YYYY.WW` or semver) when data actually changed!
  - **Bootstrap items once manually:** Create the Summer item and Winter item once via SCS Workshop Uploader (or hidden `steamcmd` upload + web UI edits + Legal Agreement acceptance) to obtain their permanent `SUMMER_WORKSHOP_ID` and `WINTER_WORKSHOP_ID`. Never use `"publishedfileid" "0"` in automated CI.
- **Confidence:** **HIGH** (verified via Steamworks `ISteamUGC` / `workshop_build_item` specification and `m00nl1ght-dev/steam-workshop-deploy` `manifest.vdf` generation).

---

## Moderate Pitfalls

### Pitfall 9: SCS Workshop Uploader Local Registry Desync (`mod_items_data.sii`) vs SteamCMD Interoperability
- **What happens:** If you initially publish Summer/Winter in SCS Workshop Uploader (`421800`) on PC-A, switch to GitHub Actions SteamCMD (`workshop_build_item`), and later open SCS Workshop Uploader on PC-B (or after reinstalling Windows), the Uploader dropdown may not list your existing item, or throws stale `Error id: 2` sync loops. Conversely, pushing via SteamCMD does not run SCS's category/UI state updates cleanly unless metadata is omitted.
- **How to avoid / recover:** Both tools target the exact same Steamworks `PublishedFileId_t` under `AppID 227300`. Deleting `C:\Users\<User>\Documents\SCS Workshop Uploader\mod_items_data.sii` forces SCS Workshop Uploader to re-query Steam UGC for items owned by the logged-in account — so an item updated via SteamCMD remains adoptable by SCS Workshop Uploader as long as `versions.sii` + package contents stay valid and owned by that account. Keep Steam Workshop descriptions, tags, and screenshots managed in the Steam Community web UI or SCS Workshop Uploader, and configure SteamCMD to **omit** `"title"`, `"description"`, `"visibility"`, and `"previewfile"` (only passing `"appid"`, `"publishedfileid"`, `"contentfolder"`, and `"changenote"`).

### Pitfall 10: ETS2 Major Version Bumps (`1.62` -> `1.63`+) Silently Introducing New Countries or Classes
- **What happens:** Because `versions.sii` uses a single `.universal` package (without `compatible_versions[]`), players on ETS2 `1.63` Open Beta won't get blocked as "Incompatible" — **which is good for UX**, *unless* `1.63` adds a new DLC country (e.g., Benelux rework changes, Ireland, etc.), adds a new `vehicle_speed_class` (just as `1.62` / Coaches includes `bus` alongside `car`, `truck`, `train`, `tram`), or alters `country.sii` / `regions[]`. Unlike `compatible_versions[]` lockouts, `.universal` silently loads stale `1.62` definitions on `1.63`!
- **How to avoid:**
  1. Pin a verified extract/manifest of vanilla ETS2 `1.62` `def/country/` & `locale.scs` metadata in git.
  2. When ETS2 updates (`1.63`), re-extract `def.scs` (manually on Windows or via official extractor) and run a `diff` check in V2 to absorb any new countries, `country_id`s, `regions[]`, or `speed_limits.sii` classes before patching.
  3. Optionally archive frozen legacy packages in `versions.sii` (`compatible_versions[]: "1.62.*"`) only when a breaking `.sui` schema change hits `1.63`.

### Pitfall 11: Seasonal Summer ↔ Winter Rules Drift & Ambiguous Rules (e.g., Spain, Estonia, Finland, Norway)
- **What happens:** Duplicating country data between two independent `summer` and `winter` folders leads to divergence where a bug fix or new country gets applied to Summer and forgotten in Winter, or seasonal dates flip inconsistently. Furthermore, real-world seasonal speed changes are nuanced (e.g., Finland winter 80/100 car limits, Estonia 90->90/100/110 seasonal switch, Sweden/Norway/Baltics seasonal rules, plus anomalies observed in V1 `reference/winter/README.md` like Spanish winter truck motorway limit mismatches).
- **How to avoid:** Maintain a **single canonical country dataset** (`data/countries.yaml` or JSON + structured `speed_rules` with optional `summer` / `winter` overrides per `vehicle_speed_class` + `lane_speed_class` + `limit` / `urban_limit` / `max_limit`, and optional DST `time_zone` override if intentionally toggled). Both `summer` and `winter` Workshop artifacts compile deterministically from that single source of truth via `--edition summer|winter`.

### Pitfall 12: HashFS v2 Packing & Unneeded Texture Work on Linux CI
- **What happens:** Modders often assume Steam Workshop *requires* `.scs` files packed with `scs_packer.exe` (Windows-only 64-bit native tool from SCS, which had threading bugs fixed only in `2025-09-12`) or try generating `.dds`/`.tobj` texture overrides in Python (`Pillow 12.3` `DdsImagePlugin` emits 0 mipmaps and raises `NotImplementedError` on sRGB DXGI formats `72/78/88/91`, flagged NO-GO in V1).
- **How to avoid:** Direct inspection of live ETS2 Workshop `227300` items confirms `1820303287` ships **plain unpacked directories** (`universal/`), `3002586900` ships `.zip` and HashFS v2 `.scs`, and SCS `validation_errors_and_solutions_for_them.md` (`00003`) explicitly accepts **normal `.zip` files or uncompressed directories** (`universal/` or `universal.zip`). Since V2 consists solely of `.sii`/`.sui` text files and one `276x162` `.jpg` icon, ship `universal/` (for SteamCMD folder upload, so Steam's Steampipe delta-chunking works maximally) or deterministic `universal.zip` (for Phase A manual upload / standalone `.scs` release) with zero Windows-binary `.scs` packing or `.dds` baking required.

---

## Minor Pitfalls

- **UTF-8 BOM & CRLF noise in `.sii`/`.sui` and `description.txt`:** Note that ETS2's own `country.sii` in `def.scs` starts with a UTF-8 BOM (`\xef\xbb\xbfSiiNunit`), and several mods use `\r\n`, which works in the game engine; however, mixed encodings (`cp1251`/`latin1`) trigger `ERROR [00004] Malformed description file` in Workshop Uploader, and mixing CRLF/LF inflates diffs and breaks content-hash idempotency. Normalize all generated outputs to **UTF-8 without BOM** and `\n` (LF), validating strict UTF-8 decoding in tests.
- **`package_version` length / formatting:** Keep `package_version` concise (e.g., `"2026.46-summer"`) and keep unit names (`package_version_info : .universal`, `mod_package : .package_name`) `<= 12` chars per segment.
- **Unquoted vs quoted `iso_country_code`:** Observed both unquoted (`fra`, `deu`, `est`) and quoted (`"mne"`, `"bih"`) in vanilla `1.62` `def.scs` and `3249064596`; preserve vanilla formatting per country to avoid unexpected parser diffs.
- **Greek code mismatch (`EL` vs `GR`):** EC Weekly Oil Bulletin uses `EL` (Eurostat convention) for Greece while ETS2 `def/country/greece.sui` uses `country_code: "GR"` / `iso_country_code: grc`. Map explicitly in ingestion rather than assuming ISO 3166-1 alpha-2 everywhere.
- **Pre-`1.44` / legacy Workshop informational packages:** Not needed for a fresh V2 listing targeting ETS2 `1.62+`; adding `informational: true` packages just creates extra zip/folder maintenance unless back-supporting old game branches.

---

## Steam Workshop Publishing Architecture: Phase A -> Phase B Progression

### Phase A: Semi-Automatic (Recommended Initial Milestone — Zero Secrets)
1. **Trigger:** Weekly Friday `06:00 UTC` schedule + `workflow_dispatch`.
2. **Pipeline:**
   - Fetch EC Weekly Oil Bulletin (dynamic XLSX discovery + date freshness check) + national open-data APIs + multi-provider FX (`EUR/L` + optional local totem strings).
   - Compare against last committed normalized price snapshot (`prices.lock.json`): apply circuit-breaker fallback + sanity bounds; if **no material fuel or speed changes**, exit cleanly (`no-op`, zero release spam).
   - Build both clean Workshop roots in `dist/workshop/summer/` and `dist/workshop/winter/` (`versions.sii` + `universal/manifest.sii` + `universal/icon.jpg` + `universal/description.txt` + `universal/def/country/...`) AND standalone local `.scs` zips if desired.
   - Run **Offline SCS Validator Suite** enforcing all `00001`–`00010` & `WARN 00001`/`00002` rules (SII syntax, 12-char unit tokens, zero `compatible_versions` or `display_name` in Workshop `manifest.sii`, `276x162` `.jpg` `<1 MB`, UTF-8 `<1 MB`, zero `\` or `..`, zero extraneous root files, `mp_mod_optional: true`, `<=2` categories, `leftside_traffic` & `regions[]` invariants, `bus`/`train`/`tram` preservation).
   - Auto-generate `CHANGELOG_SUMMER.md` / `CHANGELOG_WINTER.md` summarizing exact per-country price diffs (`DE: 2.244 -> 2.189 EUR/L`) and upload both zip bundles as GitHub Actions Artifacts / GitHub Release.
3. **Human Step (1 minute/week):** Maintainer downloads artifact (or syncs local folder) and clicks **Upload** in SCS Workshop Uploader GUI (once installed on Windows via Steam Tools -> `AppID 421800`) using the generated changelog.

### Phase B: Full-Automatic (Graduated After Verification Spike)
1. **Mandatory Pre-Flight Verification Spike (Do NOT skip!):**
   - Provisions a dedicated unrestricted (`$5+` spent) Steam publisher account owning ETS2 (`227300`) — or tests on the owning account using a **Private/Hidden (`visibility: 2`) test Workshop item**.
   - Verifies in CI that:
     1. TOTP generated *after* `steamcmd` self-update (same shell step, immediately before `+login`) logs in cleanly across repeated runs over multiple days/IPs with 0 `Invalid Login Auth Code` failures.
     2. Uploading an existing `publishedfileid` with `manifest.vdf` omitting `title`/`description`/`previewfile`/`visibility` preserves Workshop title, description, tags, preview image, and visibility in Steam Community.
     3. ETS2 `1.62.3.3s` subscribes to the SteamCMD-uploaded item, downloads `versions.sii` + `universal/`, mounts in Mod Manager, and loads in-game without `game.log.txt` `[unit]`/`[mods]` warnings or Convoy incompatibilities.
     4. SCS Workshop Uploader (`421800`) still recognizes and can update the item after clearing `mod_items_data.sii`.
2. **Production Matrix Workflow Rules:**
   - **Isolation:** Two separate matrix jobs (`edition: summer`, `edition: winter`) OR isolated `stagingPath` per edition; **never** reuse `/tmp/steam_deploy/` across editions without cleaning (`rsync` in `m00nl1ght-dev/steam-workshop-deploy` lacks `--delete`).
   - **Idempotency Gate:** Compare semantic payload SHA-256 against `state/published.json`; **skip SteamCMD entirely on no-op**.
   - **Security Guardrails:** Trigger **only** on `schedule`, `workflow_dispatch`, or protected `main` (`if: github.event_name != 'pull_request'`); require GitHub Environment `steam-workshop-prod`; pin `steamcmd` Docker digest / action SHA; never print `$HOME/Steam/config/config.vdf` or raw auth logs on error.
   - **Metadata Split:** Pass only `appid` (`227300`), `publishedfileid` (`SUMMER_ID` / `WINTER_ID`), `contentfolder`, and `changenote` in `manifest.vdf`; manage Store tags, screenshots, visibility, and description either manually or via separate intentional release script.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| **Baseline Extraction & Schema** | Copying third-party `3249064596`/`3668352310` `.sui`/`.sii` files inherits Armenia `leftside_traffic: true`, Estonia `"@@tz_eest@@i"`, `3nK` blobs, and drops `1.62` `iceland.sui` or `bus` speed classes. | Extract and vendor clean vanilla `1.62.3.3s` `def.scs` country defs as baseline; patch surgically; assert invariants in tests. |
| **Fuel & FX Pipeline** | Thursday morning schedule beats EC publication (~17:00 CET); ECB `eurofxref-daily.xml` omits `RUB` & MENA/CIS/Balkan currencies and freezes on weekends; Cloudflare `403`s GlobalPetrolPrices. | Schedule Friday `06:00 UTC`; dynamic EC XLSX link resolution; multi-source FX + EUR vs local currency typed model; fail-safe stale retention + sanity bounds. |
| **Packaging & Offline Validation** | `compatible_versions[]` or `display_name` left in Workshop `manifest.sii`; `>2` categories; ZIP-renamed-`.scs`; unreferenced files in Workshop root; >12-char unit tokens. | Build dedicated Phase A **Offline SCS Validator** mirroring `00001`–`00010` + `WARN 00001`–`00002` + `276x162` JPEG check before packaging. |
| **Phase B SteamCMD Automation** | `config.vdf` token rot (`#56`); 30s TOTP expiry race during Docker/SteamCMD self-update; `rsync` without `--delete` mixing Summer & Winter; no-op subscriber spam; secret leaks (`GHSA-mj96-mh85-r574`). | Run Phase B hidden-item spike; mint TOTP inline post-self-update; isolate Summer/Winter staging; SHA-256 diff gate; pin commit SHAs + `steam-workshop-prod` environment. |
| **ETS2 `1.63`+ Upgrades** | `.universal` hides new DLC countries (`country.sii`) or new `vehicle_speed_class` entries on day 1 of `1.63`. | Add CI/manual baseline diff against updated `def.scs` whenever ETS2 bumps major version; ship update immediately after Open Beta verification. |

---

## "Looks Done But Isn't" Checklist

Before considering either Phase A packaging or Phase B auto-publish complete:

- [ ] Both `summer/` and `winter/` artifacts build from **one canonical data/rule model** — no divergent hand-edited country files.
- [ ] `versions.sii` sits cleanly at Workshop root alongside **only** `universal/` (or `universal.zip`) — no stray `README`, `.gitkeep`, or `.scs`-renamed ZIPs (`00003`).
- [ ] `manifest.sii` inside `universal/` omits `compatible_versions[]` (`00010`/`WARN 00002`) and omits `display_name` (`WARN 00001`), specifies `mp_mod_optional: true`, uses `<= 2` valid categories, and uses `<= 12`-char unit tokens.
- [ ] `icon.jpg` is exactly `276x162` JPEG `< 1 MB`, `description.txt` is UTF-8 `< 1 MB`, and all `.sii`/`.sui` files are plaintext `SiiNunit` (zero `3nK`, zero `\`, zero `..`).
- [ ] Spot-check ETS2 `1.62` invariants pass: Armenia `leftside_traffic` absent/false, Estonia `name: "Eesti"`, `regions[]` preserved on Bosnia/Norway/Finland/Sweden/Spain, `iceland.sui` present, `bus`/`train`/`tram` intact in `speed_limits.sii`.
- [ ] Re-running build + publish twice with identical upstream prices produces **0 uploads** (canonical SHA-256 no-op gate triggers).
- [ ] (`Phase B only`) Hidden test upload verified across 2+ consecutive days on GitHub-hosted runners with TOTP auth and verified in-game via ETS2 `1.62.3.3s` `game.log.txt` showing zero `[unit]`/`[mods]` errors.

---

## Sources & Confidence

| Source | Verification Basis | Confidence |
|---|---|---|
| SCS Workshop Uploader rules (`00001`–`00010`, `WARN 00001`–`00002`, `versions.sii`, `mod_manager`, `units`, changelog through `1.62.0`) | Local `.agents/skills/scs-modding-wiki/docs/` + live `modding.scssoft.com` (`oldid=5814`, `5757`, `5288`, `5726`) | **HIGH** |
| Local machine tool availability (`AppID 421800` absent) & ETS2 `1.62` game/mod forensics (`def.scs`, `locale.scs`, `3668352310`, `3668351598`, `3249064596`, `1820303287`, `3002586900`, `game.log.txt`) | Direct filesystem & binary HashFS v1/v2 inspection (`D:\SteamLibrary`, `C:\Program Files (x86)\Steam`, `D:\ETS2Data`) | **HIGH** |
| `m00nl1ght-dev/steam-workshop-deploy` behavior, `rsync` no-`--delete`, `manifest.vdf`, `action.yml`, `Dockerfile` | Direct scrape of `master` (`7abf9c7628c3bc79229c9bca93f7a7296fa82428`) | **HIGH** |
| SteamCMD `config.vdf` token rot vs TOTP (`#56`, `duty_guvnor@743bf12`), `GHSA-mj96-mh85-r574` | Direct GitHub issue/commit scrape + GitHub Advisory search | **HIGH** |
| SteamCMD `workshop_build_item` partial VDF updates, $5 non-limited & AppID ownership rules, Workshop Legal Agreement | Official Steamworks Workshop Implementation docs + `search_web` cross-check | **HIGH** (contributor update edge case: **MEDIUM** — avoid contributor workaround by using owning publisher account) |
| EC Weekly Oil Bulletin timing/XLSX layout, ECB `eurofxref-daily.xml` exclusions (`RUB` suspended Mar 2022; EGP/DZD/AMD absent; weekend freeze), Cloudflare `403` on GlobalPetrolPrices | Official EC/ECB pages + `tavily_search` + `search_web` | **HIGH** |
