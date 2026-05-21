@echo off
echo Starting Drowning Cases Explorer...
echo App will open at http://localhost:8501
echo Press Ctrl+C to stop.
echo.
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
