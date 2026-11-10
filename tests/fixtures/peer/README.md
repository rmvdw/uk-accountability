# Peer migration fixtures (genuine responses)

Built from responses fetched on a GitHub Actions runner on 2026-11-09 (probe workflow
for #21 and #22), packed in the `per_1000` adapter's bundle format:

- `oecd_permanent_bundle.json`: OECD `DSD_MIG_INT@DF_MIG_INT_PER` (CSV with labels,
  2019 onwards), **trimmed to the G7 plus Australia** to keep the file small, and the
  World Bank `SP.POP.TOTL` response for the G7, 2019 to 2025.
- `unhcr_asylum_bundle.json`: UNHCR `asylum-applications` for each G7 country (Germany
  is `GFR`), 2019 to 2025, and the same World Bank response.

Request URLs in the bundles are the probe's, which differ slightly from the adapter's
(extra parameters only). These are test inputs, not published data.
