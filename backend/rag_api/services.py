from pathlib import Path
BASE = Path(__file__).resolve().parents[2] / "rag_data"
def retrieve(query, top_k=4):
    terms = set(query.lower().split())
    out = []
    for path in BASE.glob("*.txt"):
        text = path.read_text(encoding="utf-8")
        score = sum(term in text.lower() for term in terms)
        out.append({"source":path.name,"score":score,"text":text})
    return sorted(out,key=lambda x:x["score"],reverse=True)[:top_k]
