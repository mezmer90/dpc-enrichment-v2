# Railway Deployment Instructions

## ⚠️ CRITICAL: Environment Variables to Set

After deploying to Railway, you **MUST** set these environment variables in the Railway dashboard to prevent resource exhaustion and crashes.

### Required Environment Variables

Go to **Railway Dashboard → Your Project → Variables** and add:

```bash
# Resource Limits (CRITICAL - prevents thread explosion)
OPENBLAS_NUM_THREADS=4
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4

# Worker Configuration (CRITICAL - prevents resource exhaustion)
MAX_WORKERS=2

# Playwright Browser Cache
PLAYWRIGHT_BROWSERS_PATH=/tmp/.playwright

# API Keys (already set, but verify)
OPENROUTER_API_KEY=sk-or-v1-...
SCRAPERAPI_KEY=...

# Database & Redis (auto-provided by Railway)
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# App Configuration
FLASK_SECRET_KEY=...
APP_PASSWORD=dpc2025
USE_SCRAPING_API=true
CHECKPOINT_INTERVAL=1
```

## Why These Limits Are Critical

### Before (Without Limits)
- ❌ 6 concurrent workers
- ❌ 48 threads per worker from OpenBLAS
- ❌ Total: 6 × 48 = 288+ threads just from numpy/pandas
- ❌ Result: `pthread_create failed`, SIGSEGV crashes, 50+ minute hangs

### After (With Limits)
- ✅ 2 concurrent workers
- ✅ 4 threads per worker from OpenBLAS
- ✅ Total: 2 × 4 = 8 threads from numpy/pandas
- ✅ Result: Stable, no crashes, completes all practices

## Deployment Checklist

- [ ] Set `OPENBLAS_NUM_THREADS=4`
- [ ] Set `OMP_NUM_THREADS=4`
- [ ] Set `MKL_NUM_THREADS=4`
- [ ] Set `MAX_WORKERS=2`
- [ ] Set `PLAYWRIGHT_BROWSERS_PATH=/tmp/.playwright`
- [ ] Verify `OPENROUTER_API_KEY` is set
- [ ] Verify `SCRAPERAPI_KEY` is set
- [ ] Deploy code changes
- [ ] Monitor first 50 practices for stability
- [ ] Check logs for resource warnings

## Monitoring After Deployment

Watch for these log messages indicating healthy operation:

```
✅ Resources: CPU=45.2%, RAM=62.1%, Threads=87, Children=12, Health=0.78
✅ System circuit breaker: Resources OK
✅ Processing 25/500: [Practice Name]
```

Watch for these WARNING signs:

```
⚠️ Resource warning (1/3): num_threads exceeded: 156.0 > 150
⚠️ System circuit breaker OPENED: memory_mb exceeded: 3214.5 > 3000
```

If you see warnings:
1. Circuit breaker will automatically skip practices until resources recover
2. System will wait 2 minutes before retrying
3. This is **normal and expected** - it prevents crashes
4. The system will continue after recovery

## Expected Performance

- **Processing Rate**: ~2-3 practices/minute (slower but stable)
- **Total Time for 500 practices**: 3-4 hours
- **Memory Usage**: 1.5-2.5 GB peak
- **Thread Count**: 50-150 threads
- **Success Rate**: 90-95% (some practices may be skipped due to resource constraints)

## If Issues Persist

If you still see crashes after setting these variables:

1. **Reduce MAX_WORKERS to 1**: Even more conservative
2. **Check Railway plan limits**: Ensure you have enough RAM/CPU allocated
3. **Enable verbose logging**: Set `LOG_LEVEL=DEBUG` temporarily
4. **Contact support**: Share logs showing resource usage patterns
