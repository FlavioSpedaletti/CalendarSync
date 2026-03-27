@echo off
cd /d C:\Projetos\CalendarSync

echo Iniciando o Azurite (Emulador de Banco de Dados)...
start /B azurite --silent --skipApiVersionCheck

call .venv\Scripts\activate.bat
func host start
pause
