"""
main.py — FastAPI backend para o PBI DocGen

Endpoints:
  POST /api/upload          → upload de arquivo .pbix/.pbit/.zip
  POST /api/connect-service → autenticar no Power BI Service
  GET  /api/workspaces      → listar workspaces
  GET  /api/datasets        → listar datasets de um workspace
  GET  /api/reports         → listar reports de um workspace
  POST /api/generate        → gerar documentação (SSE streaming)
  POST /api/chat            → chat sobre o relatório
  GET  /api/download/word   → download Word
  GET  /api/download/excel  → download Excel
  GET  /api/models          → modelos LLM disponíveis
  GET  /api/metadata        → metadados extraídos do arquivo atual
"""

import asyncio
import io
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

load_dotenv()

# Importações internas
from documenta import chat_sobre_relatorio, gerar_documentacao, generate_docx, generate_excel
from extractor import extract_from_file
from llm_client import get_available_models, get_default_model
from pbi_service import (
    extract_from_service,
    list_datasets,
    list_reports,
    list_workspaces,
    validate_credentials,
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="PBI DocGen", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Estado em memória (por sessão via session_id)
# ---------------------------------------------------------------------------
# Em produção, usar Redis ou banco de dados.

_sessions: dict[str, dict] = {}


def _get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {}
    return _sessions[session_id]


# ---------------------------------------------------------------------------
# Models Pydantic
# ---------------------------------------------------------------------------

class ServiceConnectRequest(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str
    session_id: str


class ServiceExtractRequest(BaseModel):
    session_id: str
    workspace_id: str
    dataset_id: str
    report_name: Optional[str] = "PBI Report"


class GenerateRequest(BaseModel):
    session_id: str
    modelo: str
    language: str = "Português"


class ChatRequest(BaseModel):
    session_id: str
    pergunta: str
    modelo: str
    language: str = "Português"


class DownloadRequest(BaseModel):
    session_id: str
    modelo: str
    language: str = "Português"


# ---------------------------------------------------------------------------
# Endpoints de arquivo local
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(...),
):
    """Recebe um arquivo .pbix / .pbit / .zip e extrai os metadados."""
    allowed = {".pbix", ".pbit", ".zip"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: '{ext}'. Use .pbix, .pbit ou .zip."
        )

    content = await file.read()
    try:
        data = extract_from_file(io.BytesIO(content), file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Erro ao processar arquivo: {str(e)}")

    session = _get_session(session_id)
    session["data"] = data
    session["source"] = "file"
    session["filename"] = file.filename
    session["doc_resultado"] = None
    session["token"] = None

    return _metadata_response(data)


# ---------------------------------------------------------------------------
# Endpoints Power BI Service
# ---------------------------------------------------------------------------

@app.post("/api/connect-service")
async def connect_service(req: ServiceConnectRequest):
    """Valida as credenciais do Azure AD e retorna a lista de workspaces."""
    ok, result = validate_credentials(req.tenant_id, req.client_id, req.client_secret)
    if not ok:
        raise HTTPException(status_code=401, detail=result)

    token = result
    session = _get_session(req.session_id)
    session["token"] = token
    session["tenant_id"] = req.tenant_id
    session["client_id"] = req.client_id
    session["client_secret"] = req.client_secret

    try:
        workspaces = list_workspaces(token)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao listar workspaces: {e}")

    return {"workspaces": workspaces}


@app.get("/api/workspaces/{session_id}/datasets")
async def get_datasets(session_id: str, workspace_id: str):
    """Lista datasets de um workspace."""
    session = _get_session(session_id)
    token = session.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Sessão não autenticada.")
    try:
        datasets = list_datasets(token, workspace_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"datasets": datasets}


@app.get("/api/workspaces/{session_id}/reports")
async def get_reports(session_id: str, workspace_id: str):
    """Lista reports de um workspace."""
    session = _get_session(session_id)
    token = session.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Sessão não autenticada.")
    try:
        reports = list_reports(token, workspace_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"reports": reports}


@app.post("/api/extract-service")
async def extract_service(req: ServiceExtractRequest):
    """Extrai metadados de um dataset do Power BI Service."""
    session = _get_session(req.session_id)
    tenant_id = session.get("tenant_id", "")
    client_id = session.get("client_id", "")
    client_secret = session.get("client_secret", "")

    if not all([tenant_id, client_id, client_secret]):
        raise HTTPException(status_code=401, detail="Credenciais não encontradas na sessão.")

    try:
        data = extract_from_service(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            workspace_id=req.workspace_id,
            dataset_id=req.dataset_id,
            report_name=req.report_name or "PBI Report",
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Erro ao extrair do serviço: {str(e)}")

    session["data"] = data
    session["source"] = "service"
    session["doc_resultado"] = None

    return _metadata_response(data)


# ---------------------------------------------------------------------------
# Metadata helper
# ---------------------------------------------------------------------------

def _metadata_response(data: dict) -> dict:
    """Serializa os metadados extraídos para JSON."""
    tables_df = data["tables_df"]
    measures_df = data["measures_df"]
    columns_df = data["columns_df"]
    df_rels = data.get("df_relationships")

    def df_to_records(df):
        if df is None or df.empty:
            return []
        return df.fillna("").astype(str).to_dict(orient="records")

    return {
        "report_name": data["report_name"],
        "tables": df_to_records(tables_df),
        "measures": df_to_records(measures_df),
        "columns": df_to_records(columns_df),
        "relationships": df_to_records(df_rels),
        "stats": {
            "n_tables": len(tables_df) if not tables_df.empty else 0,
            "n_measures": len(measures_df) if not measures_df.empty else 0,
            "n_columns": len(columns_df) if not columns_df.empty else 0,
            "n_relationships": len(df_rels) if df_rels is not None and not df_rels.empty else 0,
        },
    }


@app.get("/api/metadata/{session_id}")
async def get_metadata(session_id: str):
    """Retorna os metadados extraídos da sessão atual."""
    session = _get_session(session_id)
    data = session.get("data")
    if not data:
        raise HTTPException(status_code=404, detail="Nenhum arquivo carregado nesta sessão.")
    return _metadata_response(data)


# ---------------------------------------------------------------------------
# Geração de documentação via SSE (Server-Sent Events)
# ---------------------------------------------------------------------------

@app.get("/api/generate")
async def generate_docs_sse(session_id: str, modelo: str, language: str = "Português"):
    """
    Gera a documentação via SSE — o cliente recebe atualizações em tempo real.

    Eventos emitidos:
      - progress: {"step": N, "total": M, "message": "..."}
      - done:     {"doc_resultado": {...}}
      - error:    {"detail": "..."}
    """
    session = _get_session(session_id)
    data = session.get("data")
    if not data:
        raise HTTPException(status_code=404, detail="Nenhum arquivo carregado.")

    progress_queue: asyncio.Queue = asyncio.Queue()

    def progress_callback(step: int, total: int, msg: str):
        # asyncio.Queue não é thread-safe. Usamos call_soon_threadsafe para enviar do worker thread para o loop principal.
        loop.call_soon_threadsafe(progress_queue.put_nowait, {"step": step, "total": total, "message": msg})

    loop = asyncio.get_event_loop()

    async def run_generation():
        """Executa a geração em thread separada para não bloquear o event loop."""
        try:
            doc_resultado = await loop.run_in_executor(
                None,
                lambda: gerar_documentacao(data, modelo, language, progress_callback),
            )
            session["doc_resultado"] = doc_resultado
            session["modelo"] = modelo
            session["language"] = language
            await progress_queue.put({"done": True, "doc_resultado": doc_resultado})
        except Exception as e:
            import traceback
            traceback.print_exc()
            await progress_queue.put({"error_msg": str(e)})

    asyncio.ensure_future(run_generation())

    async def event_generator():
        # Envia um evento inicial imediato para o Railway saber que a conexão está ativa
        yield {"event": "progress", "data": json.dumps({"step": 0, "total": 100, "message": "Iniciando orquestração IA..."})}
        
        last_pct = 0
        while True:
            try:
                # Espera por um evento da thread de processamento por no máximo 15 segundos
                event = await asyncio.wait_for(progress_queue.get(), timeout=15.0)
                
                if "error_msg" in event:
                    yield {"event": "gen_error", "data": json.dumps({"detail": event["error_msg"]})}
                    break
                if event.get("done"):
                    yield {"event": "done", "data": json.dumps({"doc_resultado": event["doc_resultado"]})}
                    break
                
                step = event.get('step', 0)
                total = event.get('total', 100)
                last_pct = round((step / total) * 100) if total else last_pct
                yield {"event": "progress", "data": json.dumps(event)}
                
            except asyncio.TimeoutError:
                # Heartbeat manual para manter o Proxy do Railway vivo
                yield {"event": "progress", "data": json.dumps({"step": last_pct, "total": 100, "message": "IA ainda processando..."})}

    return EventSourceResponse(event_generator(), ping=20)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Chat interativo sobre o relatório."""
    session = _get_session(req.session_id)
    data = session.get("data")
    doc_resultado = session.get("doc_resultado")

    if not data:
        raise HTTPException(status_code=404, detail="Nenhum relatório carregado.")
    if not doc_resultado:
        raise HTTPException(status_code=400, detail="Gere a documentação antes de usar o chat.")

    try:
        resposta = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: chat_sobre_relatorio(
                req.pergunta, data, doc_resultado, req.modelo, req.language
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"resposta": resposta}


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

@app.get("/api/download/word")
async def download_word(session_id: str):
    """Gera e retorna o arquivo Word."""
    session = _get_session(session_id)
    data = session.get("data")
    doc_resultado = session.get("doc_resultado")
    modelo = session.get("modelo", "LLM")
    language = session.get("language", "Português")

    if not data or not doc_resultado:
        raise HTTPException(status_code=400, detail="Documentação ainda não gerada.")

    buf = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: generate_docx(doc_resultado, data, modelo, language),
    )
    filename = f"doc_{data['report_name']}.docx".replace(" ", "_")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/download/excel")
async def download_excel(session_id: str):
    """Gera e retorna o arquivo Excel."""
    session = _get_session(session_id)
    data = session.get("data")
    doc_resultado = session.get("doc_resultado")

    if not data or not doc_resultado:
        raise HTTPException(status_code=400, detail="Documentação ainda não gerada.")

    buf = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: generate_excel(doc_resultado, data),
    )
    filename = f"doc_{data['report_name']}.xlsx".replace(" ", "_")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@app.get("/api/models")
async def get_models():
    """Lista modelos disponíveis e o modelo padrão."""
    return {
        "models": get_available_models(),
        "default": get_default_model(),
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Static files — deve ser o último (catch-all)
# ---------------------------------------------------------------------------

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    # Desativado reload para estabilidade em tarefas longas
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
