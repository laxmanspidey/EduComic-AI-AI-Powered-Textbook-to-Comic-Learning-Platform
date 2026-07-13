@echo off
title AI Comic Textbook - Task Worker
echo ============================================
echo   AI Comic Textbook - Background Worker
echo ============================================
echo.
echo This window runs background tasks:
echo  - PDF processing (RAG pipeline)
echo  - Comic generation (ComfyUI API calls)
echo.
echo Keep this window open while using the app!
echo.
call venv\Scripts\python manage.py qcluster
pause
