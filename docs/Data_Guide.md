# Developer Guide: Cleaned KYC & AML Datasets

Welcome! This guide explains the structure, columns, and purposes of the preprocessed datasets located in the `/data/` directory. All datasets have been standardized, deduplicated, and enriched to make them ready for training machine learning models.

---

## What is in `/data/`?

After running the preprocessing pipeline, you have clean tables stored in two formats:
1.  **CSV files (`.csv`)**: Text files where values are separated by commas. Easily readable in text editors or Excel.
2.  **Parquet files (`.parquet`)**: Binary database files. They are compressed, load much faster than CSVs, and preserve data types (like floats, dates, and arrays).

---

## 1. SAML-D Transactions (`aml_transactions/SAML-D_cleaned.parquet`)

### 📌 What is this dataset about?
Imagine a bank's ledger recording every transaction sent between accounts (wire transfers, crypto swaps, cash withdrawals). This dataset simulates **9.5 million transactions** processed in a real banking network.
*   **The Problem**: Criminals try to disguise illicit money as clean funds by breaking transfers into small amounts (Structuring), routing them through multiple international banks (Layering), or depositing cash.
*   **The ML Goal**: Identify transaction patterns that look suspicious. We train classifiers to flag when a transaction sequence looks like money laundering.
*   **Target Column**: `Is_laundering` (`0` = Normal transaction, `1` = Suspicious transaction).

### Key Columns:
*   `Sender_account` / `Receiver_account` (Integer): Unique ID codes representing the bank accounts.
*   `Amount` (Float): The transaction amount, scaled (normalized) so that the mean is `0` and standard deviation is `1`.
*   `amount_log` (Float): The natural log of the amount (`log1p`), also scaled. Log-transforming the transaction value handles the extreme range of transaction amounts.
*   `Payment_currency` / `Received_currency` (Integer): Encoded representation of currency (e.g. `0` = USD, `1` = EUR, etc.).
*   `Sender_bank_location` / `Receiver_bank_location` (Integer): Encoded bank countries.
*   `Payment_type` (Integer): Type of transaction (e.g. Cash Deposit, ACH, Credit Card).
*   `Laundering_type` (Integer): The specific typology/pattern of transaction (e.g. Structuring, Normal Deposits, Layering).
*   `Datetime` / `Date` (Datetime): Standardized timestamps and calendar dates.
*   `is_cross_border` (Binary): `1` if the sender's bank country is different from the receiver's bank country; `0` otherwise.
*   `is_currency_conversion` (Binary): `1` if payment currency is different from received currency; `0` otherwise.
*   `hour_of_day` (Integer): The hour of the transaction (`0` to `23`).
*   `day_of_week` (Integer): The day of the week (`0` = Monday, `6` = Sunday).
*   `is_amount_outlier` (Binary): `1` if the amount falls outside standard limits (IQR outlier); `0` otherwise.

---

## 2. PrivacyQA Dataset (`privacy_qa/train_cleaned.csv` & `test_cleaned.csv`)

### 📌 What is this dataset about?
Privacy policies (terms of service, app policies) are long, boring, and full of legalese. Most users never read them. This dataset contains questions asked by real users (e.g., *"Does this app track my location?"*) matched against specific sentences inside privacy policies.
*   **The Problem**: We want to make legal policies searchable. A user should be able to ask a chatbot a question, and the chatbot should find the sentence that answers it.
*   **The ML Goal**: Teach models to read a policy paragraph and predict if a specific sentence answers the user's question.
*   **Target Column**: `Label_encoded` (Train) / `Any_Relevant_encoded` (Test) (`0` = Irrelevant segment, `1` = Relevant segment).

### Key Columns:
*   `cleaned_Query` (String): Standardized, clean user question.
*   `cleaned_Segment` (String): Standardized, clean sentence from the privacy policy.
*   `query_word_count` / `segment_word_count` (Float): The word lengths of queries/segments, standardized using scaling.
*   `word_overlap_count` (Float): Number of unique matching words shared between the query and the segment (excluding common stopwords).
*   `word_overlap_ratio` (Float): Ratio of overlap count to query word count.
*   `tfidf_similarity` (Float): Vector similarity (cosine similarity) score between the query and segment vocabulary.
*   `is_query_length_outlier` / `is_segment_length_outlier` (Binary): `1` if length is abnormally long or short; `0` otherwise.
*   `first`, `third`, `datasecurity`, `dataretention`, `user_access`, `user_choice`, `other`, `audiences`, `unknown` (Binary): Joined categories representing the topic of the query. For example, if `datasecurity` is `1`, the question is about data protection measures.

---

## 3. OFAC SDN List (`sanctions/ofac_sdn_cleaned.csv`)

### 📌 What is this dataset about?
Think of this as the **US Government's master blacklist**. It contains the names of individuals, companies, ships, and aircraft associated with terrorism, drug trafficking, or hostile foreign governments (e.g. entities blocked under economic sanctions).
*   **The Problem**: Banks are legally forbidden from doing business with anyone on this list. If they do, they face billions of dollars in fines.
*   **The ML Goal**: Use this list to build name-matching tools. Since names can have spelling mistakes or translations (e.g. *"Al-Qaeda"* vs *"Al Qa'ida"*), models use fuzzy matching to flag matching names.

### Key Columns:
*   `name` (String): Standardized name of the blocked entity.
*   `type` (String): Category of target (`individual`, `entity`, `vessel`, `aircraft`, or `None` if unknown).
*   `type_encoded` (Integer): Mapped integer for target categories.
*   `program` (String): Sanctions programs (e.g. Counter Terrorism, Russia Sanctions).
*   `program_encoded` (Integer): Mapped integer for sanctions programs.
*   *Note*: Empty placeholders (which originally appeared as raw `-0-` strings) have been resolved to standard `'None'` text.

---

## 4. OpenSanctions Targets (`sanctions/opensanctions_targets_cleaned.parquet`)

### 📌 What is this dataset about?
Similar to the OFAC list, but on a global scale. It combines watchlists from **100+ countries** and international bodies (UN, EU, UK, Interpol). It also contains a database of **PEPs (Politically Exposed Persons)**, who are politicians, judges, or military leaders who have a higher risk of bribery or corruption.
*   **The Problem**: Compliance officers need a single file to search for international clients, politicians, or shell companies across the globe.
*   **The ML Goal**: Cross-reference incoming corporate names and beneficial owners against this global watchlist to generate a screening risk score.

### Key Columns:
*   `id` (String): Unique global identifier.
*   `schema` (String): Entity schema classification (e.g., `Person`, `Company`, `Vessel`).
*   `name` (String): Cleaned target name.
*   `aliases` (String): Comma-separated list of known alternative names.
*   `countries` (String): Comma-separated list of countries associated with this entity.
*   `first_seen` / `last_seen` / `last_change` (Datetime): Timestamps tracking the record status.

---

## 5. LexGLUE / EurLex (`eurlex/<subdir>/*.parquet`)

### 📌 What is this dataset about?
LexGLUE is a legal intelligence benchmark. The `eurlex` portion contains thousands of **European Union laws** (legal codes, treaties, regulations). Each document has been tagged by legal experts with one or more categories (EuroVoc labels) such as *agriculture, finance, environmental law, or human rights*.
*   **The Problem**: A legal compliance department gets hundreds of new pages of legal codes weekly. Manual categorizing is too slow.
*   **The ML Goal**: Train models to read a document and automatically predict which legal categories apply, helping companies discover what new obligations they must audit.

### Key Columns:
*   `text` (String or Sequence): Cleaned legal document paragraphs.
*   `labels` (Sequence): Lists of integer IDs representing legal categories (EuroVoc labels).

---

## 6. GDPR Full Text (`gdpr_text/gdpr_cleaned.json`)

### 📌 What is this dataset about?
The complete, official text of the **General Data Protection Regulation (GDPR)**, which is the cornerstone privacy law in Europe.
*   **Purpose**: The data is formatted as a structured JSON tree, making it easy for an AI agent to lookup specific articles (e.g., Article 17 "Right to be Forgotten" or Article 32 "Security of Processing") to quote them as legal justification in a Suspicious Activity Report (SAR).

---

## 7. Synthetic KYC & Transaction Risk Dataset (`kyc_profiles/synthetic_kyc_dataset.csv`)

### 📌 What is this dataset about?
This dataset contains synthetic corporate client profiles enriched with FATF/OFAC risk indicators, PEP flags, industry sector-based risk, and transaction anomaly signals. It simulates the onboarding KYC profiles of corporate entities.
*   **The Problem**: Compliance departments need to identify high-risk client profiles based on corporate structure, PEP association, FATF risk of their country of origin, and sector-specific risks.
*   **The ML/Rule Goal**: Set baseline risk scores for newly onboarded entities using predefined weights and tag high-risk clients for active watchlist monitoring.

### Key Columns:
*   `client_id` (String): Unique client identifier (e.g., `C_0001`).
*   `client_name` (String): Synthetic company name.
*   `client_type` (String): Corporate, Individual, or Financial Institution.
*   `country` (String): Primary jurisdiction.
*   `sector` (String): Industry sector (e.g., Real Estate, Finance, Mining, Tech).
*   `sector_risk` (String): Sector-level risk category (`Low`, `Medium`, `High`).
*   `pep_flag` (Binary): `1` if a Politically Exposed Person (PEP) is associated; `0` otherwise.
*   `sanctions_flag` (Binary): `1` if the entity is directly listed on a sanctions list; `0` otherwise.
*   `fatf_country_flag` (Binary): `1` if country is FATF blacklisted or greylisted; `0` otherwise.

---

## Loading Cleaned Data in Python (Pandas)

Here is how you can read these cleaned files in Python to begin your analysis:

```python
import pandas as pd

# 1. Read SAML-D Transactions (Parquet format)
df_transactions = pd.read_parquet("/data/aml_transactions/SAML-D_cleaned.parquet")
print("SAML-D Transactions columns:", df_transactions.columns)

# 2. Read PrivacyQA Train Data (CSV format)
df_privacy_train = pd.read_csv("/data/privacy_qa/train_cleaned.csv")
print("PrivacyQA Train Shape:", df_privacy_train.shape)

# 3. Read OpenSanctions Targets (Parquet format)
df_sanctions = pd.read_parquet("/data/sanctions/opensanctions_targets_cleaned.parquet")
print("OpenSanctions targets count:", len(df_sanctions))

# 4. Read OFAC SDN List (CSV format)
df_ofac = pd.read_csv("/data/sanctions/ofac_sdn_cleaned.csv")
print("OFAC SDN sample records:")
print(df_ofac[['name', 'type', 'program']].head(5))

# 5. Read Synthetic KYC Dataset (CSV format)
df_kyc = pd.read_csv("data/kyc_profiles/synthetic_kyc_dataset.csv")
print("Synthetic KYC Dataset client count:", len(df_kyc))
```
