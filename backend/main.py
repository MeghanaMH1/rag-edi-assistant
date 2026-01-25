from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .csv_utils import parse_csv
from .embeddings import generate_embeddings
from .rag_service import answer_question
from .ai_explainer import explain_facts  # 🔑 keep AI warm-up

app = FastAPI(title="RAG-Based EDI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
edi_rows = []
edi_row_embeddings = None   # 🔑 IMPORTANT: start as None


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def root():
    return {"message": "RAG EDI Assistant backend running"}


@app.post("/upload-csv")
def upload_csv(file: UploadFile = File(...)):
    global edi_rows, edi_row_embeddings

    edi_rows = parse_csv(file)

    # 🔑 defer embeddings (major speed win)
    edi_row_embeddings = None

    # 🔥 AI warm-up (kept, safe)
    try:
        explain_facts("warmup")
    except Exception:
        pass

    return {
        "message": "CSV uploaded and indexed successfully",
        "rows_loaded": len(edi_rows),
    }


@app.post("/ask")
def ask(req: QuestionRequest):
    global edi_row_embeddings

    if not edi_rows:
        return {"answer": "No CSV uploaded yet"}

    # 🔥 lazy embeddings (generated once, only if needed)
    if edi_row_embeddings is None:
        row_texts = [str(row) for row in edi_rows]
        edi_row_embeddings = generate_embeddings(row_texts)

    answer = answer_question(
        question=req.question,
        rows=edi_rows,
        row_embeddings=edi_row_embeddings,
    )

    return {"answer": answer}
