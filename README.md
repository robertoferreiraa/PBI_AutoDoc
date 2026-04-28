# PBI AutoDoc — Documentação da Aplicação

O **PBI AutoDoc** é uma ferramenta completa que automatiza a extração e a geração de documentação inteligente de relatórios criados no Power BI. A aplicação lê a estrutura do modelo de dados do arquivo local ou na nuvem e, com o apoio de Inteligência Artificial (LLMs), documenta tabelas, medidas, colunas e relacionamentos de forma interativa.

---

## 1. Visão Geral das Funcionalidades

- **Extração Local:** Suporte aos formatos `.pbit`, `.pbix` e `.zip` para abrir e ler a estrutura JSON do `DataModelSchema`.
- **Integração na Nuvem (PBI Service):** Conexão ao Azure AD (Service Principal) para listar workspaces, datasets e relatórios, permitindo a extração de metadados direto do ambiente publicado via REST API do Power BI.
- **Geração de Documentação por IA:** Análise de blocos (Tabelas, Medidas, Relacionamentos e Fontes) usando modelos de linguagem via `LiteLLM` (OpenAI, Gemini, Groq, Anthropic). A IA documenta e explica o significado das regras de negócios implementadas em DAX e M.
- **Exportação:** Geração de relatórios robustos nos formatos `.docx` (Word) e `.xlsx` (Excel).
- **Explorador / Chat de Dados:** Um painel interativo que permite fazer perguntas ao LLM sobre o relatório extraído e a sua documentação.

---

## 2. Tecnologias Utilizadas

### Backend (Python)
- **FastAPI:** Framework web principal da aplicação, responsável pelas rotas REST e SSE (Server-Sent Events) para o streaming do progresso da IA.
- **Pandas:** Estruturação dos metadados extraídos em DataFrames para o processamento de regras.
- **LiteLLM:** Orquestrador para a conexão com as APIs de inteligência artificial (OpenAI, Groq, Anthropic, Gemini).
- **python-docx / openpyxl / xlsxwriter:** Bibliotecas responsáveis pela geração e formatação dos documentos a serem baixados pelo usuário.
- **Uvicorn:** Servidor ASGI para rodar a aplicação FastAPI.

### Frontend
- **HTML5 / CSS3 (Vanilla):** Interface leve em página única (SPA), com design moderno e responsivo (tema claro atualizado).
- **JavaScript (app.js):** Gerenciamento do estado da UI, envio de arquivos (multipart form), comunicação com a API (fetch) e controle de WebSockets/SSE para atualização da barra de progresso.

---

## 3. Estrutura do Projeto

```text
Docs_PBI/
├── main.py              # Ponto de entrada (API FastAPI e rotas)
├── extractor.py         # Lógica de extração de metadados de arquivos físicos (.pbit/.pbix)
├── pbi_service.py       # Lógica de conexão e extração da API do Power BI Service via Azure
├── documenta.py         # Lógica de negócio para a IA gerar a documentação em lotes
├── llm_client.py        # Configurações do LiteLLM (modelos e fallbacks)
├── prompts.py           # Textos base de engenharia de prompt enviados ao LLM
├── requirements.txt     # Dependências Python do projeto
├── run.bat              # Script facilitador para inicializar servidor e abrir o navegador
├── .env                 # Variáveis de ambiente (Chaves de API, credenciais)
├── static/              # Arquivos front-end servidos na raiz da porta 8000
│   ├── index.html       # Estrutura principal da tela
│   ├── logo.png         # Logo da aplicação
│   ├── css/style.css    # Estilização visual (cores, layout, responsividade)
│   └── js/app.js        # Lógica de chamadas de API e manipulação do DOM
└── README.md            # Este arquivo de documentação
```

---

## 4. Como Configurar e Executar

### Pré-requisitos
- Python 3.10 ou superior.
- Pelo menos uma chave de API (OpenAI ou Gemini ou Groq).

### Passo 1: Dependências
Com o Python instalado, crie o ambiente virtual e instale as bibliotecas:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Passo 2: Configurar Chaves de API
Crie ou edite o arquivo `.env` na raiz do projeto, removendo o caractere de comentário `#` das chaves desejadas. Exemplo:
```env
OPENAI_API_KEY=sk-proj-xxxxxx...
GEMINI_API_KEY=AIzaSyxxxxxx...
```

### Passo 3: Rodar a Aplicação
Você pode iniciar a aplicação de duas formas:
1. **Pelo script facilitador:** Dê dois cliques em `run.bat`. Ele subirá o servidor e abrirá o navegador automaticamente em `http://localhost:8000`.
2. **Manualmente via terminal:**
```bash
.venv\Scripts\python main.py
```
*(O frontend está integrado dentro do `main.py`, sendo servido na rota principal).*

---

## 5. Fluxo de Operação

1. **Upload:** O usuário insere um arquivo `.pbit`. O sistema lê os metadados brutos localmente e extrai tabelas/medidas sem o uso de nuvem.
2. **Revisão:** A interface exibe o painel estatístico no frontend, permitindo validar o número de medidas e colunas identificadas.
3. **Documentação:** O usuário clica em "Gerar Documentação". O front-end aciona a rota SSE. O Backend invoca o LLM fatiando os dados em blocos (para não estourar o limite de tokens). Cada retorno avança a barra de progresso.
4. **Finalização:** Disponibilização dos botões para exportação final no layout Microsoft Word ou planilhas Excel. O usuário agora pode utilizar a aba Explorador para consultar detalhes da documentação levantada.
