# Railway Deployment Guide - GitHub Integration

## 🚀 Deploy from GitHub (Recommended)

Railway has **seamless GitHub integration** - it automatically deploys your app from your GitHub repository and redeploys on every push.

---

## 📋 Prerequisites

1. ✅ GitHub account
2. ✅ Railway account (sign up at https://railway.app)
3. ✅ Code pushed to GitHub
4. ✅ API keys ready (OpenRouter, ScraperAPI)

---

## 🎯 Step-by-Step Deployment

### **Step 1: Push Code to GitHub**

```powershell
# If not done yet:
git init
git add .
git commit -m "Initial commit: DPC Enrichment V2 with Railway"
git remote add origin https://github.com/YOUR_USERNAME/dpc-enrichment-v2.git
git branch -M main
git push -u origin main
```

---

### **Step 2: Create Railway Project**

1. Go to https://railway.app
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub
5. Select your repository: `dpc-enrichment-v2`
6. Railway will auto-detect it's a Python app

---

### **Step 3: Add PostgreSQL Database**

1. In your Railway project, click **"+ New"**
2. Select **"Database"** → **"PostgreSQL"**
3. Railway will:
   - Create PostgreSQL instance
   - Auto-generate `DATABASE_URL`
   - Connect it to your app

---

### **Step 4: Add Redis**

1. Click **"+ New"** again
2. Select **"Database"** → **"Redis"**
3. Railway will:
   - Create Redis instance
   - Auto-generate `REDIS_URL`
   - Connect it to your app

---

### **Step 5: Set Environment Variables**

In your Railway project settings, add these variables:

```env
# API Keys (REQUIRED)
OPENROUTER_API_KEY=sk-or-v1-your_key_here
SCRAPERAPI_KEY=your_key_here

# Flask Config
FLASK_SECRET_KEY=your-random-secret-key-here
FLASK_ENV=production

# Enrichment Config (Optional)
MAX_WORKERS=6
CHECKPOINT_INTERVAL=1

# Database & Redis (Auto-provided by Railway)
# DATABASE_URL=postgresql://...  (already set)
# REDIS_URL=redis://...          (already set)
```

**Generate secret key:**
```python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

### **Step 6: Deploy Worker Service**

Railway needs TWO services: **web** (Flask) and **worker** (Celery)

1. In Railway project, click **"+ New"**
2. Select **"Empty Service"**
3. Connect to same GitHub repo
4. In settings:
   - **Service Name**: `worker`
   - **Start Command**: `celery -A webapp.tasks.celery_app worker --loglevel=info`
   - Add same environment variables

---

### **Step 7: Deploy!**

Railway automatically deploys when you:
- Push to GitHub
- Change environment variables
- Manually click "Deploy"

**First deployment takes ~5-10 minutes** (installing Playwright, etc.)

---

## 🔍 Post-Deployment

### **1. Check Deployment**

Your app will be at: `https://your-app-name.up.railway.app`

Visit `/health` to verify: `https://your-app-name.up.railway.app/health`

Expected response:
```json
{"status": "healthy", "service": "dpc-enrichment-web"}
```

### **2. Create Admin User**

Run this command in Railway terminal:

```python
from app import create_app, db
from webapp.models import User

app = create_app()
with app.app_context():
    user = User(username='admin', email='admin@example.com', is_admin=True)
    user.set_password('your-secure-password')
    db.session.add(user)
    db.session.commit()
    print('Admin user created!')
```

### **3. Load Practice Data**

Upload your practice data to the database (one-time setup).

---

## 🔄 Continuous Deployment

**Every time you push to GitHub:**
1. Railway detects the push
2. Rebuilds your app
3. Runs tests (if configured)
4. Deploys new version
5. Zero downtime (rolling deployment)

```powershell
# Make changes
git add .
git commit -m "Add new feature"
git push

# Railway automatically deploys! 🚀
```

---

## 📊 Railway Services Overview

Your project will have **4 services**:

1. **Web** - Flask app (main UI)
2. **Worker** - Celery worker (background enrichment)
3. **PostgreSQL** - Database
4. **Redis** - Task queue & cache

---

## 💰 Cost Estimate

### **Railway Pricing**

**Hobby Plan** (Free tier):
- $5 of free credits/month
- Then $0.000231/GB-hour

**Pro Plan** ($20/month):
- Better performance
- More resources
- Priority support

**Estimated Monthly Cost**:
- Web service: ~$10-15
- Worker service: ~$10-15
- PostgreSQL: ~$5
- Redis: ~$2
- **Total: ~$27-37/month**

### **API Costs** (Same as CLI)
- Per enrichment run: ~$83 (2,763 practices)
- OpenRouter: ~$17
- ScraperAPI: ~$66

---

## 🛠️ Railway CLI (Optional)

Install Railway CLI for advanced features:

```powershell
# Install
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# View logs
railway logs

# Run commands
railway run python manage.py

# Open dashboard
railway open
```

---

## 🔒 Security Best Practices

1. ✅ Never commit `.env` to GitHub
2. ✅ Use Railway environment variables
3. ✅ Rotate API keys regularly
4. ✅ Enable 2FA on Railway account
5. ✅ Use strong admin password
6. ✅ Monitor logs for suspicious activity

---

## 📝 Environment Variables Checklist

Required in Railway dashboard:

- [ ] `OPENROUTER_API_KEY` - Your OpenRouter key
- [ ] `SCRAPERAPI_KEY` - Your ScraperAPI key
- [ ] `FLASK_SECRET_KEY` - Random secret (generate new)
- [ ] `FLASK_ENV` - Set to `production`
- [ ] `DATABASE_URL` - Auto-provided by Railway
- [ ] `REDIS_URL` - Auto-provided by Railway

Optional:
- [ ] `MAX_WORKERS` - Number of concurrent workers (default: 6)
- [ ] `CHECKPOINT_INTERVAL` - Save frequency (default: 1)

---

## 🐛 Troubleshooting

### **Deployment fails**
- Check Railway logs
- Verify `requirements.txt` is correct
- Ensure Playwright installs successfully

### **Database connection error**
- Verify `DATABASE_URL` is set
- Check PostgreSQL service is running
- Ensure connection string format is correct

### **Worker not processing**
- Check worker service is deployed
- Verify `REDIS_URL` is set
- Check Celery logs in worker service

### **App is slow**
- Increase worker resources in Railway
- Add more Celery workers
- Enable Redis caching

---

## 📞 Support

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **GitHub Issues**: Your repo issues page

---

## 🎉 Success!

Once deployed:

1. 🌐 Access web UI at `https://your-app.up.railway.app`
2. 🔐 Login with admin credentials
3. 🚀 Start enrichment from dashboard
4. 📊 Monitor progress in real-time
5. 💾 Data persists in PostgreSQL
6. 🔄 Auto-deploys on GitHub push

**Your DPC Enrichment system is now live! 🎊**

---

## 🗺️ Next Steps

After deployment:

- [ ] Test enrichment with small batch
- [ ] Set up monitoring/alerts
- [ ] Configure custom domain (optional)
- [ ] Add more users
- [ ] Schedule enrichment runs
- [ ] Set up backups

---

**Railway + GitHub = Easy Deployment** 🚀

No Docker knowledge needed. No server management. Just push to GitHub and Railway handles the rest!
