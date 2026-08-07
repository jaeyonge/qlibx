# `DW/` Financial Data Catalog

Catalog snapshot: **2026-08-07**  
Source folder: `DW/`  
Inventory: **31 files** — 24 CSV, 6 Parquet, 1 JSON — **7,099,989,578 bytes (6.61 GiB)**

This catalog describes the files as they exist in the repository. CSV row counts exclude the header. Date ranges and entity counts were profiled from the full CSV files, with identifier and date columns read as text. Parquet files were cataloged as compact counterparts of same-named CSV files; their row-level parity was not independently tested.

## At a glance

| Data family | Main content | Observed coverage | Granularity |
|---|---|---:|---|
| Daily market data | OHLC, volume, value, shares, trading/status flags | 2015-01-02 to 2026-07-20 | Security × trading day |
| Index/classification | KOSPI 200 constituents and weights; FGSC classifications | 2017-05-24 to 2026-07-20; 2020-01-02 to 2026-04-29 | Security × date |
| Shares and dividends | Daily/annual share counts and dividend facts | 2015-01-02 to 2026-07-20 | Security/company × date or fiscal period |
| Financial statements | Separate and consolidated statement values, plus account mappings | Fiscal periods 2015-02 to 2026-05 | Company × fiscal period × statement type × account |
| Statement-family downloads | Broader DataGuide statement exports organized as financial statement, income statement, and cash flow | Fiscal periods 2018-02 to 2026-03 | Company × fiscal period × statement type × account |
| Mirror/reference data | Calendar, valuation, consensus, executives, major shareholders, and free float | Mostly 2018 to 2026 | Dataset-specific snapshot or daily observation |

## Identifier, date, and value conventions

- `종목약코드`, `기업코드`, and KOSPI 200 `종목코드2` use values such as `A000020`. They appear to share the same A-prefixed security/company namespace, but a formal crosswalk is not included.
- `종목코드`, `종목코드1`, and `지수ISIN` are ISIN-style identifiers such as `KR7090710005` and `KRD020020016`.
- Dates are delimiter-free strings: `YYYYMMDD` for daily dates and `YYYYMM` for fiscal/reference months. Keep them as strings during ingestion to preserve semantics.
- Statement values are stored in `재무데이타`. The applicable unit should be resolved through the account-code mapping rather than assumed globally.
- `결산구분` is encoded with `1`, `2`, `3`, `4`, `A`, `B`, `C`, and `D` in statement data. This folder does not contain a codebook for those values.
- Most missing values are blank strings. `dw_fng_free_float_ratio.csv` also contains two literal `None` values in `기준일자`.
- Some Korean labels are fixed-width and padded with trailing spaces, notably FGSC `종목명` and KOSPI 200 `지수명국문`. Trim before grouping or joining on labels.

## Logical datasets

### Daily stock prices

**File:** `DW/fng_stock_daily_prices.csv`  
**Rows / size:** 8,709,828 / 720.0 MiB  
**Coverage:** 2015-01-02 to 2026-07-20; 2,833 distinct trading dates; 5,670 securities  
**Candidate key:** (`종목약코드`, `거래일자`)

Columns:

`종목약코드`, `거래일자`, `기준가`, `시가`, `고가`, `저가`, `종가`, `전일종가`, `수정계수`, `거래량`, `거래대금`, `유통주식수`, `상장구분`, `락구분`, `거래정지구분`, `관리감리구분`

Use this as the primary daily price/volume table. Price adjustment is represented by `수정계수`; the catalog does not infer whether OHLC columns are already adjusted.

### KOSPI 200 membership and weights

**File:** `DW/fng_k200_members.csv`  
**Rows / size:** 449,429 / 101.0 MiB  
**Coverage:** 2017-05-24 to 2026-07-20; 2,244 dates; 309 historical constituents  
**Candidate key:** (`일자`, `지수ISIN`, `종목코드2`)

Columns:

`일자`, `지수ISIN`, `지수명국문`, `종목코드1`, `종목코드2`, `종목명국문`, `상장주식수`, `상장시가총액`, `지수주식수`, `당일가격`, `유동비율`, `지수시가총액`, `지수내비중`

The observed index label is KOSPI 200 (`코스피 200`), with padded and unpadded string variants.

### FGSC security classifications

**File:** `DW/DW_FNG_FGSC종목_20200101-20260430.csv`  
**Rows / size:** 3,507,557 / 241.9 MiB  
**Coverage:** 2020-01-02 to 2026-04-29; 1,549 dates; 2,822 securities; 62 FGSC codes  
**Candidate key:** (`종목약코드`, `일자`, `FGSC지수코드`)

Columns:

`종목약코드`, `일자`, `종목명`, `종목코드`, `FGSC지수코드`

The filename ends at 2026-04-30, while the latest observed record is 2026-04-29.

### Daily and annual share counts

#### Daily indicator share counts

**File:** `DW/fng_daily_indicator_share_counts.csv`  
**Rows / size:** 7,960,162 / 447.4 MiB  
**Coverage:** 2015-01-02 to 2026-07-20; 2,344 distinct dates; 5,789 securities  
**Candidate key:** (`종목약코드`, `거래일자`)

Columns:

`SOURCE_TABLE`, `종목약코드`, `거래일자`, `기말보통주주식수`, `기말우선주주식수`, `기말보통주자기주식수`, `기말우선주주기주식수`

`기말우선주주기주식수` appears to be a source typo for preferred treasury shares. Preserve the actual column name in ingestion code.

#### Annual indicator share counts

**File:** `DW/fng_annual_indicator_share_counts.csv`  
**Rows / size:** 34,878 / 3.1 MiB  
**Coverage:** annual reference dates 2015-12-31 to 2025-12-31; 4,835 securities  
**Candidate key:** (`종목약코드`, `기준일자`, `결산년도`)

Columns:

`SOURCE_TABLE`, `종목약코드`, `기준일자`, `시작일자`, `종료일자`, `결산년도`, `결산년도일`, `최근결산구분`, `보통주주식수평균`, `우선주주식수평균`, `주식수평균`

`결산년도` and `결산년도일` are stored as full dates despite their names. Their observed ranges extend back to 2014-01-31 and 2000-09-30 because they reference the fiscal period used in each later annual calculation.

### Dividends

**File:** `DW/fng_dividend_items.csv`  
**Rows / size:** 28,576 / 2.1 MiB  
**Coverage:** fiscal months 2015-03 to 2026-03; 1,797 companies  
**Candidate key:** (`기업코드`, `회계년월`, `배당구분1`, `배당구분2`)

Columns:

`SOURCE_TABLE`, `기업코드`, `회계년월`, `배당구분1`, `배당구분2`, `대주주현금배당율`, `소주주현금배당율`, `대주주주식배당율`, `소주주주식배당율`, `현금배당금`, `주식배당금`, `배당금합계`, `대주주주당현금배당`, `소주주주당현금배당`, `대주주주당주식배당율`, `소주주주당주식배당율`

Observed `배당구분1` codes are `10` through `90` in increments of 10; `배당구분2` is `10` or `20`. Their labels are not supplied in this folder.

### Financial statements

All statement value tables share this six-column long format:

`SOURCE_TABLE`, `기업코드`, `회계년월`, `결산구분`, `계정코드`, `재무데이타`

The natural join to the mapping tables is `계정코드`. A candidate fact-table key is (`기업코드`, `회계년월`, `결산구분`, `계정코드`), but uniqueness has not been asserted.

#### Compact/core statement extracts

| File | Scope | Rows | Size | Fiscal coverage | Companies | Accounts |
|---|---|---:|---:|---:|---:|---:|
| `DW/fng_separate_financial_statement_items.csv` | Separate statements | 1,645,689 | 90.9 MiB | 2015-02 to 2026-03 | 3,014 | 9 |
| `DW/fng_consolidated_financial_statement_items.csv` | Consolidated statements | 1,642,566 | 100.4 MiB | 2015-02 to 2026-05 | 2,631 | 11 |

These files contain a small set of commonly used statement accounts over a longer history than the broader DataGuide exports below.

#### Broader DataGuide statement exports

| File | Scope | Rows | Size | Fiscal coverage | Companies | Accounts |
|---|---|---:|---:|---:|---:|---:|
| `DW/fng_dataguide_separate_statement_items.csv` | Separate statements | 11,966,456 | 653.2 MiB | 2018-02 to 2026-03 | 2,904 | 111 |
| `DW/fng_dataguide_consolidated_statement_items.csv` | Consolidated statements | 12,046,107 | 727.4 MiB | 2018-02 to 2026-03 | 2,615 | 142 |

These two files are byte-for-byte identical to the corresponding files in `dataguide_mapped_statement_download/financial_statement/`; see “Duplicates and overlap.”

#### Account-code mappings

Both mappings use this schema:

`계정코드`, `보고`, `업종`, `계정식별코드`, `계정과목명`, `계정영문명`, `단위`, `단위영문명`

| File | Rows | Size | Unique account codes | Observed report codes | Observed industry codes |
|---|---:|---:|---:|---|---|
| `DW/fng_ifrs_account_code_mapping.csv` | 40,538 | 3.7 MiB | 40,538 | `10`, `30`, `40`, `60` | `01`, `02`, `03`, `04`, `06`, `07`, `08`, `09` |
| `DW/fng_gaap_account_code_mapping.csv` | 20,496 | 1.9 MiB | 20,496 | `10`, `30`, `40` | `01`–`09` |

Units observed across the mappings include KRW (`원`), thousand KRW (`천원`), shares (`주`), percentages (`%`), multiples (`배`), days (`일`), occurrences (`회`), and—in IFRS only—people (`명`) or unitless (`-`/blank).

### Statement-family download folder

Folder: `DW/dataguide_mapped_statement_download/`

These files use the same six-column long schema as the financial-statement tables. Folder names indicate the intended statement family. The account selections overlap, so do not concatenate the families without checking for duplicate fact keys.

| Family | Scope | File | Rows | Size | Fiscal coverage | Companies | Accounts |
|---|---|---|---:|---:|---:|---:|---:|
| Financial statement | Separate | `financial_statement/fng_dataguide_separate_statement_items.csv` | 11,966,456 | 653.2 MiB | 2018-02 to 2026-03 | 2,904 | 111 |
| Financial statement | Consolidated | `financial_statement/fng_dataguide_consolidated_statement_items.csv` | 12,046,107 | 727.4 MiB | 2018-02 to 2026-03 | 2,615 | 142 |
| Income statement | Separate | `income_statement/fng_dataguide_separate_statement_items.csv` | 3,433,348 | 186.1 MiB | 2018-02 to 2026-03 | 2,908 | 29 |
| Income statement | Consolidated | `income_statement/fng_dataguide_consolidated_statement_items.csv` | 3,293,886 | 197.9 MiB | 2018-02 to 2026-03 | 2,543 | 33 |
| Cash flow | Separate | `cash_flow/fng_dataguide_separate_statement_items.csv` | 3,755,980 | 204.2 MiB | 2018-02 to 2026-03 | 2,908 | 36 |
| Cash flow | Consolidated | `cash_flow/fng_dataguide_consolidated_statement_items.csv` | 3,342,858 | 200.8 MiB | 2018-02 to 2026-03 | 2,619 | 49 |

Paths in this table are relative to `DW/dataguide_mapped_statement_download/`.

### Mirror/reference datasets

Folder: `DW/dw_fng_mirror/`

Each tabular dataset is supplied as CSV and Parquet. The statistics below come from the CSV. Use Parquet for faster typed analytics and CSV when portability or manual inspection matters.

#### Trading calendar

**CSV / Parquet:** `dw_fng_calendar.csv` (3,103 rows, 178.9 KiB) / `dw_fng_calendar.parquet` (81.7 KiB)  
**Coverage:** 2018-01-01 to 2026-06-30  
**Key:** `일자` (also declared in the manifest)

Columns:

`source_table`, `일자`, `전영업일`, `요일구분`, `주식개장구분`, `채권개장구분`, `미국개장구분`, `총일차`, `총주차`, `휴일여부`, `월말여부`

#### Daily valuation

**CSV / Parquet:** `dw_fng_valuation.csv` (5,831,522 rows, 493.0 MiB) / `dw_fng_valuation.parquet` (73.5 MiB)  
**Coverage:** 2018-01-02 to 2026-06-08; 2,067 dates; 4,281 securities  
**Candidate key:** (`종목약코드`, `일자`)

Columns:

`source_table`, `종목약코드`, `일자`, `베타`, `FORWARD_EPS`, `FORWARD_PER`, `FORWARD_PERIF`, `BPS`, `PBR`, `추정BPS`, `추정PBR`, `배당수익율`, `EV_EBITDA`, `순이익FY1`, `순이익FY1IF`, `순이익FY2`, `순이익FY2IF`, `순이익12MFWD`, `순이익12MFWDIF`

#### Daily consensus

**CSV / Parquet:** `dw_fng_daily_consensus.csv` (9,576,361 rows, 742.6 MiB) / `dw_fng_daily_consensus.parquet` (77.0 MiB)  
**Observation coverage:** 2018-01-02 to 2026-06-08; 2,065 dates; 1,843 companies  
**Forecast fiscal coverage:** 2017-12 to 2031-12  
**Candidate key:** (`일자`, `보고서구분`, `기업코드`, `결산년월`, `결산구분`)

Columns:

`source_table`, `일자`, `보고서구분`, `기업코드`, `결산년월`, `결산구분`, `매출액`, `영업이익`, `조정영업이익`, `순부채`, `순이익`, `지배주주순이익`

Observed `보고서구분` values are `B` and `D`.

#### Executive information

**CSV / Parquet:** `dw_fng_executive_info.csv` (248,063 rows, 42.2 MiB) / `dw_fng_executive_info.parquet` (12.9 MiB)  
**Coverage:** fiscal months 2018-03 to 2025-12; 3,201 companies; 40,623 distinct names  
**Candidate key:** (`기업코드`, `회계년월`, `SEQ`)

Columns:

`source_table`, `기업코드`, `회계년월`, `SEQ`, `구분`, `직명코드`, `직명`, `성명`, `생년월일`, `소유보통주수`, `소유우선주수`, `학력1`, `학력2`, `학력3`, `경력1`, `경력2`, `경력3`

`생년월일` includes partial dates encoded with `00` components, for example `19460100`; do not parse it as a strict calendar date without a partial-date policy.

#### Major shareholders

**CSV / Parquet:** `dw_fng_major_shareholders.csv` (637,586 rows, 54.1 MiB) / `dw_fng_major_shareholders.parquet` (9.6 MiB)  
**Coverage:** fiscal months 2018-02 to 2025-12; 3,303 companies; 43,435 distinct shareholder-name strings  
**Key:** (`기업코드`, `회계년월`, `SEQ`) (also declared in the manifest)

Columns:

`source_table`, `기업코드`, `회계년월`, `SEQ`, `주주구분`, `관계`, `성명`, `보통주식수`, `보통주식비율`, `우선주식수`, `우선주식비율`

#### Free-float ratio

**CSV / Parquet:** `dw_fng_free_float_ratio.csv` (45,917 rows, 2.8 MiB) / `dw_fng_free_float_ratio.parquet` (444.7 KiB)  
**Coverage:** application dates 2018-01-05 to 2026-06-15; 3,345 securities  
**Reference-month coverage:** 2017-06 to 2026-03, excluding two literal `None` values  
**Key:** (`종목약코드`, `적용일자`) (also declared in the manifest)

Columns:

`source_table`, `종목약코드`, `적용일자`, `기준일자`, `비유동주식수`, `보통주식지분`

#### Mirror manifest

**File:** `DW/dw_fng_mirror/mirror_manifest.json` (2.4 KiB)

The manifest records an incremental/backfill extraction configuration, annual chunks from 2015 through 2017, and declared schemas/keys for `free-float-ratio`, `major-shareholders`, and `calendar`. Its `coverage` array is empty, and it does not list valuation, consensus, or executive information. Treat the profiled CSV coverage above—not the manifest—as the authoritative description of the files currently present.

## File inventory

| Path under `DW/` | Format | Data rows | Size |
|---|---|---:|---:|
| `DW_FNG_FGSC종목_20200101-20260430.csv` | CSV | 3,507,557 | 241.9 MiB |
| `fng_annual_indicator_share_counts.csv` | CSV | 34,878 | 3.1 MiB |
| `fng_consolidated_financial_statement_items.csv` | CSV | 1,642,566 | 100.4 MiB |
| `fng_daily_indicator_share_counts.csv` | CSV | 7,960,162 | 447.4 MiB |
| `fng_dataguide_consolidated_statement_items.csv` | CSV | 12,046,107 | 727.4 MiB |
| `fng_dataguide_separate_statement_items.csv` | CSV | 11,966,456 | 653.2 MiB |
| `fng_dividend_items.csv` | CSV | 28,576 | 2.1 MiB |
| `fng_gaap_account_code_mapping.csv` | CSV | 20,496 | 1.9 MiB |
| `fng_ifrs_account_code_mapping.csv` | CSV | 40,538 | 3.7 MiB |
| `fng_k200_members.csv` | CSV | 449,429 | 101.0 MiB |
| `fng_separate_financial_statement_items.csv` | CSV | 1,645,689 | 90.9 MiB |
| `fng_stock_daily_prices.csv` | CSV | 8,709,828 | 720.0 MiB |
| `dataguide_mapped_statement_download/cash_flow/fng_dataguide_consolidated_statement_items.csv` | CSV | 3,342,858 | 200.8 MiB |
| `dataguide_mapped_statement_download/cash_flow/fng_dataguide_separate_statement_items.csv` | CSV | 3,755,980 | 204.2 MiB |
| `dataguide_mapped_statement_download/financial_statement/fng_dataguide_consolidated_statement_items.csv` | CSV | 12,046,107 | 727.4 MiB |
| `dataguide_mapped_statement_download/financial_statement/fng_dataguide_separate_statement_items.csv` | CSV | 11,966,456 | 653.2 MiB |
| `dataguide_mapped_statement_download/income_statement/fng_dataguide_consolidated_statement_items.csv` | CSV | 3,293,886 | 197.9 MiB |
| `dataguide_mapped_statement_download/income_statement/fng_dataguide_separate_statement_items.csv` | CSV | 3,433,348 | 186.1 MiB |
| `dw_fng_mirror/dw_fng_calendar.csv` | CSV | 3,103 | 178.9 KiB |
| `dw_fng_mirror/dw_fng_calendar.parquet` | Parquet | See paired CSV | 81.7 KiB |
| `dw_fng_mirror/dw_fng_daily_consensus.csv` | CSV | 9,576,361 | 742.6 MiB |
| `dw_fng_mirror/dw_fng_daily_consensus.parquet` | Parquet | See paired CSV | 77.0 MiB |
| `dw_fng_mirror/dw_fng_executive_info.csv` | CSV | 248,063 | 42.2 MiB |
| `dw_fng_mirror/dw_fng_executive_info.parquet` | Parquet | See paired CSV | 12.9 MiB |
| `dw_fng_mirror/dw_fng_free_float_ratio.csv` | CSV | 45,917 | 2.8 MiB |
| `dw_fng_mirror/dw_fng_free_float_ratio.parquet` | Parquet | See paired CSV | 444.7 KiB |
| `dw_fng_mirror/dw_fng_major_shareholders.csv` | CSV | 637,586 | 54.1 MiB |
| `dw_fng_mirror/dw_fng_major_shareholders.parquet` | Parquet | See paired CSV | 9.6 MiB |
| `dw_fng_mirror/dw_fng_valuation.csv` | CSV | 5,831,522 | 493.0 MiB |
| `dw_fng_mirror/dw_fng_valuation.parquet` | Parquet | See paired CSV | 73.5 MiB |
| `dw_fng_mirror/mirror_manifest.json` | JSON | — | 2.4 KiB |

## Relationships and likely joins

| From | To | Join fields | Notes |
|---|---|---|---|
| Daily prices | Daily share counts | `종목약코드`, `거래일자` | Direct daily security join; date coverage counts differ, so use an explicit join policy. |
| Daily prices | Daily valuation | `종목약코드`, price `거래일자` = valuation `일자` | Valuation begins in 2018 and ends earlier than prices. |
| Daily prices | FGSC | `종목약코드`, price `거래일자` = FGSC `일자` | FGSC is available only from 2020 through April 2026. |
| Daily prices | KOSPI 200 | price `종목약코드` = K200 `종목코드2`; date equality | Use membership rows to construct point-in-time index universes and weights. |
| Statement facts | IFRS/GAAP mappings | `계정코드` | Select the accounting-regime mapping appropriate to the source before interpreting names/units. |
| Company-level datasets | Security-level datasets | `기업코드` ↔ `종목약코드` | Codes look compatible, but validate one-to-one/many-to-one behavior before treating this as a guaranteed crosswalk. |
| Any daily dataset | Calendar | daily date field = calendar `일자` | Useful for exchange-open, holiday, prior-business-day, and month-end flags. |

## Duplicates, overlap, and ingestion cautions

1. **Exact duplicates:** SHA-256 checks show that the two root DataGuide statement files are exact copies of their `financial_statement/` counterparts:
   - `fng_dataguide_separate_statement_items.csv` = `dataguide_mapped_statement_download/financial_statement/fng_dataguide_separate_statement_items.csv`
   - `fng_dataguide_consolidated_statement_items.csv` = `dataguide_mapped_statement_download/financial_statement/fng_dataguide_consolidated_statement_items.csv`
2. **Overlapping statement families:** The financial-statement, income-statement, and cash-flow account selections are not guaranteed to be disjoint. Deduplicate on the full candidate fact key if combining them.
3. **CSV/Parquet pairs:** Same-named mirror files represent the same logical dataset, but this catalog did not perform a value-by-value or row-count parity test between formats.
4. **Point-in-time safety:** Fiscal values, consensus forecasts, classifications, and ownership snapshots should be aligned using their publication/application semantics. The folder does not include explicit release timestamps for every dataset, so fiscal period alone must not be treated as an availability date.
5. **Identifiers and dates:** Read codes and date strings as text. Automatic numeric inference can remove the `A` prefix, strip leading zeroes from encoded categories, or misinterpret partial dates.
6. **Source naming:** `SOURCE_TABLE` is uppercase in the root exports, while the mirror files use lowercase `source_table`.
7. **Unverified keys:** Keys labeled “candidate” were inferred from schema and granularity; duplicate-key checks were outside this inventory pass.
