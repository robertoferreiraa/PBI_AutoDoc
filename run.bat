@echo off
echo ==============================================
echo Iniciando o Servidor PBI DocGen...
echo O frontend esta integrado ao backend na porta 8000.
echo ==============================================
echo.

:: Abre o navegador padrao no endereco da aplicacao
start http://localhost:8000

:: Inicia o servidor usando o ambiente virtual
.venv\Scripts\python main.py

pause
