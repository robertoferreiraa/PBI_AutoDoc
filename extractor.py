"""
extractor.py — Extração de metadados de arquivos Power BI (.pbix / .pbit / .zip)

O arquivo .pbix é internamente um ZIP que contém:
- DataModelSchema  → metadados do modelo (tabelas, medidas, colunas, relacionamentos)
- DataModel        → (versões mais antigas) modelo binário
- Report/Layout    → layout visual (não utilizado aqui)

Para modelos mais novos, o conteúdo está em formato JSON compactado dentro de
'DataModelSchema', ou como arquivo separado 'Model.bim' (formato TMSL).
"""

import zipfile
import json
import io
import pandas as pd
import re


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def _try_decode(data: bytes) -> str:
    """Tenta decodificar bytes com diferentes encodings, muito comum o uso de utf-16-le no PBI."""
    for enc in ("utf-16-le", "utf-16", "utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    # Fallback brutal se tiver prefixo binário sujo
    return data.decode("utf-16-le", errors="ignore")


def _list_zip_files(zf: zipfile.ZipFile) -> list[str]:
    return [zi.filename for zi in zf.infolist()]


def _read_zip_entry(zf: zipfile.ZipFile, name: str) -> bytes:
    with zf.open(name) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Leitura do modelo
# ---------------------------------------------------------------------------

def _find_model_entry(names: list[str]) -> str | None:
    """Retorna o nome da entrada ZIP que contém o modelo TMSL/JSON."""
    priority = [
        "DataModelSchema",
        "DataModel",
        "Model.bim",
        "model.bim",
    ]
    for candidate in priority:
        if candidate in names:
            return candidate
    # Fallback: qualquer arquivo .bim
    for n in names:
        if n.lower().endswith(".bim"):
            return n
    return None


def _parse_model_json(raw: str) -> dict:
    """
    Extrai o JSON do modelo a partir do conteúdo bruto do DataModelSchema.
    Tenta JSON direto; se falhar, tenta encontrar o bloco JSON dentro do texto.
    """
    # Remove BOM se presente
    raw = raw.lstrip("\ufeff").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Às vezes há prefixo binário e sufixo binário; tenta encontrar o primeiro '{' e o último '}'
        idx_start = raw.find("{")
        idx_end = raw.rfind("}")
        if idx_start != -1 and idx_end != -1 and idx_end > idx_start:
            try:
                return json.loads(raw[idx_start:idx_end+1])
            except json.JSONDecodeError:
                pass
    raise ValueError("Não foi possível fazer o parse do modelo JSON do arquivo Power BI.")


# ---------------------------------------------------------------------------
# Extração de metadados
# ---------------------------------------------------------------------------

def _extract_tables_and_measures(model: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Retorna:
      - tables: [{nome, fonte_dados}]
      - measures: [{tabela, nome, expressao}]
      - columns: [{tabela, nome, tipo_dado, tipo_coluna, expressao}]
    """
    tables_raw = []
    measures_raw = []
    columns_raw = []

    # Suporte a schemas com "model" aninhado (formato TMSL completo)
    model_node = model.get("model", model)

    for tbl in model_node.get("tables", []):
        tbl_name = tbl.get("name", "")

        # Fonte de dados via partitions → source → expression (M Query)
        fonte = ""
        for partition in tbl.get("partitions", []):
            src = partition.get("source", {})
            expr = src.get("expression", "")
            if isinstance(expr, list):
                expr = "\n".join(expr)
            if expr:
                fonte = expr
                break

        tables_raw.append({"NomeTabela": tbl_name, "FonteDados": fonte})

        # Medidas
        for measure in tbl.get("measures", []):
            expr = measure.get("expression", "")
            if isinstance(expr, list):
                expr = "\n".join(expr)
            measures_raw.append({
                "NomeMedida": measure.get("name", ""),
                "ExpressaoMedida": expr,
                "NomeTabela": tbl_name,
            })

        # Colunas
        for col in tbl.get("columns", []):
            expr_col = col.get("expression", "")
            if isinstance(expr_col, list):
                expr_col = "\n".join(expr_col)

            tipo_coluna = col.get("type", "data")  # "calculated" | "data" | "calculatedTableColumn"
            tipo_dado = col.get("dataType", "")

            columns_raw.append({
                "NomeTabela": tbl_name,
                "NomeColuna": col.get("name", ""),
                "TipoDadoColuna": tipo_dado,
                "TipoColuna": tipo_coluna,
                "ExpressaoColuna": expr_col or "N/A",
            })

    return tables_raw, measures_raw, columns_raw


def _extract_relationships(model: dict) -> list[dict]:
    """Extrai relacionamentos do modelo."""
    rels = []
    model_node = model.get("model", model)
    for rel in model_node.get("relationships", []):
        rels.append({
            "FromTable": rel.get("fromTable", ""),
            "FromColumn": rel.get("fromColumn", ""),
            "ToTable": rel.get("toTable", ""),
            "ToColumn": rel.get("toColumn", ""),
            "CrossFilteringBehavior": rel.get("crossFilteringBehavior", "singleDirection"),
        })
    return rels


def _get_report_name(zf: zipfile.ZipFile, filename: str) -> str:
    """Tenta ler o nome do relatório a partir do arquivo de metadados."""
    names = _list_zip_files(zf)
    if "Metadata" in names:
        try:
            raw = _try_decode(_read_zip_entry(zf, "Metadata"))
            data = json.loads(raw)
            return data.get("name", filename)
        except Exception:
            pass
    return filename.replace(".pbix", "").replace(".pbit", "")


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def extract_from_file(file_obj, filename: str) -> dict:
    """
    Extrai metadados de um arquivo Power BI.

    Parâmetros
    ----------
    file_obj : file-like object (bytes ou BytesIO)
        Conteúdo do arquivo .pbix / .pbit / .zip
    filename : str
        Nome original do arquivo

    Retorna
    -------
    dict com:
        - report_name: str
        - df: pd.DataFrame  (tabelas, medidas, colunas)
        - df_relationships: pd.DataFrame
        - tables_df: pd.DataFrame
        - measures_df: pd.DataFrame
        - columns_df: pd.DataFrame
        - model_raw: dict  (JSON completo do modelo)
    """
    if not isinstance(file_obj, (io.BytesIO, io.BufferedReader)):
        file_obj = io.BytesIO(file_obj.read() if hasattr(file_obj, "read") else file_obj)

    with zipfile.ZipFile(file_obj, "r") as zf:
        names = _list_zip_files(zf)
        entry = _find_model_entry(names)
        if entry is None:
            raise ValueError(
                f"Não foi possível localizar o modelo de dados no arquivo '{filename}'. "
                f"Arquivos encontrados: {names}"
            )

        raw = _try_decode(_read_zip_entry(zf, entry))
        
        if "XPress9" in raw[:100] or raw.startswith("This backup was created"):
            raise ValueError(
                "Este arquivo .pbix utiliza um formato binário comprimido que não pode ser lido diretamente. "
                "Por favor, abra-o no Power BI Desktop e salve como 'Modelo de Relatório do Power BI (.pbit)', "
                "ou utilize a aba 'Power BI Service' para extrair os metadados diretamente da nuvem."
            )
            
        model = _parse_model_json(raw)
        report_name = _get_report_name(zf, filename)

    tables_raw, measures_raw, columns_raw = _extract_tables_and_measures(model)
    relationships_raw = _extract_relationships(model)

    tables_df = pd.DataFrame(tables_raw)
    measures_df = pd.DataFrame(measures_raw) if measures_raw else pd.DataFrame(
        columns=["NomeMedida", "ExpressaoMedida", "NomeTabela"]
    )
    columns_df = pd.DataFrame(columns_raw) if columns_raw else pd.DataFrame(
        columns=["NomeTabela", "NomeColuna", "TipoDadoColuna", "TipoColuna", "ExpressaoColuna"]
    )
    df_relationships = pd.DataFrame(relationships_raw) if relationships_raw else None

    # DataFrame unificado (compatível com o fluxo de documentação)
    df_combined = _build_combined_df(tables_df, measures_df, columns_df, report_name)

    return {
        "report_name": report_name,
        "df": df_combined,
        "df_relationships": df_relationships,
        "tables_df": tables_df,
        "measures_df": measures_df,
        "columns_df": columns_df,
        "model_raw": model,
    }


def _build_combined_df(
    tables_df: pd.DataFrame,
    measures_df: pd.DataFrame,
    columns_df: pd.DataFrame,
    report_name: str,
) -> pd.DataFrame:
    """
    Constrói um DataFrame unificado com todas as informações,
    similar ao formato utilizado pelo PBIAutoDoc.
    """
    rows = []

    # Linhas de tabelas (incluindo fonte de dados)
    for _, t in tables_df.iterrows():
        rows.append({
            "ReportName": report_name,
            "NomeTabela": t["NomeTabela"],
            "FonteDados": t["FonteDados"],
            "NomeMedida": None,
            "ExpressaoMedida": None,
            "NomeColuna": None,
            "TipoDadoColuna": None,
            "TipoColuna": None,
            "ExpressaoColuna": None,
        })

    # Linhas de medidas
    for _, m in measures_df.iterrows():
        rows.append({
            "ReportName": report_name,
            "NomeTabela": m.get("NomeTabela", "Medidas"),
            "FonteDados": None,
            "NomeMedida": m["NomeMedida"],
            "ExpressaoMedida": m["ExpressaoMedida"],
            "NomeColuna": None,
            "TipoDadoColuna": None,
            "TipoColuna": None,
            "ExpressaoColuna": None,
        })

    # Linhas de colunas
    for _, c in columns_df.iterrows():
        rows.append({
            "ReportName": report_name,
            "NomeTabela": c["NomeTabela"],
            "FonteDados": None,
            "NomeMedida": None,
            "ExpressaoMedida": None,
            "NomeColuna": c["NomeColuna"],
            "TipoDadoColuna": c["TipoDadoColuna"],
            "TipoColuna": c["TipoColuna"],
            "ExpressaoColuna": c["ExpressaoColuna"],
        })

    return pd.DataFrame(rows)
