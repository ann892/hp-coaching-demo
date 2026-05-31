"""
Hello Paralegal — Discovery Call Coach (Public Demo)
A free lead-magnet tool: paste a transcript, get coaching feedback.
Built by Hello Paralegal. Powered by Claude.
"""

import os
import re
import csv
import time
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
from anthropic import Anthropic

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Discovery Call Coach — Hello Paralegal",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Hide Streamlit branding
HIDE_STREAMLIT_STYLE = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 780px;}
    h1 {font-family: Georgia, serif; font-weight: 600;}
    .stButton button {
        background-color: #1a1a1a;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.6rem 1.4rem;
        font-weight: 500;
    }
    .stButton button:hover {
        background-color: #333;
        color: white;
    }
    .lead-card {
        background: #f7f7f5;
        border-left: 3px solid #1a1a1a;
        padding: 1.2rem 1.5rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .cta-box {
        background: #1a1a1a;
        color: white;
        padding: 1.8rem;
        border-radius: 6px;
        margin-top: 2rem;
        text-align: center;
    }
    .cta-box a {
        color: white;
        font-weight: 600;
        text-decoration: underline;
    }
    .small-print {
        color: #888;
        font-size: 0.85rem;
        line-height: 1.5;
    }
</style>
"""
st.markdown(HIDE_STREAMLIT_STYLE, unsafe_allow_html=True)


def get_secret(key, default=""):
    """Read from Streamlit secrets or env var."""
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


ANTHROPIC_API_KEY = get_secret("ANTHROPIC_API_KEY")
CALENDLY_URL = get_secret("CALENDLY_URL", "https://calendly.com/helloparalegal/30min")
RESEND_API_KEY = get_secret("RESEND_API_KEY")
LEAD_NOTIFY_EMAIL = get_secret("LEAD_NOTIFY_EMAIL", "ann@gavelspeaks.com")
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD", "")
MAX_TRANSCRIPT_CHARS = 30000
RATE_LIMIT_HOURS = 24

LEADS_CSV = Path(__file__).parent / "leads.csv"


# ============================================================
# COACHING PROMPT (generalized for any lawyer, not Ankita-specific)
# ============================================================

COACHING_SYSTEM_PROMPT = """You are an expert sales coach for lawyers running client discovery calls — initial consults, intake calls, and referral conversations with prospective clients.

THE FRAMEWORK YOU'RE GRADING AGAINST:

**Mental Model: Closer vs Host Mode**
- CLOSER: talks 30%, listens 70%, drives the next step, absorbs pushback without retreating, names the value of what they're offering before giving it away
- HOST: talks 60%+, pitches early, suggests solutions before probing, ends with vague follow-ups ("I'll email you some thoughts")

**The 4 Pitfalls (watch for these in the transcript):**
1. **HOST MODE** — talking too much, pitching before fully understanding the matter, proposing how to handle it before hearing 3 specific facts about the client's situation
2. **SOFT ANSWER TRAP** — saying "yes I can do that" without naming the value first. E.g., "happy to include the demand letter" without "that's normally a separate $X engagement." Also includes verbal commitments without scope ("we'll figure out the deposition strategy later")
3. **PREMATURE CREDENTIAL DUMP** — answering "what's your background?" with bar admissions, schools, years of practice — before showing operational competence with concrete case outcomes or specific approaches
4. **SKIPPED CLOSE-THE-CALL MECHANIC** — ending without a locked: (a) specific date, (b) specific deliverable from the lawyer's side, (c) specific commitment from the prospect's side (signed engagement letter, deposit, document production, etc.)

**The 4-Phase Call Structure:**
- **Phase 1 — Open (first 2 min):** warm intro, ask the keystone open question ("Before I tell you anything about how I work, tell me what's going on")
- **Phase 2 — Diagnose (8-15 min):** probe with "walk me through what happened" / "what's the timeline" — drill into the 3rd-4th question for the real pain. Don't pivot to your pitch when they name a fact.
- **Phase 3 — Mirror Back (3-5 min):** play back what you heard, confirm ("Did I get that right?")
- **Phase 4 — Close-the-Call (last 5 min):** lock specific date + deliverable + commitment

**The 5 Forever Rules:**
1. Talk 30%. Listen 70%.
2. Never propose how you'll handle the matter before hearing 3 specific facts.
3. Never offer free work to defuse pressure.
4. Never apologize for the prospect's rigor or pushback.
5. Never end a call without a locked date, deliverable, and commitment from both sides.

YOUR JOB:

Read the call transcript provided. Provide an honest, specific, actionable post-mortem with these sections, in this exact order:

## Top-Line Verdict
One paragraph + numeric rating (1-10). Reference rough benchmarks:
- 2-3/10: Host mode the whole call, no close, prospect walked away unclear
- 5/10: Some good moments, multiple slips, no real close
- 7/10: Mostly solid, a couple of slips, close-the-call attempted
- 8.5/10: Closed it. Tight. Specific commitments both sides.

## What You Did Well
3-5 specific moments with direct quotes from the transcript. Each one names what they did and why it was right.

## Where You Slipped
3-5 specific moments with direct quotes. For each: (a) the moment, (b) which of the 4 pitfalls it maps to, (c) the better script they could have used (verbatim).

## Pitfall Scorecard
A checklist of the 4 pitfalls, showing ✅ avoided or ⚠️ slipped — with one-line justification each.

## Next Step (within 24 hours)
ONE specific action. Date, deliverable, who sends it.

## What to Send Next
If a follow-up email is appropriate, draft it here. Subject + body. Direct, no fluff, references specific things the prospect said.

CRITICAL RULES:
- Be honest. Don't be flattering. Specific moments and direct quotes are the key — vague feedback is worthless.
- Quote the transcript exactly when calling out moments.
- Direct, lawyer-to-lawyer, no business-school-speak.
- Every observation should reference something specific the prospect or the lawyer said.
- If they did exceptionally well, say so. If they slipped badly, say so. The goal is improvement, not encouragement.
"""


# ============================================================
# LEAD CAPTURE
# ============================================================

def log_lead(email: str, firm: str, transcript_chars: int):
    """Append lead to local CSV. Also try to email via Resend if configured."""
    # CSV log
    new_file = not LEADS_CSV.exists()
    try:
        with open(LEADS_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(["timestamp", "email", "firm", "transcript_chars"])
            writer.writerow([
                datetime.utcnow().isoformat(),
                email,
                firm,
                transcript_chars,
            ])
    except Exception as e:
        st.session_state.setdefault("_log_errors", []).append(str(e))

    # Resend email notification (optional)
    if RESEND_API_KEY:
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                method="POST",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                data=json.dumps({
                    "from": "Hello Paralegal Coach <coach@helloparalegal.com>",
                    "to": [LEAD_NOTIFY_EMAIL],
                    "subject": f"New coach lead: {firm or email}",
                    "text": (
                        f"New discovery call coach submission.\n\n"
                        f"Email: {email}\n"
                        f"Firm: {firm or '(not provided)'}\n"
                        f"Transcript length: {transcript_chars:,} chars\n"
                        f"Time: {datetime.utcnow().isoformat()}\n"
                    ),
                }).encode("utf-8"),
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass  # Don't block analysis if email fails


def rate_limit_check(email: str) -> bool:
    """Returns True if user is within rate limit (allowed), False if rate-limited."""
    if "rate_limits" not in st.session_state:
        st.session_state.rate_limits = {}
    last = st.session_state.rate_limits.get(email.lower())
    if last and (datetime.utcnow() - last) < timedelta(hours=RATE_LIMIT_HOURS):
        return False
    return True


def mark_used(email: str):
    if "rate_limits" not in st.session_state:
        st.session_state.rate_limits = {}
    st.session_state.rate_limits[email.lower()] = datetime.utcnow()


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))


# ============================================================
# CLAUDE ANALYSIS
# ============================================================

def analyze_transcript(transcript: str) -> str:
    """Run the transcript through Claude with the coaching system prompt."""
    if not ANTHROPIC_API_KEY:
        return "❌ Configuration error: ANTHROPIC_API_KEY is not set. Contact ann@gavelspeaks.com."

    # Truncate if too long
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[TRANSCRIPT TRUNCATED]"

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            system=COACHING_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Here is the call transcript. Analyze it per the framework above.\n\n---\n\n{transcript}",
            }],
        )
        return response.content[0].text
    except Exception as e:
        return f"❌ Analysis failed: {e}\n\nIf this keeps happening, DM @helloparalegal on X."


# ============================================================
# ADMIN PAGE
# ============================================================

def render_admin():
    st.title("Admin — Leads")
    if not LEADS_CSV.exists():
        st.info("No leads yet.")
        return
    with open(LEADS_CSV, "r", encoding="utf-8") as f:
        content = f.read()
    st.code(content)
    st.download_button("Download leads.csv", content, file_name="leads.csv", mime="text/csv")


# ============================================================
# MAIN UI
# ============================================================

# Admin route
query_params = st.query_params
if query_params.get("admin") and ADMIN_PASSWORD and query_params.get("admin") == ADMIN_PASSWORD:
    render_admin()
    st.stop()


# Header
st.title("Discovery Call Coach")
st.markdown(
    "**Paste a transcript from a recent client discovery call. "
    "Get an honest post-mortem in 60 seconds.**"
)

st.markdown(
    """
Lawyers run discovery calls every day — initial consults, intake calls, referrals across jurisdictions.
In 30 minutes you have to figure out fit, scope, budget, and whether to take it or refer it out.
Most of us were never taught how to systematically run that call.

This tool grades your last call against a closer's framework:

- **The 4 pitfalls** lawyers fall into (host mode, soft answers, premature credentials, no real close)
- **The 4-phase structure** of a tight discovery call
- **Specific moments** where you nailed it — and where you slipped, with the better script
- **What to send next** — a follow-up email drafted in your voice
"""
)

st.markdown("---")

# Lead capture form
if "analysis_unlocked" not in st.session_state:
    st.session_state.analysis_unlocked = False
if "lead_email" not in st.session_state:
    st.session_state.lead_email = ""
if "lead_firm" not in st.session_state:
    st.session_state.lead_firm = ""

if not st.session_state.analysis_unlocked:
    st.subheader("Get your analysis")
    with st.form("lead_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("Your email *", placeholder="jane@yourfirm.com")
        with col2:
            firm = st.text_input("Firm name", placeholder="Smith & Associates")
        st.caption(
            "We'll email you the analysis as a PDF and follow up with one short message about how we'd "
            "build this as an always-on agent for your firm. No newsletter. No spam."
        )
        submitted = st.form_submit_button("Continue →")
        if submitted:
            if not is_valid_email(email):
                st.error("Please enter a valid email address.")
            else:
                st.session_state.lead_email = email
                st.session_state.lead_firm = firm
                st.session_state.analysis_unlocked = True
                st.rerun()

if st.session_state.analysis_unlocked:
    st.success(f"✓ Unlocked for **{st.session_state.lead_email}**")
    st.subheader("Paste your transcript")
    st.markdown(
        '<p class="small-print">'
        "⚠️ <strong>Redact client identifying details before pasting</strong> "
        "(names, case numbers, specific facts that could identify the matter). "
        "Your transcript is sent to Anthropic's Claude API for analysis and is not stored on our servers."
        "</p>",
        unsafe_allow_html=True,
    )
    transcript = st.text_area(
        "Transcript",
        height=300,
        placeholder="Speaker A 00:00:01\nThanks for hopping on. Tell me a little about what's going on...\n\nSpeaker B 00:00:15\nSure, so we've been dealing with...",
        label_visibility="collapsed",
    )

    if st.button("Analyze my call", type="primary", use_container_width=True):
        if len(transcript.strip()) < 200:
            st.error("Transcript looks too short. Paste at least a few minutes of dialogue.")
        elif not rate_limit_check(st.session_state.lead_email):
            st.warning(
                "You've already run one analysis in the last 24 hours. "
                "Want unlimited analyses for your firm? "
                f"[Book a call →]({CALENDLY_URL})"
            )
        else:
            log_lead(st.session_state.lead_email, st.session_state.lead_firm, len(transcript))
            mark_used(st.session_state.lead_email)
            with st.spinner("Reading the transcript... (60 seconds)"):
                result = analyze_transcript(transcript)
            st.markdown("---")
            st.markdown("## Your Post-Mortem")
            st.markdown(result)
            st.markdown("---")

            # CTA
            st.markdown(
                f"""
<div class="cta-box">
<h3 style="color:white; margin-top:0;">Want this as an always-on agent for your firm?</h3>
<p>We build it for solo and small law firms in 3 weeks. $2,500.<br>
Your transcripts come in, your coach output goes out, your team learns the framework.</p>
<a href="{CALENDLY_URL}" target="_blank">Book a discovery call →</a>
</div>
                """,
                unsafe_allow_html=True,
            )

# Footer
st.markdown("---")
st.markdown(
    '<p class="small-print">'
    "Built by <a href='https://helloparalegal.com'>Hello Paralegal</a> · "
    "AI workflows for solo and small law firms · "
    "Operated by Gavel Speaks Inc."
    "</p>",
    unsafe_allow_html=True,
)
