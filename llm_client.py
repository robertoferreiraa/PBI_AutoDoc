"""
llm_client.py — Cliente LiteLLM unificado para chamadas a modelos de linguagem
"""

import json
import os
import tiktoken
from litellm import completion
from prompts import SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Tokenização
# ---------------------------------------------------------------------------

def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Conta tokens de um texto usando tiktoken."""
    try:
        enc = tiktoken.get_encoding(model)
        return len(enc.encode(text))
    except Exception:
        # Fallback: estimativa simples por palavras
        return len(text.split()) * 4 // 3


def chunk_text_by_tokens(
    segments: list[str],
    max_tokens: int = 3000,
) -> list[str]:
    """
    Agrupa uma lista de segmentos em chunks que não excedam max_tokens.
    Cada chunk é uma string com os segmentos concatenados.
    """
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for seg in segments:
        seg_tokens = count_tokens(seg)
        if current and current_tokens + seg_tokens > max_tokens:
            chunks.append("\n".join(current))
            current = [seg]
            current_tokens = seg_tokens
        else:
            current.append(seg)
            current_tokens += seg_tokens

    if current:
        chunks.append("\n".join(current))

    return chunks


# ---------------------------------------------------------------------------
# Chamada ao modelo
# ---------------------------------------------------------------------------

def _clean_response(text: str) -> str:
    """Remove marcadores markdown do JSON retornado pelo modelo."""
    text = text.strip()
    # Remove blocos ```json ... ``` ou ``` ... ```
    for marker in ("```json", "```JSON", "```"):
        text = text.replace(marker, "")
    return text.strip()


def call_llm(
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 8192,
    temperature: float = 0,
) -> dict:
    """
    Chama o modelo via LiteLLM e retorna o JSON parseado.

    Parâmetros
    ----------
    modelo : str
        Nome do modelo no formato LiteLLM (ex: "gpt-4.1-mini", "claude-3-7-sonnet-20250219")
    system_prompt : str
        Prompt do sistema
    user_prompt : str
        Prompt do usuário com os dados
    max_tokens : int
        Máximo de tokens na resposta
    temperature : float
        Temperatura do modelo

    Retorna
    -------
    dict  (JSON parseado do modelo)

    Levanta
    -------
    Exception  em caso de erro após tentativa com modelo fallback
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = completion(
            model=modelo,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        raw = response.choices[0].message.content
        cleaned = _clean_response(raw)
        return json.loads(cleaned)

    except Exception as e:
        # Fallback: tenta com um modelo Groq gratuito
        fallback = "groq/meta-llama/llama-4-scout-17b-16e-instruct"
        print(f"[LLM] Erro com '{modelo}': {e}. Tentando fallback '{fallback}'...")
        try:
            response = completion(
                model=fallback,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw = response.choices[0].message.content
            cleaned = _clean_response(raw)
            return json.loads(cleaned)
        except Exception as e2:
            raise RuntimeError(
                f"Falha ao chamar LLM com modelo '{modelo}' e fallback '{fallback}': {e2}"
            ) from e2


def call_llm_text(
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 8192,
    temperature: float = 0.3,
) -> str:
    """
    Chama o modelo e retorna texto puro (sem parse JSON).
    Usado para o chat interativo.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = completion(
        model=modelo,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Carga de modelos disponíveis
# ---------------------------------------------------------------------------

def get_available_models() -> list[str]:
    """Retorna a lista de modelos configurados via variável de ambiente."""
    raw = os.getenv("AVAILABLE_MODELS", "")
    if raw:
        return [m.strip() for m in raw.split(",") if m.strip()]
    # Padrão mínimo
    return ["gpt-4.1-mini", "claude-3-7-sonnet-20250219", "gemini/gemini-2.5-flash-preview-04-17"]


def get_default_model() -> str:
    """Retorna o modelo padrão configurado."""
    return os.getenv("DEFAULT_MODEL", "gpt-4.1-mini")
