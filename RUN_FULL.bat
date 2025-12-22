@echo off
REM Full Production Run - Batch Enrichment V2
REM Enriches all 2,763 practices

echo ============================================
echo Batch Enrichment V2 - FULL RUN
echo ============================================
echo.
echo WARNING: This will process ALL 2,763 practices
echo Estimated time: 3-5 hours
echo Estimated cost: ~$80-100
echo.
echo Press Ctrl+C to cancel, or
pause

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run setup first.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run full enrichment
echo.
echo Starting full enrichment...
echo Progress will be saved after each practice.
echo You can stop and resume at any time.
echo.
python batch_enrich_v2.py

echo.
echo ============================================
echo Enrichment Complete!
echo ============================================
echo Results saved to: data/enriched/dpc_enriched_v2_FINAL.json
echo Check the logs in: batch_enrichment_v2.log
echo.
pause
