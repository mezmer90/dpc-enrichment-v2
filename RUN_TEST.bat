@echo off
REM Quick Test Run - Batch Enrichment V2
REM Tests with 5 practices

echo ============================================
echo Batch Enrichment V2 - Test Run
echo ============================================
echo.
echo This will test the enrichment with 5 practices
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run setup first:
    echo   1. python -m venv venv
    echo   2. venv\Scripts\activate
    echo   3. pip install -r requirements_enrichment.txt
    echo   4. playwright install chromium
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run test
echo Running enrichment with 5 practices...
echo.
python batch_enrich_v2.py --limit 5

echo.
echo ============================================
echo Test Complete!
echo ============================================
echo Check the output in: data/enriched/
echo Check the logs in: batch_enrichment_v2.log
echo.
pause
