# 🚀 PBI AutoDoc

**PBI AutoDoc** é uma solução inteligente e automatizada para geração de documentação técnica de modelos do Power BI. Utilizando Inteligência Artificial de ponta, a ferramenta extrai metadados, analisa medidas DAX e cria relatórios detalhados em segundos.

![License](https://img.shields.io/github/license/robertoferreiraa/PBI_AutoDoc)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)

---

## 🧐 Overview: Como funciona?

A aplicação automatiza o ciclo de vida da documentação técnica através de 4 pilares principais:

1.  **Extração de Metadados**: O sistema lê arquivos `.pbix`/`.pbit` ou se conecta via API ao Power BI Service para capturar a estrutura do modelo (tabelas, colunas, relacionamentos e medidas DAX) sem acessar os dados sensíveis.
2.  **Processamento por IA**: Utilizando modelos como GPT-4o e Gemini, a ferramenta interpreta fórmulas DAX complexas e as "traduz" em explicações de regras de negócio claras e concisas.
3.  **Geração Multi-Formato**: Os insights gerados são estruturados e exportados automaticamente para documentos **Word (.docx)** profissionais ou planilhas **Excel (.xlsx)** técnicas.
4.  **Interface Interativa**: Além da documentação estática, o usuário pode interagir com um Chat inteligente para tirar dúvidas específicas sobre a lógica do relatório em tempo real.

---

## ✨ Funcionalidades

- **📂 Extração Multi-Fonte**: 
  - Upload de arquivos locais (`.pbix`, `.pbit`, `.zip`).
  - Conexão direta com o **Power BI Service** via API REST (Azure AD).
- **🧠 IA Generativa**: Documentação automática de tabelas, medidas e lógica de negócio.
- **💬 Chat Interativo**: Converse com seu modelo de dados para tirar dúvidas sobre cálculos e métricas.
- **📊 Metadados Detalhados**: Visualização completa de tabelas, colunas, medidas e relacionamentos.
- **📥 Exportação Profissional**: Gere arquivos em **Word (.docx)** e **Excel (.xlsx)** formatados.
- **⚡ Streaming em Tempo Real**: Acompanhe o progresso da geração via SSE (Server-Sent Events).
- **🤖 Suporte Multi-LLM**: Integração com OpenAI (GPT-4), Anthropic (Claude), Google Gemini e Groq.

---

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python, FastAPI, Uvicorn.
- **Processamento de Dados**: Pandas, Python-docx, XlsxWriter.
- **IA/LLM**: LiteLLM (Interface unificada para múltiplos provedores).
- **Frontend**: Single Page Application (SPA) servida estaticamente.
- **Autenticação PBI**: MSAL (Microsoft Authentication Library).

---

## 🚀 Como Executar

Acesse a aplicação diretamente pelo link:
[https://web-production-e4a3c.up.railway.app](https://web-production-e4a3c.up.railway.app)


---
