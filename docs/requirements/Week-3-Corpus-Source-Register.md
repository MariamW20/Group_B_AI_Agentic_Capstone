# Week 3 Controlled Corpus and Source Register

Project: Centenary Bank Customer Support AI
Date: 2026-09-17
Status: Draft Week 3 evidence artifact

## Purpose

This register documents the controlled corpus used for Week 3 retrieval and the provenance of each selected record. The seed CSV has 98 data rows, and the controlled corpus below uses a frozen 24-record slice so evaluation can be repeated against the same inputs.

## Corpus selection rule

- Use 10 to 50 equivalent records.
- Prefer approved public or synthetic sources only.
- Do not add uncited ad hoc answers.
- If a record cannot be traced back to a listed source, exclude it from the corpus.
- Treat the root CSV as the working corpus seed; the register records how each selected row maps to approved source anchors.

Working corpus seed: [centenary_bank_faqs.csv](../../centenary_bank_faqs.csv)

## Source Register

| Source ID | Source | Type | Location | Role in corpus | Notes |
|---|---|---|---|---|---|
| G-01 | AI Boundary Matrix | governance | [docs/requirements/AI_Boundary_Matrix.docx](../requirements/AI_Boundary_Matrix.docx) | Defines what the assistant may answer, what must be escalated, and what data is excluded | Primary control source for corpus scope |
| G-02 | Project Charter | governance | [docs/requirements/Project_Charter_Final_3_Pages.docx](../requirements/Project_Charter_Final_3_Pages.docx) | Confirms the project scope and support boundaries | Referenced by the boundary matrix |
| R-01 | Centenary Bank official website | public reference | https://www.centenarybank.co.ug/ | General bank facts, products, branch/support references | Public source anchor |
| R-02 | Centenary Bank Treasury Platform FAQ | public reference | https://centetreasury.centenarybank.co.ug/ | Product and procedure references | Public source anchor for fee/product items |
| R-03 | Centenary Bank CSD Account application | public reference | https://centetreasury.centenarybank.co.ug/open-csd/ | Account-opening procedure and requirements | Public source anchor |
| R-04 | Bank of Uganda Financial Inclusion and Consumer Protection | regulatory reference | https://bou.or.ug/financial_inclusion_and_consumer_protection | Consumer protection, fair treatment, complaint handling | Governance anchor |
| R-05 | Bank of Uganda Supervision / Published Charges | regulatory reference | https://bou.or.ug/supervision | Published fees and charges | Governance anchor |
| R-06 | Personal Data Protection Office obligations page | regulatory reference | https://www.pdpo.go.ug/information-center/organisation | Data protection and controller obligations | Governance anchor |
| R-07 | Uganda Data Protection and Privacy Regulations 2021 | regulatory reference | https://pdpo.go.ug/media/2022/03/Data_Protection_and_Privacy_Regulations-2021.pdf | Data rights, lawful processing, privacy controls | Governance anchor |

## Corpus Records

The following records are selected from the CSV as the controlled corpus slice for retrieval testing. Each row is preserved with a stable record ID and a source-basis note.

| Record ID | CSV row | Topic | Intended answer type | Source basis | Provenance note |
|---|---:|---|---|---|---|
| COR-001 | 1 | Who is Centenary Bank? | Bank overview | R-01 | Imported from the working CSV; verify against the official website before external use |
| COR-002 | 3 | Services and products | Product summary | R-01, R-02 | Imported from the working CSV; public product information |
| COR-003 | 5 | Head office location | Contact/location | R-01 | Imported from the working CSV; public contact information |
| COR-004 | 6 | Support numbers | Support contact | R-01 | Imported from the working CSV; public support contact |
| COR-005 | 8 | Minimum account balance | Account rule | R-01, R-05 | Imported from the working CSV; verify fees/limits against approved sources |
| COR-006 | 10 | CenteSacco benefits | Product features | R-02 | Imported from the working CSV; product feature reference |
| COR-007 | 13 | CenteSacco opening requirements | Account opening requirements | R-03 | Imported from the working CSV; account-opening procedure source |
| COR-008 | 14 | CenteSacco interest calculation | Fees and rates | R-02, R-05 | Imported from the working CSV; pricing/charge style content |
| COR-009 | 15 | CenteSacco withdrawal charges | Charges and fees | R-05 | Imported from the working CSV; published charges topic |
| COR-010 | 19 | CenteSacco maintenance fees | Fees and charges | R-05 | Imported from the working CSV; published charges topic |
| COR-011 | 20 | CenteSacco statements | Service policy | R-02 | Imported from the working CSV; product-service policy |
| COR-012 | 32 | Standing order and direct debit charges | Fees and charges | R-05 | Imported from the working CSV; published charges topic |
| COR-013 | 41 | CenteSacco current account requirements | Account opening requirements | R-03 | Imported from the working CSV; account-opening procedure source |
| COR-014 | 48 | CenteDiaspora account features | Product features | R-01, R-02 | Imported from the working CSV; public product information |
| COR-015 | 49 | CenteDiaspora opening requirements | Account opening requirements | R-03 | Imported from the working CSV; account-opening procedure source |
| COR-016 | 58 | Inactive/dormant activation | Account servicing | R-01, R-02 | Imported from the working CSV; account servicing topic |
| COR-017 | 63 | Mobile balance enquiry | Digital banking support | R-02 | Imported from the working CSV; digital channel procedure |
| COR-018 | 66 | Monthly deductions | Charges explanation | R-05 | Imported from the working CSV; published charges topic |
| COR-019 | 67 | Statement charges | Charges explanation | R-05 | Imported from the working CSV; published charges topic |
| COR-020 | 69 | Savings account opening requirements | Account opening requirements | R-03 | Imported from the working CSV; account-opening procedure source |
| COR-021 | 70 | Visa card requirements | Card application | R-01, R-05 | Imported from the working CSV; fee and product reference |
| COR-022 | 71 | Visa card replacement | Card replacement support | R-01, R-05 | Imported from the working CSV; support and fee reference |
| COR-023 | 72 | Over-the-counter withdrawal charges | Charges explanation | R-05 | Imported from the working CSV; published charges topic |
| COR-024 | 73 | Internet banking services | Digital channel capabilities | R-01, R-02 | Imported from the working CSV; public digital service information |

## Provenance notes

- The CSV is a working corpus seed, not a standalone authority. Its rows should be traced back to the approved public and governance sources listed above.
- G-01 and G-02 define what may be used, what must be escalated, and which kinds of questions should never be answered from the corpus alone.
- R-04 through R-07 are governance anchors, not product facts. They belong in the Week 3 evidence set because they constrain how the corpus is used.
- If the team expands the corpus later, keep the same record ID style and add a new source basis entry for every new row.
How to Use Your Existing CSV Data

If you already have CSV data, you do not need to collect dozens of separate files. You can handle this in one of two ways:

Option A: Treat 10–50 Rows as Your Corpus (Easiest)

Select 10 to 50 representative rows from your CSV file to serve as your controlled evaluation dataset.

Treat each row (or a generated text string combining that row's fields) as a document record in your pipeline.
## Report-ready summary

Week 3 uses a controlled corpus of 24 equivalent records selected from a 98-row CSV seed and grounded in approved public and governance sources. Each record has a stable ID, a source basis, and provenance notes so the retrieval set can be audited and reproduced.