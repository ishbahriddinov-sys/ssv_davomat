@echo off
REM Обратный прокси + автоматический HTTPS (Caddy для Windows).
REM Требуется caddy.exe в этой папке. Домен берётся из переменной DOMAIN.
cd /d "%~dp0"
set DOMAIN=ssvdavomat.uz
caddy.exe run --config Caddyfile
