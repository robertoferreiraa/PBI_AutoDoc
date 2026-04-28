# 🚀 PBI AutoDoc

**PBI AutoDoc** é uma solução inteligente e automatizada para geração de documentação técnica de modelos do Power BI. Utilizando Inteligência Artificial de ponta, a ferramenta extrai metadados, analisa medidas DAX e cria relatórios detalhados em segundos.

![License](https://img.shields.io/github/license/robertoferreiraa/PBI_AutoDoc)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)

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

### Pré-requisitos
- Python 3.9+
- Chave de API de um provedor de LLM (OpenAI, Gemini, etc.)

### Instalação Local

1. **Clone o repositório**:
   ```bash
   git clone https://github.com/robertoferreiraa/PBI_AutoDoc.git
   cd PBI_AutoDoc
   ```

2. **Crie um ambiente virtual**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
   ```

3. **Instale as dependências**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as variáveis de ambiente**:
   Crie um arquivo `.env` na raiz do projeto:
   ```env
   OPENAI_API_KEY=sua_chave_aqui
   GEMINI_API_KEY=sua_chave_aqui
   DEFAULT_MODEL=gpt-4o-mini
   ```

5. **Inicie a aplicação**:
   ```bash
   python main.py
   ```
   Acesse: `http://localhost:8000`

---

## ☁️ Deploy no Railway

Este projeto está configurado para deploy imediato no **Railway.app**.

1. Conecte seu repositório no painel do Railway.
2. Adicione as chaves de API nas **Variables**.
3. O deploy será feito automaticamente usando o `Procfile` incluso.

---

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

Desenvolvido com ❤️ por [Roberto Ferreira](https://github.com/robertoferreiraa)
