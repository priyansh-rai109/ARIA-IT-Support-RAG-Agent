# ARIA: Production Deployment Master Guide 🚀

This guide provides step-by-step instructions for deploying ARIA as an enterprise-grade AI Operating System to production using **Railway** (Backend) and **Vercel** (Frontend).

## Architecture
- **Frontend**: Next.js deployed on Vercel (Global Edge Network, automatic HTTPS).
- **Backend**: FastAPI deployed on Railway Docker container (Persistent WebSockets, background tasks).
- **Vector Database**: ChromaDB running inside the Backend container with a persistent volume mount.
- **Cache**: Managed Redis on Railway.

---

## Phase 1: Backend Deployment (Railway)

1. **Create a Railway Account:** Go to [railway.app](https://railway.app) and sign up.
2. **Create a New Project:** Click "New Project" -> "Deploy from GitHub repo".
3. **Select your Repository:** Connect your ARIA GitHub repository.
4. **Configure Environment Variables:** Go to the Variables tab and add:
   - `GROQ_API_KEY`: Your Groq API key.
   - `JWT_SECRET`: A strong random string for auth tokens.
5. **Add Redis (Optional but Recommended):** 
   - In your Railway project, click "New" -> "Database" -> "Add Redis".
   - Link the internal Redis URL to your Backend service as `REDIS_URL`.
6. **Add Persistent Volume for ChromaDB:**
   - Go to your Backend service settings.
   - Under "Volumes", click "Add Volume".
   - Mount path: `/app/backend/database`.
7. **Deploy:** The `railway.toml` file in the root directory will automatically tell Railway to use the `backend/Dockerfile` and start the server with Uvicorn.
8. **Get the Public URL:** Once deployed, go to the Settings tab of your backend service, and generate a Public Domain. (e.g., `aria-backend-production.up.railway.app`).

---

## Phase 2: Frontend Deployment (Vercel)

1. **Create a Vercel Account:** Go to [vercel.com](https://vercel.com) and sign up.
2. **Import Project:** Click "Add New..." -> "Project" -> "Import from Git Repository".
3. **Configure Framework:** Ensure the Framework Preset is set to **Next.js**.
4. **Root Directory:** Edit the Root Directory and set it to `aria-frontend`.
5. **Configure Environment Variables:**
   - Add `NEXT_PUBLIC_API_URL`: The public Railway URL you got in Phase 1 (e.g., `https://aria-backend-production.up.railway.app`).
6. **Deploy:** Click Deploy. Vercel will build the frontend using the rules defined in `aria-frontend/vercel.json`.
7. **HTTPS & Voice:** Vercel automatically secures the domain with an SSL certificate. This is critical, as microphone permissions for the Voice AI will *only* work over HTTPS.

---

## Phase 3: CI/CD Pipeline (GitHub Actions)

We have included a GitHub Actions workflow `.github/workflows/deploy.yml`. 
To enable automated deployments on every `git push` to `main`:

1. Go to your GitHub Repository -> **Settings** -> **Secrets and variables** -> **Actions**.
2. Add the following repository secrets:
   - `RAILWAY_TOKEN`: Generate this from your Railway account settings.
   - `VERCEL_TOKEN`: Generate this from your Vercel account settings.
   - `VERCEL_ORG_ID` & `VERCEL_PROJECT_ID`: Get this by running `vercel link` locally.

Once configured, pushing to `main` will automatically lint the Python backend, build the Next.js frontend, and deploy both to their respective clouds.

---

## Alternative: Self-Hosted Docker Deployment (AWS/Azure/GCP)

If you prefer deploying ARIA to a traditional Virtual Machine (EC2, Droplet, VM Instance):

1. SSH into your production server.
2. Clone your repository.
3. Edit the `.env` file with your production keys.
4. Run the production docker-compose file:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d --build
   ```
This setup will automatically launch the backend, a Redis container, and mount persistent volumes for ChromaDB `chroma_data` locally.

---

## Production Security Checklist
- [ ] Ensure `.env` is **never** committed to version control.
- [ ] Change the `JWT_SECRET` to a highly secure randomly generated string.
- [ ] Use HTTPS on the frontend (Vercel handles this).
- [ ] Ensure `CORS_ORIGINS` in `backend/api.py` is locked down strictly to your Vercel URL instead of `*`.
