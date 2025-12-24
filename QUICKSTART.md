# Quick Start Guide - DPC Enrichment V2

## Setup (First Time Only)

### 1. Create .env File
```powershell
copy .env.example .env
notepad .env
```

Add your API keys:
```env
OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY_HERE
SCRAPERAPI_KEY=YOUR_KEY_HERE
```

Get keys from:
- OpenRouter: https://openrouter.ai/keys
- ScraperAPI: https://www.scraperapi.com/

### 2. Validate Setup
```powershell
python validate_setup.py
```

Expected output: `[OK] ALL TESTS PASSED!`

## Running Enrichment

### Test Run (5 practices)
```powershell
python batch_enrich_v2.py --limit 5
```

### Full Run (All practices)
```powershell
python batch_enrich_v2.py
```

Or use batch files:
```powershell
RUN_TEST.bat    # Test with 5 practices
RUN_FULL.bat    # Full run
```

## What to Expect

### Console Output
```
[OK] Loaded environment variables
[OK] ScraperAPI (98.9% success rate)
[OK] Smart URL selector (Gemini AI)
[OK] Progressive saving (after EVERY practice)

Processing 1/5: Practice Name
  Scraped: 7 pages (12543 chars)
  Enriched: 73 fields extracted (cost: $0.0045)
  [SUCCESS] Practice Name completed!
```

### If API Budget Runs Out
```
[!] API BUDGET/CREDITS EXHAUSTED

Action required:
1. Go to OpenRouter dashboard
2. Add more credits/upgrade your plan
3. Press Enter to resume enrichment

IMPORTANT: Data is safe - all progress has been saved!
```

**Don't worry!** The system will:
- Pause automatically
- Save all progress
- NOT mark practices as failed
- Resume from exact same point when you press Enter

## Monitoring Progress

### Log File
- `batch_enrichment_v2.log` - Full UTF-8 log with all details

### Output Files
- `data/enriched/dpc_enriched_v2_FINAL.json` - Enriched practices
- `data/progress/enrichment_v2_state.json` - Progress tracking
- `data/markdown/` - Scraped website content

## Troubleshooting

### "API key not set" error
➜ Check your `.env` file has the correct keys

### Unicode/encoding errors
➜ All fixed! You should see `[OK]` instead of emojis

### API budget/rate limit errors
➜ System will pause and ask you to refresh - just follow instructions

### Validation fails
➜ Run `python validate_setup.py` and fix reported issues

## Cost Estimates

### Test Run (5 practices)
- Cost: ~$0.15
- Time: ~30 seconds

### Full Run (2,763 practices)
- Cost: ~$80-100
- Time: 3-5 hours
- Success Rate: 90-95%

## Resume After Stopping

The system auto-saves after EVERY practice. If you stop (Ctrl+C) or crash:

```powershell
# Just run again - it will auto-resume!
python batch_enrich_v2.py
```

Output:
```
[RESUME] Auto-resume detected: 125 already completed, 2638 pending
```

## Need Help?

1. Check `STREAMLINING_SUMMARY.md` for detailed changes
2. Run `python validate_setup.py` to diagnose issues
3. Review `batch_enrichment_v2.log` for error details

---

**You're all set!** Run `python validate_setup.py` first, then start with a test run.
