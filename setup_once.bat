@echo off
echo ================================================
echo  Drowning Cases Explorer — First-Time Setup
echo ================================================

echo.
echo [1/4] Installing Python dependencies...
pip install -r requirements.txt

echo.
echo [2/4] Pulling Ollama models...
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text

echo.
echo [3/4] Done. Now fill in config.py with your:
echo   - AZURE_CONNECTION_STRING
echo   - AZURE_CONTAINER_NAME
echo   - LOCAL_PDF_FOLDER
echo   - SQL_SERVER_CONN (if using SQL Server)
echo.
echo [4/4] Then run these in order:
echo   python ingest.py          (download + extract PDFs)
echo   python embed_pdfs.py      (build vector DB — ~30-60 min for 6000 PDFs)
echo   python train.py           (train Vanna on schema)
echo   python analyze_reports.py (run repeatedly for structured extraction)
echo.
echo   streamlit run app.py      (launch the app)
echo.
pause
