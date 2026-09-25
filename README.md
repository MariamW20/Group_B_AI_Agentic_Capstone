# Group_B_AI_Agentic_Capstone
Capstone project repository for BSE4104 AI Agentic Systems, featuring an autonomous, goal-driven agent architecture with tool execution and memory capabilities.

## Week 3 RAG evaluation

The [15-case evaluation report](docs/evaluation/Week-3-15-Case-RAG-Evaluation.md) covers five answerable, five partially answerable and five deliberately unanswerable questions against the registered 24-record corpus. It includes actual retrieval results, expected responses, failure analysis and reproduction steps. See the report for the separate model-generation completion status.

Fixed cases: `tests/rag_cases.json`. Raw evidence: `evidence/traces/rag-evaluation.json`.

## Week 4 tool QA

- [Tool failure and authorization test evidence](docs/evaluation/Week-4-Tool-QA.md)
- [Updated Week 4 architecture](docs/architecture/updated-agent-architecture.md)
- [Architecture image (PNG)](docs/architecture/agentarchitecture-week4-final.png)
- [Week 4 progress report](docs/weekly-reports/Week4_Progress_Report_Final.docx)
- Run QA: `python3 -m unittest discover -s tests/week4 -v`
