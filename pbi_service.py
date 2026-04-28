"""
pbi_service.py — Integração com o Power BI Service via API REST

Requer um App Registration no Azure AD com as permissões:
  - Dataset.Read.All
  - Report.Read.All
  - Workspace.Read.All

Fluxo de autenticação: OAuth2 Client Credentials (App-only)
Documentação: https://learn.microsoft.com/en-us/power-bi/developer/embedded/embed-service-principal
"""

import os
import requests
import pandas as pd
from typing import Optional


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

AUTHORITY_URL = "https://login.microsoftonline.com/{tenant_id}"
SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]
PBI_BASE = "https://api.powerbi.com/v1.0/myorg"


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def get_access_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """
    Obtém token de acesso via Client Credentials (Service Principal).

    Parâmetros
    ----------
    tenant_id    : ID do tenant Azure AD
    client_id    : App ID (Application ID) do registro no Azure
    client_secret: Secret Value criado no Azure AD

    Retorna
    -------
    str  — Bearer token de acesso
    """
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://analysis.windows.net/powerbi/api/.default",
    }
    response = requests.post(url, data=data, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Workspaces (Groups)
# ---------------------------------------------------------------------------

def list_workspaces(token: str) -> list[dict]:
    """
    Lista todos os workspaces acessíveis pelo Service Principal.

    Retorna lista de dicts: [{id, name, type, isReadOnly}]
    """
    url = f"{PBI_BASE}/groups"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json().get("value", [])


# ---------------------------------------------------------------------------
# Datasets (Modelos)
# ---------------------------------------------------------------------------

def list_datasets(token: str, workspace_id: Optional[str] = None) -> list[dict]:
    """
    Lista datasets de um workspace ou do workspace pessoal.
    """
    if workspace_id:
        url = f"{PBI_BASE}/groups/{workspace_id}/datasets"
    else:
        url = f"{PBI_BASE}/datasets"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json().get("value", [])


def get_dataset_tables(token: str, dataset_id: str, workspace_id: Optional[str] = None) -> list[dict]:
    """
    Retorna as tabelas de um dataset.
    Nota: requer que o dataset esteja publicado e acessível.
    """
    if workspace_id:
        url = f"{PBI_BASE}/groups/{workspace_id}/datasets/{dataset_id}/tables"
    else:
        url = f"{PBI_BASE}/datasets/{dataset_id}/tables"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json().get("value", [])


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def list_reports(token: str, workspace_id: Optional[str] = None) -> list[dict]:
    """Lista relatórios de um workspace."""
    if workspace_id:
        url = f"{PBI_BASE}/groups/{workspace_id}/reports"
    else:
        url = f"{PBI_BASE}/reports"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json().get("value", [])


# ---------------------------------------------------------------------------
# Extração via XMLA / Dataset REST API (metadados ricos)
# ---------------------------------------------------------------------------

def _execute_dax(token: str, workspace_id: str, dataset_id: str, dax_query: str) -> list[dict]:
    """
    Executa uma query DAX via Power BI REST API (executeQueries).
    Requer Premium, Premium Per User ou Fabric capacity.
    """
    url = f"{PBI_BASE}/groups/{workspace_id}/datasets/{dataset_id}/executeQueries"
    body = {
        "queries": [{"query": dax_query}],
        "serializerSettings": {"includeNulls": True},
    }
    resp = requests.post(url, headers=_headers(token), json=body, timeout=60)
    resp.raise_for_status()
    results = resp.json()
    rows = results.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])
    return rows


def extract_from_service(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    workspace_id: str,
    dataset_id: str,
    report_name: str = "PBI Report",
) -> dict:
    """
    Extrai metadados de um dataset do Power BI Service.

    Utiliza as APIs REST do Power BI para obter:
    - Tabelas e colunas (via $metadata do dataset)
    - Medidas (via DMV queries se disponível, ou parseando metadados)
    - Relacionamentos (quando acessível)

    Retorna o mesmo formato de dict que extractor.extract_from_file().
    """
    token = get_access_token(tenant_id, client_id, client_secret)

    # --- Tabelas ---
    tables_raw_api = get_dataset_tables(token, dataset_id, workspace_id)

    tables_list = []
    measures_list = []
    columns_list = []

    for tbl in tables_raw_api:
        tbl_name = tbl.get("name", "")
        tables_list.append({"NomeTabela": tbl_name, "FonteDados": ""})

        # Colunas da tabela
        for col in tbl.get("columns", []):
            columns_list.append({
                "NomeTabela": tbl_name,
                "NomeColuna": col.get("name", ""),
                "TipoDadoColuna": col.get("dataType", ""),
                "TipoColuna": col.get("columnType", "data"),
                "ExpressaoColuna": col.get("expression", "N/A") or "N/A",
            })

        # Medidas da tabela
        for m in tbl.get("measures", []):
            expr = m.get("expression", "")
            measures_list.append({
                "NomeMedida": m.get("name", ""),
                "ExpressaoMedida": expr,
                "NomeTabela": tbl_name,
            })

    # --- Relacionamentos (via DMV — requer capacidade adequada) ---
    df_relationships = None
    try:
        rows = _execute_dax(
            token, workspace_id, dataset_id,
            "SELECT * FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS"
        )
        if rows:
            df_relationships = pd.DataFrame([
                {
                    "FromTable": r.get("FromTableName", ""),
                    "FromColumn": r.get("FromColumnName", ""),
                    "ToTable": r.get("ToTableName", ""),
                    "ToColumn": r.get("ToColumnName", ""),
                }
                for r in rows
            ])
    except Exception:
        # DMV não disponível neste workspace/capacidade
        pass

    tables_df = pd.DataFrame(tables_list)
    measures_df = pd.DataFrame(measures_list) if measures_list else pd.DataFrame(
        columns=["NomeMedida", "ExpressaoMedida", "NomeTabela"]
    )
    columns_df = pd.DataFrame(columns_list) if columns_list else pd.DataFrame(
        columns=["NomeTabela", "NomeColuna", "TipoDadoColuna", "TipoColuna", "ExpressaoColuna"]
    )

    from extractor import _build_combined_df
    df_combined = _build_combined_df(tables_df, measures_df, columns_df, report_name)

    return {
        "report_name": report_name,
        "df": df_combined,
        "df_relationships": df_relationships,
        "tables_df": tables_df,
        "measures_df": measures_df,
        "columns_df": columns_df,
        "model_raw": {},
        "source": "service",
    }


# ---------------------------------------------------------------------------
# Helpers para a UI
# ---------------------------------------------------------------------------

def validate_credentials(tenant_id: str, client_id: str, client_secret: str) -> tuple[bool, str]:
    """
    Valida as credenciais do Azure AD.
    Retorna (True, token) em caso de sucesso ou (False, mensagem_de_erro).
    """
    try:
        token = get_access_token(tenant_id, client_id, client_secret)
        return True, token
    except requests.HTTPError as e:
        return False, f"Erro de autenticação HTTP: {e.response.status_code} — {e.response.text}"
    except Exception as e:
        return False, f"Erro de autenticação: {str(e)}"
