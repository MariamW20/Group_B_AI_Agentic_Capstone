import argparse, csv, hashlib, json, platform, re, subprocess, sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.eval-deps'))
sys.path.insert(0, str(ROOT / 'evidence/demo/centenary-RAG'))
import sklearn
from ingest import Document
from chunk import chunk_documents
from index_store import build_index
from retrieve import retrieve
from context_builder import build_context, build_llm_messages

def main():
    parser = argparse.ArgumentParser(description="Evaluate the registered corpus with the team's unchanged RAG modules")
    parser.add_argument('--output', default='evidence/traces/rag-evaluation.json')
    args = parser.parse_args()
    register = ROOT / 'docs/requirements/Week-3-Corpus-Source-Register.md'
    selected = re.findall(r'^\| (COR-\d+) \| (\d+) \|', register.read_text(encoding='utf-8'), re.M)
    with (ROOT / 'centenary_bank_faqs.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = {r['id']: r for r in csv.DictReader(f)}
    docs = [Document(doc_id, rows[row]['question'],
            f"Question: {rows[row]['question']}\nAnswer: {rows[row]['answer']}",
            {'csv_id': int(row), 'register': str(register.relative_to(ROOT))}) for doc_id, row in selected]
    assert len(docs) == 24 and len({d.doc_id for d in docs}) == 24
    chunks = chunk_documents(docs)
    index = build_index(chunks)
    cases = json.loads((ROOT / 'tests/rag_cases.json').read_text(encoding='utf-8-sig'))
    assert Counter(c['category'] for c in cases) == dict(answerable=5, partially_answerable=5, unanswerable=5)
    assert len({c['id'] for c in cases}) == 15
    results = []
    for case in cases:
        hits = retrieve(index, case['question'], k=4, min_score=0.05)
        context = build_context(hits)
        found = {h.chunk.doc_id for h in hits}
        expected = set(case['expected_sources'])
        assert expected <= {d.doc_id for d in docs}
        # Empty retrieval is a conservative proxy, NOT proof of safe model abstention.
        passed = expected <= found if expected else not hits
        results.append({**case, 'retrieval_result': 'PASS' if passed else 'FAIL',
            'sources': [asdict(s) for s in context.sources],
            'messages': build_llm_messages(case['question'], context),
            'generation_status': 'NOT_RUN', 'actual_answer': None, 'answer_verdict': 'NOT_EVALUATED'})
    files = ['centenary_bank_faqs.csv', str(register.relative_to(ROOT)), 'tests/rag_cases.json']
    files += [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'evidence/demo/centenary-RAG').glob('*.py'))]
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'python': platform.python_version(), 'sklearn': sklearn.__version__,
        'corpus_records': len(docs), 'chunks': len(chunks), 'k': 4, 'min_score': 0.05,
        'sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}, 'results': results}
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for r in results:
        print(r['id'], r['category'], r['retrieval_result'], [(s['doc_id'], s['score']) for s in r['sources']])

if __name__ == '__main__':
    main()
