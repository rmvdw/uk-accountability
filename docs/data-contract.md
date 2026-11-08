# Data contract

Agents own this document and may change it in a PR. Changes that alter what an indicator *means* go to Ross.

## Layout

| Path | Contents |
| --- | --- |
| `indicators/<id>.yml` | Indicator definition (registry). One file per indicator. |
| `config/geographies.yml` | Canonical geography IDs, labels and code mappings. |
| `config/peers.yml` | Named peer groups. |
| `data/raw/<id>/` | Saved source responses, exactly as received. |
| `data/observations/<id>.csv` | Parsed, validated observations (published). |
| `data/manifest.json` | One entry per saved raw response: provenance. |
| `data/checks.json` | One entry per indicator: last attempt and last successful live check. |
| `tests/fixtures/` | Test-only data. Never published. |

The schema is enforced in code by `src/ukdash/schema.py` (pydantic). If this document and the code disagree, fix one of them in the same PR.

## Observations table

Long format, one CSV per indicator, UTF-8, header row:

| Column | Type | Rule |
| --- | --- | --- |
| `indicator_id` | string | Matches the YAML file name. |
| `geography_id` | string | A canonical ID from `config/geographies.yml`. |
| `period` | string | See periods below. |
| `frequency` | `A`, `Q`, `M`, `M3` | Must match the period format. |
| `value` | number or empty | Empty means missing; requires a `status`. |
| `status` | string or empty | Source flags, e.g. `provisional`, `estimated`, `break`, `missing`. |

Unique key: `(indicator_id, geography_id, period)`. Duplicates fail validation. Missing values stay missing; never fill or interpolate.

## Periods

| Frequency | Format | Example | Meaning |
| --- | --- | --- | --- |
| `A` | `YYYY` | `2024` | Calendar year |
| `Q` | `YYYY-Qn` | `2024-Q3` | Calendar quarter |
| `M` | `YYYY-MM` | `2024-09` | Calendar month |
| `M3` | `YYYY-MM` | `2024-09` | Rolling three months *ending* that month (e.g. ONS LFS). Never relabel as a quarter. |

Financial years, academic years and other conventions get their own frequency code when first needed; add them here first.

## Geography

One canonical ID per entity, prefixed by scheme:

- Countries: `iso:` + ISO 3166-1 alpha-3, e.g. `iso:USA`.
- The United Kingdom is `iso:GBR`. ISO `GB`/`GBR` means the whole UK including Northern Ireland, **never** Great Britain.
- UK sub-divisions and GB: `gss:` + ONS GSS code, e.g. `gss:K03000001` (Great Britain).

`config/geographies.yml` maps provider codes (OECD, World Bank, ONS) to canonical IDs and gives display labels. Pages display labels from that file only; templates never hard-code geography names.

A code lookup does not prove coverage. Each indicator records what its source series actually covers (`geography_note`), e.g. an ONS "UK" series that is really GB-only.

## Indicator definition (`indicators/<id>.yml`)

Required fields are enforced by `IndicatorDefinition` in `src/ukdash/schema.py`. In brief:

- `id`, `title`, `status` (`draft` or `published`; only `published` indicators appear on the site)
- `what_it_measures`, `why_it_matters`: plain English, one or two sentences each
- `unit`, `decimals`, `frequency`, `direction` (`higher_is_better`, `lower_is_better` or `neutral`)
- `coverage`: population/age, seasonal adjustment, and `geography_note`
- `source`: publisher, dataset, URL, licence, attribution text, `adapter` name and adapter `query`
- `peers`: a group ID from `config/peers.yml`, plus documented `exclusions`
- `comparison`: `common_latest_period` (default) — compare peers only on the latest period that every included geography has
- `caveats`: list of plain-English limitations
- `check_cadence_days`: how often a live check is expected; drives the overdue flag

## Provenance (`data/manifest.json`)

One entry per raw file: `indicator_id`, `path`, `sha256`, `request` (URL or description), `retrieval_method` (`live` or `manual`), `retrieved_at` (UTC ISO 8601), `publisher_release_date` (if known), `licence`. Manual downloads are allowed to seed an indicator if the origin is documented and `retrieval_method` is `manual`.

## Checks (`data/checks.json`)

Per indicator: `last_attempt_at`, `last_attempt_result` (`ok`, `unchanged`, `failed`), `last_successful_check_at`. See `docs/refresh-policy.md` for when each field moves.
