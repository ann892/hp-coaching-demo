# Hello Paralegal — Discovery Call Coach (Public Demo)

A free lead-magnet tool. Lawyers paste a transcript from a recent client discovery call, get an honest post-mortem in 60 seconds. Drives bookings to Hello Paralegal's discovery call.

Live: `coaching.helloparalegal.com`

## What it does

1. Lawyer lands on the page (from X post, LinkedIn, referral)
2. Enters email + firm name (lead capture)
3. Pastes a transcript (with PII redaction warning)
4. Gets back a Claude-generated post-mortem grading against the 4 pitfalls + 4-phase framework
5. Sees a CTA to book a real discovery call

## Tech

- **Streamlit** — single-file Python app
- **Anthropic Claude (`claude-opus-4-5`)** — the coach brain
- **Resend** (optional) — email notification on each new lead
- Lead capture writes to local `leads.csv`. Streamlit Community Cloud filesystem is ephemeral so set up Resend to get real-time email pings.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (public is fine — no secrets in code).
2. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub → "New app"
3. Select repo → branch `main` → main file `app.py`
4. Click "Advanced settings" → paste this into Secrets:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
CALENDLY_URL = "https://calendly.com/helloparalegal/discovery"
ADMIN_PASSWORD = "pick-a-long-random-string"

# Optional but recommended:
RESEND_API_KEY = "re_..."
LEAD_NOTIFY_EMAIL = "ann@gavelspeaks.com"
```

5. Deploy. First boot takes ~2 min.

## Custom domain (`coaching.helloparalegal.com`)

1. In the Streamlit Cloud app → "Settings" → "Custom subdomain" → set to `hp-coaching-demo` (gives you `hp-coaching-demo.streamlit.app`)
2. In your DNS (wherever you registered helloparalegal.com):
   - Add a `CNAME` record:
   - Host: `coaching`
   - Points to: `hp-coaching-demo.streamlit.app`
3. Back in Streamlit Cloud → "Settings" → "Custom domain" → add `coaching.helloparalegal.com` and follow the verification step.

DNS propagation can take up to a few hours.

## Admin

Visit `https://coaching.helloparalegal.com/?admin=YOUR_PASSWORD` to view/download captured leads as CSV.

## Run locally

```bash
cd hp-coaching-demo
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml with your real keys
python -m streamlit run app.py
```

Opens at `http://localhost:8501`.
