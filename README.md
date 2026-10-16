# ChainWealth Capital

Cryptocurrency investment brokerage platform with user accounts and admin balance control.

## Admin Credentials
- Username: `admin`
- Password: `ChainWealth@Admin2026`

## Deploy to Render (Recommended – Free)

1. Go to [render.com](https://render.com) and sign up / log in.
2. Click **New +** → **Web Service**.
3. Connect your GitHub (or upload this folder as a repo).
4. Settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Environment:** Python
5. Add environment variable (optional but recommended):
   - `SECRET_KEY` = any long random string
6. Click **Create Web Service**.

After deployment you’ll get a public URL like `https://chainwealthcapital.onrender.com`.

**Note:** On the free plan, the disk is ephemeral — user data (balances, accounts) resets when the service restarts or sleeps. For persistent data you would need a paid plan or external database (PostgreSQL).

## Run Locally
```bash
pip install -r requirements.txt
python app.py
```
Then open http://localhost:5000
