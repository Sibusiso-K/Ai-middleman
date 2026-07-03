@echo off
set "PATH=C:\Users\lovilocal.adm\AppData\Local\node-portable22\node-v22.12.0-win-x64;%PATH%"
cd /d "%~dp0"
npm run dev -- --port 5174
