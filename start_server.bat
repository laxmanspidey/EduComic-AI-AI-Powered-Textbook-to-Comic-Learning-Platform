@echo off
title AI Comic Textbook - Django Server
echo ============================================
echo   AI Comic Textbook - Starting Server
echo ============================================
echo.
echo Make sure ComfyUI is running at http://127.0.0.1:8188
echo Make sure Ollama is running (ollama serve)
echo.
echo Starting Django development server on http://127.0.0.1:8000
echo Login: admin / admin123
echo.
call venv\Scripts\python manage.py runserver 127.0.0.1:8000
pause
