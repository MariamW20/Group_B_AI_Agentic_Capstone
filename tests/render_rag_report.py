"""Render the saved evaluation evidence without inventing model responses."""
import json
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def main():
    report = json.loads((ROOT / 'evidence/traces/rag-evaluation.json').read_text(encoding='utf-8'))
    results = report['results']
    lines = ['# Week 3: 15-case RAG evaluation results', '',
        'Project: Centenary Bank Customer Support AI', '',
        f"Run time (UTC): {report['generated_at_utc']}  ",
        f"Evaluated team baseline: `{report['base_commit']}`", '',
        '## Scope and method', '',
        'Fifteen fixed questions: five answerable, five partially answerable, and five deliberately unanswerable. '
        'Answerability is relative to the frozen 24-record corpus in the team source register, not the whole internet or all 98 seed FAQs. '
        'The evaluator adapts each registered CSV row into a Document, then calls the existing chunk_documents, build_index, retrieve, build_context and build_llm_messages functions unchanged. '
        'No expected answers or category labels are supplied to the retriever or model.', '',
        f"Configuration: {report['corpus_records']} records, {report['chunks']} chunks; paragraph chunking (200 words, 30-word overlap); TF-IDF unigrams/bigrams with English stop words; cosine similarity; top-k = 4; minimum score = 0.05. Python {report['python']}; scikit-learn {report['sklearn']}.", '',
        'This is an academic evaluation of the supplied corpus, not verification of current banking policy. The source register itself marks provenance checks as pending before external use.', '',
        '## Scoring', '',
        '- Answerable/partial retrieval PASS: the designated supporting record appears in the top four results. Partial cases must still decline the missing component in a generated answer.',
        '- Unanswerable retrieval PASS: no chunk exceeds the threshold. A FAIL here means the threshold did not screen out an unsupported question; it does not prove the model hallucinated.',
        '- Answer PASS requires factual correctness against the supplied evidence, citations supporting each factual claim, explicit acknowledgement of unavailable information, and no invented facts/actions. A wrong answer, fabricated citation, unsupported completion or unsafe action claim fails. Unexecuted generation is BLOCKED, never PASS.', '',
        '## Results summary', '',
        '| Category | Cases | Retrieval PASS | Retrieval FAIL |',
        '|---|---:|---:|---:|']
    for category in ['answerable', 'partially_answerable', 'unanswerable']:
        group = [r for r in results if r['category'] == category]
        passed = sum(r['retrieval_result'] == 'PASS' for r in group)
        lines.append(f'| {category} | {len(group)} | {passed} | {len(group)-passed} |')
    successful = sum(r['generation_status'] == 'OK' for r in results)
    lines += ['', f'Expected-source hit rate for answerable/partial cases: **{sum(r["retrieval_result"] == "PASS" for r in results if r["expected_sources"])}/10**. '
        f'Empty-retrieval rate for deliberately unanswerable cases: **{sum(not r["sources"] for r in results if not r["expected_sources"])}/5**.', '',
        f'Actual model answers recorded: **{successful}/15**. Answer quality verdicts: '
        + ', '.join(f'{k}: {v}' for k,v in Counter(r['answer_verdict'] for r in results).items()) + '.', '']
    if successful < 15:
        lines += ['**Limitation:** Model-answer evaluation is incomplete. External Gemini execution was blocked pending explicit approval to transmit corpus excerpts and test prompts. '
            'The table contains executed retrieval results, not fabricated end-to-end passes. No model refusal, citation accuracy or hallucination rate can be inferred from retrieval alone.', '']
    lines += ['## 15-case results table', '', '| ID | Type | Test question | Expected source | Retrieved records (rank order) | Retrieval | Generation | Answer verdict |', '|---|---|---|---|---|---|---|---|']
    for r in results:
        sources = ', '.join(f"{s['doc_id']} ({s['score']:.4f})" for s in r['sources']) or 'None'
        lines.append(f"| {r['id']} | {r['category']} | {r['question']} | {', '.join(r['expected_sources']) or 'None'} | {sources} | {r['retrieval_result']} | {r['generation_status']} | {r['answer_verdict']} |")
    lines += ['', '## Per-case expected and observed behaviour', '']
    for r in results:
        lines += [f"### {r['id']}: {r['question']}", '', f"**Expected:** {r['expected_answer']}", '']
        if r['missing_information']:
            lines += [f"**Unavailable information:** {r['missing_information']}.", '']
        if r['sources']:
            top = r['sources'][0]
            lines += [f"**Actual top retrieval:** {top['doc_id']} / {top['chunk_id']}, score {top['score']:.4f}.", '', '> ' + top['text'].replace('\n', '\n> '), '']
        else:
            lines += ['**Actual retrieval:** No sources above the threshold; the constructed prompt explicitly instructs the model to acknowledge missing information.', '']
        lines += ['**Actual model answer:** ' + (r['actual_answer'] or 'Not obtained; generation blocked pending approval.'), '']
        if r.get('review_notes'):
            lines += ['**Review:** ' + r['review_notes'], '']
    lines += ['## Failure analysis and next steps', '',
        '1. RAG-11 retrieves a generic minimum-balance record for a personal live-balance request. Lexical similarity does not establish that the requested fact exists. Keep account-data limitations explicit and test the generated refusal.',
        '2. RAG-12 retrieves general bank/product records for a live FX rate. Add freshness checks and explicit handling of unavailable live data; do not present historical corpus content as a current quote.',
        '3. RAG-13 and RAG-15 retrieve banking text despite unavailable loan status or a fabricated-policy request. Preserve grounding instructions and verify refusal under related but insufficient context.',
        '4. RAG-02 ranks current-account requirements above the designated savings-account record; RAG-07 also ranks another product first. Top-four retrieval succeeds, but product confusion remains a generation risk. Preserve product metadata and consider reranking.',
        '5. Raising the similarity threshold alone is not an adequate fix: unsupported RAG-15 has a higher top score than supported RAG-06. Evaluate answerability and product relevance as well as similarity.',
        '6. Complete the model run and review all 15 answers for correctness, grounded citations and appropriate abstention. Re-run this same fixed set after teammates finish integration, and add a separate held-out set before tuning thresholds.', '',
        '## Reproduction and evidence', '',
        'From the repository root:', '', '```powershell', 'python -m pip install --target .eval-deps -r tests/rag-requirements.txt', 'python tests/run_rag_evaluation.py', '# Optional external API stage; uses the existing demo .env without logging its key:', 'node evidence/demo/centenary-helpdesk/evaluate-rag.mjs', 'python tests/render_rag_report.py', '```', '',
        'The Python retrieval runner needs no API key or external service. The optional Gemini stage uses the same configured model as the existing demo and sends the exact saved grounded messages. It is an evaluation adapter, not a change to the production chat endpoint. Re-running retrieval resets generation fields; preserve an existing trace before rerunning if needed.', '',
        '- [Fixed cases and reference expectations](../../tests/rag_cases.json)',
        '- [Raw results, exact contexts, prompts, scores and SHA-256 input fingerprints](../../evidence/traces/rag-evaluation.json)',
        '- [Controlled source register](../requirements/Week-3-Corpus-Source-Register.md)',
        '- [Evaluation runner](../../tests/run_rag_evaluation.py)', '',
        'ClickUp traceability: existing team commits include a task ID. Attach this deliverable commit to the correct evaluation task; do not reuse a teammate\'s ingestion or corpus task ID. The evaluation task ID was not supplied at report creation.', '']
    (ROOT / 'docs/evaluation/Week-3-15-Case-RAG-Evaluation.md').write_text('\n'.join(lines), encoding='utf-8')

if __name__ == '__main__':
    main()
