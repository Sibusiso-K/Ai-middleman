@echo off
set "PATH=C:\Users\lovilocal.adm\AppData\Local\node-portable22\node-v22.12.0-win-x64;%PATH%"
cd /d "%~dp0"
if "%PORT%"=="" set PORT=5174
npm run dev -- --port %PORT%
