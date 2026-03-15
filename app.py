import streamlit as st
import anthropic
import textstat
import re
import time
import math
from collections import Counter
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

# ── NLTK downloads (silent) ────────────────────────────────────────────────
import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

for pkg in ["punkt", "punkt_tab", "stopwords", "averaged_perceptron_tagger"]:
    try:
        nltk.download(pkg, quiet=True)
    except Exception:
        pass

# ── PAGE CONFIG ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HumanizeAI · NYZTrade",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CUSTOM CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

/* ── Root Variables ─────────────────────────────────── */
:root {
  --ink:       #1a1a2e;
  --paper:     #f5f0e8;
  --cream:     #faf7f2;
  --gold:      #c9a84c;
  --gold-lt:   #e8d5a3;
  --rust:      #b5451b;
  --sage:      #4a7c59;
  --slate:     #5a6a7a;
  --border:    #d4c9b5;
  --shadow:    rgba(26,26,46,0.10);
}

/* ── Global ─────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: 'DM Sans', sans-serif;
  background-color: var(--cream) !important;
  color: var(--ink);
}

/* ── Hide Streamlit chrome ───────────────────────────── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; max-width: 1400px !important; }

/* ── Header banner ───────────────────────────────────── */
.hero-banner {
  background: linear-gradient(135deg, var(--ink) 0%, #2d2d4e 60%, #1a3a2e 100%);
  border-radius: 16px;
  padding: 2rem 2.5rem 1.6rem;
  margin-bottom: 1.8rem;
  position: relative;
  overflow: hidden;
}
.hero-banner::before {
  content: '';
  position: absolute; inset: 0;
  background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23c9a84c' fill-opacity='0.04'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
  opacity: 0.6;
}
.hero-title {
  font-family: 'Playfair Display', serif;
  font-size: 2.4rem;
  font-weight: 900;
  color: var(--gold);
  margin: 0 0 0.3rem;
  letter-spacing: -0.5px;
  position: relative;
}
.hero-sub {
  font-family: 'DM Sans', sans-serif;
  font-size: 0.95rem;
  color: rgba(255,255,255,0.65);
  margin: 0;
  font-weight: 300;
  position: relative;
}
.hero-badge {
  position: absolute;
  top: 1.5rem; right: 2rem;
  background: rgba(201,168,76,0.15);
  border: 1px solid rgba(201,168,76,0.4);
  color: var(--gold);
  border-radius: 20px;
  padding: 0.3rem 0.9rem;
  font-size: 0.78rem;
  font-family: 'DM Mono', monospace;
  letter-spacing: 1px;
  text-transform: uppercase;
}

/* ── Cards ───────────────────────────────────────────── */
.card {
  background: white;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.4rem 1.6rem;
  margin-bottom: 1rem;
  box-shadow: 0 2px 12px var(--shadow);
}
.card-title {
  font-family: 'Playfair Display', serif;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 0.8rem;
  padding-bottom: 0.6rem;
  border-bottom: 2px solid var(--gold-lt);
}

/* ── Score rings ─────────────────────────────────────── */
.score-ring-wrap {
  display: flex; flex-direction: column; align-items: center; gap: 0.3rem;
}
.score-ring {
  width: 90px; height: 90px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-family: 'Playfair Display', serif;
  font-size: 1.6rem;
  font-weight: 900;
  position: relative;
}
.score-label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--slate);
  text-align: center;
}

/* ── Metric chips ────────────────────────────────────── */
.metric-row { display: flex; flex-wrap: wrap; gap: 0.7rem; margin-top: 0.5rem; }
.metric-chip {
  background: var(--cream);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.45rem 0.9rem;
  font-size: 0.82rem;
  color: var(--slate);
}
.metric-chip b { color: var(--ink); font-weight: 600; }

/* ── Diff highlight ──────────────────────────────────── */
.diff-improved { background: #e8f5e9; border-radius: 3px; padding: 1px 2px; }
.diff-changed  { background: #fff8e1; border-radius: 3px; padding: 1px 2px; }

/* ── Style selector buttons ──────────────────────────── */
div[data-testid="stRadio"] > div { gap: 0.5rem !important; }
div[data-testid="stRadio"] label {
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  padding: 0.4rem 0.9rem !important;
  cursor: pointer !important;
  transition: all 0.2s !important;
  background: white !important;
}
div[data-testid="stRadio"] label:hover {
  border-color: var(--gold) !important;
  background: var(--cream) !important;
}

/* ── Text areas ───────────────────────────────────────── */
textarea {
  font-family: 'DM Sans', sans-serif !important;
  font-size: 0.9rem !important;
  line-height: 1.65 !important;
  border-radius: 10px !important;
  border: 1.5px solid var(--border) !important;
  background: white !important;
}
textarea:focus { border-color: var(--gold) !important; box-shadow: 0 0 0 3px rgba(201,168,76,0.15) !important; }

/* ── Primary button ──────────────────────────────────── */
div[data-testid="stButton"] > button[kind="primary"] {
  background: linear-gradient(135deg, var(--ink), #2d2d4e) !important;
  color: var(--gold) !important;
  border: 1.5px solid var(--gold) !important;
  border-radius: 10px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 600 !important;
  font-size: 1rem !important;
  padding: 0.65rem 2rem !important;
  letter-spacing: 0.3px !important;
  transition: all 0.25s !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 20px rgba(26,26,46,0.3) !important;
}

/* ── Sidebar ──────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--ink) !important;
  border-right: 1px solid rgba(201,168,76,0.2) !important;
}
[data-testid="stSidebar"] * { color: rgba(255,255,255,0.85) !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stRadio label { color: rgba(255,255,255,0.7) !important; font-size: 0.85rem !important; }
[data-testid="stSidebar"] h3 {
  color: var(--gold) !important;
  font-family: 'Playfair Display', serif !important;
  font-size: 1.1rem !important;
}

/* ── Progress bar ────────────────────────────────────── */
div[data-testid="stProgress"] > div > div {
  background: linear-gradient(90deg, var(--gold), var(--rust)) !important;
  border-radius: 4px !important;
}

/* ── Divider ─────────────────────────────────────────── */
hr { border: none; border-top: 1.5px solid var(--border); margin: 1.2rem 0; }

/* ── Comparison arrow ────────────────────────────────── */
.compare-arrow {
  display: flex; align-items: center; justify-content: center;
  font-size: 2rem; color: var(--gold); padding: 0.5rem;
}

/* ── Word count badge ────────────────────────────────── */
.wc-badge {
  display: inline-block;
  background: var(--cream);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.2rem 0.6rem;
  font-family: 'DM Mono', monospace;
  font-size: 0.78rem;
  color: var(--slate);
  margin-top: 0.3rem;
}

/* ── Improvement banner ──────────────────────────────── */
.improvement-banner {
  background: linear-gradient(135deg, #1a3a2e, #2d4a1e);
  border: 1px solid rgba(74,124,89,0.5);
  border-radius: 12px;
  padding: 1rem 1.5rem;
  display: flex; align-items: center; gap: 1rem;
  margin: 1rem 0;
}
.improvement-banner .score-delta {
  font-family: 'Playfair Display', serif;
  font-size: 2rem;
  font-weight: 900;
  color: #6fcf97;
  white-space: nowrap;
}
.improvement-banner .score-desc {
  font-size: 0.88rem;
  color: rgba(255,255,255,0.8);
  line-height: 1.5;
}
</style>
""", unsafe_allow_html=True)

# ── SCORING ENGINE ─────────────────────────────────────────────────────────

def compute_scores(text: str) -> dict:
    """Compute a rich set of linguistic humanness metrics."""
    if not text or not text.strip():
        return {}

    try:
        sentences = sent_tokenize(text)
        words = word_tokenize(text.lower())
        words_alpha = [w for w in words if w.isalpha()]
        stop_words = set(stopwords.words("english"))
        content_words = [w for w in words_alpha if w not in stop_words]
    except Exception:
        sentences = text.split('. ')
        words_alpha = re.findall(r'\b[a-z]+\b', text.lower())
        content_words = words_alpha
        stop_words = set()

    word_count = len(words_alpha)
    sent_count = max(len(sentences), 1)

    # ── Flesch Reading Ease (0-100, higher = easier/more human) ──
    try:
        flesch = textstat.flesch_reading_ease(text)
        flesch = max(0, min(100, flesch))
    except Exception:
        flesch = 50.0

    # ── Lexical Diversity (TTR) ────────────────────────────────
    unique_words = set(words_alpha)
    ttr = (len(unique_words) / word_count * 100) if word_count > 0 else 0

    # ── Sentence Length Variation (std dev) ───────────────────
    sent_lengths = [len(word_tokenize(s)) for s in sentences]
    if len(sent_lengths) > 1:
        mean_sl = sum(sent_lengths) / len(sent_lengths)
        variance = sum((l - mean_sl) ** 2 for l in sent_lengths) / len(sent_lengths)
        sl_variation = min(100, math.sqrt(variance) * 5)
    else:
        sl_variation = 0.0

    # ── Avg sentence length ────────────────────────────────────
    avg_sent_len = word_count / sent_count

    # ── Burstiness (human writers vary rhythm more) ───────────
    if len(sent_lengths) > 2:
        diffs = [abs(sent_lengths[i] - sent_lengths[i-1]) for i in range(1, len(sent_lengths))]
        burstiness = min(100, (sum(diffs) / len(diffs)) * 4)
    else:
        burstiness = 0.0

    # ── Contraction ratio ──────────────────────────────────────
    contractions = len(re.findall(
        r"\b(i'm|you're|he's|she's|it's|we're|they're|i've|you've|we've|they've|"
        r"i'd|you'd|he'd|she'd|we'd|they'd|i'll|you'll|he'll|she'll|we'll|they'll|"
        r"isn't|aren't|wasn't|weren't|don't|doesn't|didn't|won't|wouldn't|can't|"
        r"couldn't|shouldn't|haven't|hasn't|hadn't|that's|there's|here's|let's)\b",
        text.lower()
    ))
    contraction_score = min(100, (contractions / max(sent_count, 1)) * 40)

    # ── First-person pronouns (humanising signal) ──────────────
    first_person = len(re.findall(r'\b(i|me|my|myself|we|our|us)\b', text.lower()))
    fp_score = min(100, (first_person / max(word_count, 1)) * 500)

    # ── Passive voice penalty ──────────────────────────────────
    passive_count = len(re.findall(
        r'\b(is|are|was|were|be|been|being)\s+\w+ed\b', text.lower()
    ))
    passive_ratio = passive_count / max(sent_count, 1)
    passive_score = max(0, 100 - passive_ratio * 60)

    # ── Transition / discourse markers ────────────────────────
    transition_words = [
        'however', 'therefore', 'moreover', 'furthermore', 'although',
        'despite', 'meanwhile', 'consequently', 'additionally', 'nevertheless',
        'on the other hand', 'in contrast', 'for instance', 'in other words',
        'as a result', 'similarly', 'in fact', 'of course', 'after all'
    ]
    transitions = sum(1 for t in transition_words if t in text.lower())
    transition_score = min(100, transitions * 8)

    # ── Readability grade ──────────────────────────────────────
    try:
        grade = textstat.flesch_kincaid_grade(text)
    except Exception:
        grade = 10.0

    # ── Composite "Humanness Score" ────────────────────────────
    # Weights tuned for natural writing feel
    humanness = (
        flesch           * 0.20 +
        ttr              * 0.18 +
        sl_variation     * 0.15 +
        burstiness       * 0.12 +
        contraction_score* 0.10 +
        fp_score         * 0.08 +
        passive_score    * 0.10 +
        transition_score * 0.07
    )
    humanness = round(min(100, max(0, humanness)), 1)

    return {
        "humanness":        humanness,
        "flesch":           round(flesch, 1),
        "ttr":              round(ttr, 1),
        "sl_variation":     round(sl_variation, 1),
        "burstiness":       round(burstiness, 1),
        "contraction_score":round(contraction_score, 1),
        "passive_score":    round(passive_score, 1),
        "transition_score": round(transition_score, 1),
        "word_count":       word_count,
        "sent_count":       sent_count,
        "avg_sent_len":     round(avg_sent_len, 1),
        "grade_level":      round(grade, 1),
        "unique_words":     len(unique_words),
    }


def score_color(score: float) -> tuple:
    """Return (bg_color, text_color, label) for a score 0-100."""
    if score >= 75:
        return ("#1a3a2e", "#6fcf97", "Excellent")
    elif score >= 55:
        return ("#2d3a1e", "#b5d97a", "Good")
    elif score >= 35:
        return ("#3a2d1a", "#e8c97a", "Fair")
    else:
        return ("#3a1a1a", "#e87a7a", "Needs Work")


def render_score_ring(score: float, label: str) -> str:
    bg, fg, grade_lbl = score_color(score)
    return f"""
    <div class="score-ring-wrap">
      <div class="score-ring" style="background:{bg}; color:{fg};
           box-shadow: 0 0 0 3px {fg}30, 0 4px 16px rgba(0,0,0,0.2);">
        {score:.0f}
      </div>
      <div class="score-label">{label}</div>
      <div class="score-label" style="color:{fg}; font-size:0.68rem;">{grade_lbl}</div>
    </div>"""


def render_metrics(sc: dict) -> str:
    chips = [
        ("Words",      sc.get("word_count", 0)),
        ("Sentences",  sc.get("sent_count", 0)),
        ("Avg Sent Len", sc.get("avg_sent_len", 0)),
        ("Grade Level", sc.get("grade_level", 0)),
        ("Unique Words", sc.get("unique_words", 0)),
        ("Flesch Ease", sc.get("flesch", 0)),
        ("Lexical Div%", sc.get("ttr", 0)),
        ("Rhythm Var",  sc.get("sl_variation", 0)),
    ]
    html = '<div class="metric-row">'
    for name, val in chips:
        html += f'<div class="metric-chip"><b>{val}</b> {name}</div>'
    html += "</div>"
    return html


# ── HUMANIZATION ENGINE ────────────────────────────────────────────────────

STYLE_PROMPTS = {
    "Academic": (
        "You are an expert academic editor. Rewrite the following text to sound like it was written "
        "by a thoughtful, experienced scholar. Use varied sentence structures, precise vocabulary, "
        "appropriate hedging language, and natural academic discourse markers. Avoid robotic repetition, "
        "overly uniform sentence lengths, and AI-style list-heavy formatting. Maintain the original meaning exactly."
    ),
    "Conversational": (
        "You are a skilled writer who specialises in warm, engaging conversational prose. Rewrite the "
        "following text as if a knowledgeable friend is explaining it naturally — include occasional "
        "contractions, rhetorical questions, varied rhythm, and a genuine personal voice. Keep all key "
        "facts intact but make it feel truly human and approachable."
    ),
    "Professional": (
        "You are a senior business writer. Rewrite the following text with the polished clarity of "
        "a seasoned professional — concise yet nuanced, authoritative but not stiff. Use active voice "
        "where possible, vary sentence cadence, and ensure it reads as if written by a confident human "
        "expert rather than a machine. Preserve every key idea."
    ),
    "Journalistic": (
        "You are an experienced journalist from a top-tier publication. Rewrite the text using journalistic "
        "craft — punchy lead sentences, vivid specific detail, varied paragraph lengths, active voice, "
        "and a compelling narrative thread. Make it read as if published in a quality magazine. Keep all facts."
    ),
    "Creative / Expressive": (
        "You are a creative writer with a distinctive literary voice. Rewrite the following text with "
        "expressive flair — use metaphor, rhythm, sensory detail, and stylistic variety to make the prose "
        "genuinely engaging and human. Preserve all the original ideas but elevate the writing artistically."
    ),
}

INTENSITY_INSTRUCTIONS = {
    "Light": "Make subtle improvements — fix robotic phrasing and uniformity, but keep the structure largely intact.",
    "Moderate": "Substantially rewrite for naturalness — restructure sentences, vary rhythm, enrich vocabulary.",
    "Deep": "Completely transform the writing. Vary structure radically, add human discourse markers, inject personality while preserving all meaning.",
}


def chunk_text(text: str, max_words: int = 800) -> list[str]:
    """Split text into paragraph-aware chunks for API processing."""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks, current, current_wc = [], [], 0

    for para in paragraphs:
        wc = len(para.split())
        if current_wc + wc > max_words and current:
            chunks.append('\n\n'.join(current))
            current, current_wc = [para], wc
        else:
            current.append(para)
            current_wc += wc

    if current:
        chunks.append('\n\n'.join(current))

    return chunks if chunks else [text]


def humanize_chunk(client: anthropic.Anthropic, chunk: str, style: str, intensity: str) -> str:
    system_prompt = STYLE_PROMPTS[style]
    intensity_note = INTENSITY_INSTRUCTIONS[intensity]

    user_prompt = f"""{intensity_note}

IMPORTANT RULES:
- Preserve 100% of the original meaning and all factual content
- Do NOT add new information or remove key points
- Do NOT use bullet points or numbered lists unless the original had them
- Output ONLY the rewritten text, no preamble or commentary
- Aim for natural variation in sentence structure and length
- Use active voice where appropriate
- Include natural discourse markers and transitions

TEXT TO REWRITE:
\"\"\"
{chunk}
\"\"\"
"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )
    return message.content[0].text.strip()


# ── SIDEBAR ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ✍️ HumanizeAI")
    st.markdown("*NYZTrade Analytics · Text Intelligence*")
    st.markdown("---")

    st.markdown("### ⚙️ Writing Style")
    style = st.selectbox(
        "Target style",
        list(STYLE_PROMPTS.keys()),
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("### 🔧 Rewrite Intensity")
    intensity = st.radio(
        "Intensity",
        ["Light", "Moderate", "Deep"],
        index=1,
        label_visibility="collapsed",
    )

    st.markdown("### 🔑 API Key")
    api_key_input = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        label_visibility="collapsed",
        help="Your Anthropic API key. Never stored.",
    )

    st.markdown("---")
    st.markdown("""
    <div style="font-size:0.75rem; color:rgba(255,255,255,0.4); line-height:1.6;">
    <b style="color:rgba(255,255,255,0.6);">Scoring Dimensions</b><br>
    • Flesch Reading Ease<br>
    • Lexical Diversity (TTR)<br>
    • Sentence Rhythm Variation<br>
    • Burstiness Index<br>
    • Passive Voice Ratio<br>
    • Contraction Naturalness<br>
    • Discourse Transitions<br>
    • First-Person Voice
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div style="font-size:0.72rem; color:rgba(255,255,255,0.3);">
    Processes 5000+ words in parallel chunks.<br>
    All processing via Anthropic API.
    </div>
    """, unsafe_allow_html=True)


# ── HERO BANNER ────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero-banner">
  <div class="hero-badge">v2.0 · NYZTrade</div>
  <div class="hero-title">HumanizeAI</div>
  <div class="hero-sub">Transform AI-generated text into natural, expressive human writing — with intelligent scoring</div>
</div>
""", unsafe_allow_html=True)


# ── MAIN LAYOUT ────────────────────────────────────────────────────────────

col_in, col_out = st.columns([1, 1], gap="large")

with col_in:
    st.markdown('<div class="card-title">📄 Input Text</div>', unsafe_allow_html=True)

    input_text = st.text_area(
        label="Input",
        height=380,
        placeholder="Paste your AI-generated text here (5000+ words supported)…",
        label_visibility="collapsed",
        key="input_text",
    )

    wc_in = len(input_text.split()) if input_text.strip() else 0
    sc_in = len(re.split(r'[.!?]+', input_text)) if input_text.strip() else 0
    st.markdown(
        f'<span class="wc-badge">📝 {wc_in:,} words · {sc_in} sentences</span>',
        unsafe_allow_html=True,
    )

    if input_text.strip():
        scores_in = compute_scores(input_text)
        st.markdown("**Before — Humanness Analysis**")

        r1, r2, r3, r4 = st.columns(4)
        with r1: st.markdown(render_score_ring(scores_in["humanness"], "Humanness"), unsafe_allow_html=True)
        with r2: st.markdown(render_score_ring(scores_in["flesch"], "Readability"), unsafe_allow_html=True)
        with r3: st.markdown(render_score_ring(scores_in["ttr"], "Lexical Div"), unsafe_allow_html=True)
        with r4: st.markdown(render_score_ring(scores_in["sl_variation"], "Rhythm Var"), unsafe_allow_html=True)

        st.markdown(render_metrics(scores_in), unsafe_allow_html=True)
    else:
        scores_in = {}

with col_out:
    st.markdown('<div class="card-title">✨ Humanized Output</div>', unsafe_allow_html=True)

    output_placeholder = st.empty()

    if "output_text" not in st.session_state:
        st.session_state.output_text = ""

    output_text = st.session_state.output_text

    output_placeholder.text_area(
        label="Output",
        value=output_text,
        height=380,
        label_visibility="collapsed",
        key="output_display",
    )

    if output_text.strip():
        scores_out = compute_scores(output_text)
        wc_out = scores_out.get("word_count", 0)
        sc_out = scores_out.get("sent_count", 0)
        st.markdown(
            f'<span class="wc-badge">📝 {wc_out:,} words · {sc_out} sentences</span>',
            unsafe_allow_html=True,
        )

        st.markdown("**After — Humanness Analysis**")

        r1, r2, r3, r4 = st.columns(4)
        with r1: st.markdown(render_score_ring(scores_out["humanness"], "Humanness"), unsafe_allow_html=True)
        with r2: st.markdown(render_score_ring(scores_out["flesch"], "Readability"), unsafe_allow_html=True)
        with r3: st.markdown(render_score_ring(scores_out["ttr"], "Lexical Div"), unsafe_allow_html=True)
        with r4: st.markdown(render_score_ring(scores_out["sl_variation"], "Rhythm Var"), unsafe_allow_html=True)

        st.markdown(render_metrics(scores_out), unsafe_allow_html=True)
    else:
        scores_out = {}


# ── ACTION ROW ─────────────────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)
btn_col, info_col = st.columns([2, 3])

with btn_col:
    run_btn = st.button(
        "✦ Humanize Text",
        type="primary",
        use_container_width=True,
        disabled=(not input_text.strip()),
    )

with info_col:
    if not api_key_input:
        st.info("🔑 Add your Anthropic API key in the sidebar to begin.")
    elif not input_text.strip():
        st.info("📄 Paste your text in the input panel above.")
    else:
        chunks = chunk_text(input_text)
        st.markdown(
            f'<div class="wc-badge">🔀 Will process in {len(chunks)} chunk{"s" if len(chunks)>1 else ""} '
            f'· Style: {style} · Intensity: {intensity}</div>',
            unsafe_allow_html=True,
        )


# ── PROCESSING LOGIC ───────────────────────────────────────────────────────

if run_btn:
    if not api_key_input:
        st.error("Please enter your Anthropic API key in the sidebar.")
    elif not input_text.strip():
        st.error("Please enter some text to humanize.")
    else:
        try:
            client = anthropic.Anthropic(api_key=api_key_input)
            chunks = chunk_text(input_text)
            n = len(chunks)

            progress_bar = st.progress(0, text="Initialising…")
            status_box = st.empty()

            results = []
            for i, chunk in enumerate(chunks):
                status_box.markdown(
                    f'<div class="wc-badge">⚡ Processing chunk {i+1} of {n} '
                    f'({len(chunk.split())} words)…</div>',
                    unsafe_allow_html=True,
                )
                humanized = humanize_chunk(client, chunk, style, intensity)
                results.append(humanized)
                progress_bar.progress((i + 1) / n, text=f"Chunk {i+1}/{n} complete")
                time.sleep(0.1)

            progress_bar.progress(1.0, text="✓ Complete!")
            status_box.empty()

            st.session_state.output_text = "\n\n".join(results)
            st.rerun()

        except anthropic.AuthenticationError:
            st.error("❌ Invalid API key. Please check your Anthropic API key.")
        except anthropic.RateLimitError:
            st.error("⚠️ Rate limit hit. Please wait a moment and try again.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")


# ── COMPARISON PANEL ───────────────────────────────────────────────────────

if scores_in and scores_out:
    st.markdown("---")
    st.markdown(
        '<div class="card-title" style="font-size:1.15rem;">📊 Before vs After — Full Comparison</div>',
        unsafe_allow_html=True,
    )

    delta = scores_out["humanness"] - scores_in["humanness"]
    delta_sign = "+" if delta >= 0 else ""
    delta_color = "#6fcf97" if delta >= 0 else "#e87a7a"

    st.markdown(f"""
    <div class="improvement-banner">
      <div class="score-delta" style="color:{delta_color};">{delta_sign}{delta:.1f}</div>
      <div class="score-desc">
        <b>Humanness Score Change</b><br>
        Before: <b>{scores_in['humanness']}</b> → After: <b>{scores_out['humanness']}</b><br>
        {style} style · {intensity} intensity rewrite
      </div>
    </div>
    """, unsafe_allow_html=True)

    metrics_to_compare = [
        ("Humanness Score",    "humanness",         "Higher = more natural"),
        ("Flesch Readability", "flesch",             "Higher = easier to read"),
        ("Lexical Diversity",  "ttr",                "Higher = richer vocabulary"),
        ("Rhythm Variation",   "sl_variation",       "Higher = more varied sentences"),
        ("Burstiness",         "burstiness",         "Higher = more human rhythm"),
        ("Passive Voice Score","passive_score",      "Higher = more active voice"),
        ("Transition Score",   "transition_score",   "Higher = better flow"),
        ("Grade Level",        "grade_level",        "Lower = more accessible"),
    ]

    c1, c2, c3, c4 = st.columns(4)
    cols = [c1, c2, c3, c4]
    for idx, (label, key, hint) in enumerate(metrics_to_compare):
        v_before = scores_in.get(key, 0)
        v_after  = scores_out.get(key, 0)
        d = v_after - v_before
        sign = "+" if d >= 0 else ""
        col_d = "#6fcf97" if d >= 0 else "#e87a7a"
        if key == "grade_level":
            col_d = "#6fcf97" if d <= 0 else "#e87a7a"

        with cols[idx % 4]:
            st.markdown(f"""
            <div style="background:white; border:1px solid #d4c9b5; border-radius:10px;
                        padding:0.9rem; margin-bottom:0.8rem; text-align:center;">
              <div style="font-size:0.72rem; color:#5a6a7a; text-transform:uppercase;
                          letter-spacing:0.8px; margin-bottom:0.5rem;">{label}</div>
              <div style="display:flex; justify-content:space-around; align-items:center;">
                <div style="text-align:center;">
                  <div style="font-size:1.3rem; font-weight:700; color:#1a1a2e;">{v_before}</div>
                  <div style="font-size:0.68rem; color:#9a8a7a;">Before</div>
                </div>
                <div style="font-size:1.4rem; color:#c9a84c;">→</div>
                <div style="text-align:center;">
                  <div style="font-size:1.3rem; font-weight:700; color:#1a1a2e;">{v_after}</div>
                  <div style="font-size:0.68rem; color:#9a8a7a;">After</div>
                </div>
              </div>
              <div style="font-size:0.82rem; font-weight:700; color:{col_d}; margin-top:0.4rem;">
                {sign}{d:.1f}
              </div>
              <div style="font-size:0.67rem; color:#9a8a7a; margin-top:0.2rem;">{hint}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Copy output button ─────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    dl_col, _, _ = st.columns([1, 1, 1])
    with dl_col:
        st.download_button(
            label="⬇️  Download Humanized Text",
            data=st.session_state.output_text,
            file_name="humanized_output.txt",
            mime="text/plain",
            use_container_width=True,
        )
