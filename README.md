# Bootcamp Shop (FastAPI)

A small online shop: browse products, add to cart, sign in with Google, check out, and get a confirmation email.

- **Backend:** Python FastAPI + Jinja2 templates
- **Database:** Postgres on Supabase or Neon (SQLAlchemy). Tables are created automatically on startup.
- **Login:** Google OAuth via Google Cloud Console
- **Emails:** Mailgun API

## Run it locally

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in the values (steps below)
uvicorn app.main:app --reload
```

Open http://localhost:8000

With an empty `DATABASE_URL` it uses a local SQLite file, so you can try the shop before setting up anything. Google login and emails need the steps below.

## 1. Database (pick Supabase OR Neon)

**Supabase**
1. Create a project at supabase.com.
2. Click **Connect** (or Project Settings -> Database) and copy the **Session pooler** connection string (URI).
3. Replace `[YOUR-PASSWORD]` with your database password and put it in `.env` as `DATABASE_URL`.

**Neon**
1. Create a project at neon.tech.
2. Copy the connection string from the dashboard (it ends with `?sslmode=require`).
3. Put it in `.env` as `DATABASE_URL`.

Start the app once and the `users`, `products`, `orders` and `order_items` tables are created, with 6 sample products.

## 2. Google login (Google Cloud Console)

1. Go to console.cloud.google.com and create a project.
2. **APIs & Services -> OAuth consent screen**: choose External, fill in app name and your email, and add your own Gmail as a **test user**.
3. **APIs & Services -> Credentials -> Create credentials -> OAuth client ID** -> type **Web application**.
4. Under **Authorized redirect URIs** add exactly:
   `http://localhost:8000/auth/google/callback`
   (after deploying, also add `https://YOUR-SITE/auth/google/callback`).
5. Copy the Client ID and Client secret into `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

## 3. Mailgun emails

1. Sign up at mailgun.com. Use the free **sandbox domain** shown under Sending -> Domains.
2. Sandbox domains only send to **authorized recipients**: open the sandbox domain, add your own email under "Authorized Recipients", and click the verification link Mailgun emails you. Use that same email for Google login when testing.
3. Create an API key (Settings -> API keys) and put it in `.env` as `MAILGUN_API_KEY`.
4. Set `MAILGUN_DOMAIN` to the sandbox domain, and `MAILGUN_FROM` like `Bootcamp Shop <postmaster@YOUR-SANDBOX-DOMAIN>`.
5. If your Mailgun account is in the EU region, set `MAILGUN_API_BASE=https://api.eu.mailgun.net`.

## How it works

| Step | Where |
|------|-------|
| Products, cart (kept in a signed cookie) | `app/main.py` |
| Google sign-in, user saved in DB | `/auth/google`, `/auth/google/callback` |
| Checkout page, order + items saved in DB | `/checkout` |
| Confirmation email sent after order is saved | `app/emailer.py` |
| Order history | `/orders` |

If an email fails to send, the order is still saved; `orders.email_sent` stays `false` so you can see which ones failed.

## Deploying

Set the same variables from `.env` on your host (Render, Railway, Fly.io...), set `BASE_URL` to your public URL, and add the matching redirect URI in Google Cloud Console. Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
