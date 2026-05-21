@echo off
echo Running analysis batch (%date% %time%)...
echo Processes up to %BATCH_SIZE% PDFs then stops.
echo Run this repeatedly (or schedule it) until all PDFs are analyzed.
echo.
python analyze_reports.py
echo.
echo Done. Check Batch Status tab in the app for progress.
pause
