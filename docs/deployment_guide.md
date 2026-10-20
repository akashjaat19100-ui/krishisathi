# 🚀 KisanSathi Deployment Guide
### How to Deploy KisanSathi on the Internet for Free

Here are the 3 simplest ways to deploy your app, depending on what you need:

---

## ⚡ Method 1: Instant Public Link (Share in 10 Seconds without Cloud Setup)

If your app is running locally on your laptop (`./run.sh`), you can generate an instant secure HTTPS public link that works on any phone, anywhere in the world.

### Using Cloudflare Tunnel (Free & No Signup Required):
In your terminal, run:
```bash
npx localtunnel --port 8000
```
or with cloudflared:
```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared tunnel --url http://localhost:8000
```
It gives you a public URL (e.g. `https://random-word.trycloudflare.com`). Send this link to anyone or open it on your phone!

---

## ☁️ Method 2: Free 24/7 Cloud Hosting on Render.com (Permanent Link)

Render offers a generous **100% free tier** for web services.

### Step-by-Step:
1. **Push your code to GitHub**:
   ```bash
   cd /Users/akashdhillon/.gemini/antigravity/scratch/krishisathi
   git init
   git add .
   git commit -m "Initial commit of KisanSathi"
   # Create a repository on github.com and link it:
   git remote add origin https://github.com/YOUR_USERNAME/kisansathi.git
   git push -u origin main
   ```

2. **Deploy on Render**:
   - Go to [render.com](https://render.com) and sign up with GitHub.
   - Click **"New +"** $\rightarrow$ **"Web Service"**.
   - Select your `kisansathi` GitHub repository.
   - Fill in the settings:
     - **Name**: `kisansathi`
     - **Region**: Singapore or Frankfurt (fastest for India)
     - **Branch**: `main`
     - **Runtime**: `Python 3`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `python run.py`
     - **Instance Type**: `Free`
   - Click **"Deploy Web Service"**.

Render will build and give you a permanent public URL:
👉 `https://kisansathi.onrender.com`

---

## 🐳 Method 3: Deploy with Docker on Any VPS (AWS / DigitalOcean / Linode)

If you have a Linux cloud server / VPS:

1. Copy the project folder to your server:
   ```bash
   scp -r /Users/akashdhillon/.gemini/antigravity/scratch/krishisathi user@your_server_ip:/home/user/
   ```
2. SSH into your server:
   ```bash
   ssh user@your_server_ip
   cd /home/user/krishisathi
   ```
3. Run with Docker Compose:
   ```bash
   docker compose up -d --build
   ```
The app will run automatically in the background on port `8000`.
