import streamlit as st
import streamlit.components.v1 as components
import requests
import re
import time
import math
from collections import Counter

# ── ZERO-DEPENDENCY READABILITY ENGINE ────────────────────────────────────

def _count_syllables(word: str) -> int:
    word = word.lower().strip(".,!?;:'\"()")
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    word = re.sub(r'(?:[^laeiouy]es|ed|[^laeiouy]e)$', '', word)
    word = re.sub(r'^y', '', word)
    count = len(re.findall(r'[aeiouy]{1,2}', word))
    return max(1, count)

def _flesch_reading_ease(text: str) -> float:
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    words = re.findall(r'\b[a-zA-Z]+\b', text)
    if not sentences or not words:
        return 50.0
    syllables = sum(_count_syllables(w) for w in words)
    asl = len(words) / len(sentences)
    asw = syllables / len(words)
    score = 206.835 - 1.015 * asl - 84.6 * asw
    return round(max(0.0, min(100.0, score)), 1)

def _flesch_kincaid_grade(text: str) -> float:
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    words = re.findall(r'\b[a-zA-Z]+\b', text)
    if not sentences or not words:
        return 10.0
    syllables = sum(_count_syllables(w) for w in words)
    asl = len(words) / len(sentences)
    asw = syllables / len(words)
    grade = 0.39 * asl + 11.8 * asw - 15.59
    return round(max(0.0, grade), 1)

def _sent_tokenize(text: str) -> list:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p.strip()] or [text]

def _word_tokenize(text: str) -> list:
    return re.findall(r'\b[a-zA-Z]+\b', text.lower())

_STOPWORDS = {
    "a","an","the","and","but","or","for","nor","so","yet","at","by","in",
    "of","on","to","up","as","is","it","its","be","was","are","were","been",
    "has","have","had","do","does","did","will","would","could","should",
    "may","might","shall","can","need","dare","ought","used","that","this",
    "these","those","i","me","my","we","our","us","you","your","he","him",
    "his","she","her","they","them","their","what","which","who","whom",
    "when","where","why","how","all","both","each","few","more","most",
    "other","some","such","no","not","only","same","than","too","very",
    "just","with","from","into","through","during","before","after","above",
    "below","between","out","off","over","under","again","then","once",
    "here","there","about","if","because","while","although","though",
    "since","until","unless","however","therefore","also","even","still",
    "already","now"
}

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

:root {
  --ink:    #1a1a2e;
  --cream:  #faf7f2;
  --gold:   #c9a84c;
  --gold-lt:#e8d5a3;
  --rust:   #b5451b;
  --slate:  #5a6a7a;
  --border: #d4c9b5;
  --shadow: rgba(26,26,46,0.10);
}

html, body, [class*="css"] {
  font-family: 'DM Sans', sans-serif;
  background-color: var(--cream) !important;
  color: var(--ink);
}

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; max-width: 1400px !important; }

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
  opacity:0.6;
}
.hero-title {
  font-family: 'Playfair Display', serif;
  font-size: 2.4rem; font-weight: 900;
  color: var(--gold); margin: 0 0 0.3rem;
  letter-spacing: -0.5px; position: relative;
}
.hero-sub {
  font-size: 0.95rem; color: rgba(255,255,255,0.65);
  margin: 0; font-weight: 300; position: relative;
}
.hero-badge {
  position: absolute; top: 1.5rem; right: 2rem;
  background: rgba(201,168,76,0.15);
  border: 1px solid rgba(201,168,76,0.4);
  color: var(--gold); border-radius: 20px;
  padding: 0.3rem 0.9rem; font-size: 0.78rem;
  font-family: 'DM Mono', monospace;
  letter-spacing: 1px; text-transform: uppercase;
}

.card-title {
  font-family: 'Playfair Display', serif;
  font-size: 1.05rem; font-weight: 700;
  color: #c9a84c !important;
  margin-bottom: 0.8rem;
  padding-bottom: 0.6rem;
  border-bottom: 2px solid #c9a84c;
  text-shadow: 0 1px 3px rgba(0,0,0,0.3);
}

.score-ring-wrap { display:flex; flex-direction:column; align-items:center; gap:0.3rem; }
.score-ring {
  width:90px; height:90px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-family:'Playfair Display',serif; font-size:1.6rem; font-weight:900;
}
.score-label {
  font-size:0.72rem; font-weight:600;
  text-transform:uppercase; letter-spacing:1px;
  color:var(--slate); text-align:center;
}

.metric-row { display:flex; flex-wrap:wrap; gap:0.7rem; margin-top:0.5rem; }
.metric-chip {
  background:var(--cream); border:1px solid var(--border);
  border-radius:8px; padding:0.45rem 0.9rem;
  font-size:0.82rem; color:var(--slate);
}
.metric-chip b { color:var(--ink); font-weight:600; }

/* Radio buttons — cream bg so text always readable */
div[data-testid="stRadio"] > div { gap:0.4rem !important; }
div[data-testid="stRadio"] label {
  border:1px solid rgba(201,168,76,0.4) !important;
  border-radius:8px !important; padding:0.45rem 1rem !important;
  cursor:pointer !important; transition:all 0.2s !important;
  background:#f5f0e8 !important;
}
div[data-testid="stRadio"] label > div,
div[data-testid="stRadio"] label span,
div[data-testid="stRadio"] label p { color:#1a1a2e !important; font-weight:500 !important; }
div[data-testid="stRadio"] label:hover {
  border-color:var(--gold) !important; background:#ede8dc !important;
}

textarea {
  font-family:'DM Sans',sans-serif !important; font-size:0.9rem !important;
  line-height:1.65 !important; border-radius:10px !important;
  border:1.5px solid var(--border) !important;
  background:white !important; color:#1a1a2e !important;
}
textarea:focus {
  border-color:var(--gold) !important;
  box-shadow:0 0 0 3px rgba(201,168,76,0.15) !important;
}

div[data-testid="stButton"] > button[kind="primary"] {
  background:linear-gradient(135deg,var(--ink),#2d2d4e) !important;
  color:var(--gold) !important; border:1.5px solid var(--gold) !important;
  border-radius:10px !important; font-family:'DM Sans',sans-serif !important;
  font-weight:600 !important; font-size:1rem !important;
  padding:0.65rem 2rem !important; letter-spacing:0.3px !important;
  transition:all 0.25s !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
  transform:translateY(-2px) !important;
  box-shadow:0 6px 20px rgba(26,26,46,0.3) !important;
}

/* Sidebar */
[data-testid="stSidebar"] { background:var(--ink) !important; border-right:1px solid rgba(201,168,76,0.2) !important; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span:not([data-testid]),
[data-testid="stSidebar"] div.stMarkdown,
[data-testid="stSidebar"] .stMarkdown p { color:rgba(255,255,255,0.88) !important; }
[data-testid="stSidebar"] h3 { color:var(--gold) !important; font-family:'Playfair Display',serif !important; font-size:1.1rem !important; }
/* Selectbox */
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
  background:rgba(255,255,255,0.08) !important;
  border:1px solid rgba(201,168,76,0.4) !important;
  border-radius:8px !important; color:white !important;
}
/* API key input */
[data-testid="stSidebar"] input {
  background:rgba(255,255,255,0.08) !important; color:white !important;
  border:1px solid rgba(201,168,76,0.4) !important; border-radius:8px !important;
}
[data-testid="stSidebar"] input::placeholder { color:rgba(255,255,255,0.35) !important; }

div[data-testid="stProgress"] > div > div {
  background:linear-gradient(90deg,var(--gold),var(--rust)) !important;
  border-radius:4px !important;
}

hr { border:none; border-top:1.5px solid var(--border); margin:1.2rem 0; }

.wc-badge {
  display:inline-block; background:var(--cream); border:1px solid var(--border);
  border-radius:6px; padding:0.2rem 0.6rem;
  font-family:'DM Mono',monospace; font-size:0.78rem; color:var(--slate); margin-top:0.3rem;
}

.improvement-banner {
  background:linear-gradient(135deg,#1a3a2e,#2d4a1e);
  border:1px solid rgba(74,124,89,0.5); border-radius:12px;
  padding:1rem 1.5rem; display:flex; align-items:center; gap:1rem; margin:1rem 0;
}
.improvement-banner .score-delta { font-family:'Playfair Display',serif; font-size:2rem; font-weight:900; white-space:nowrap; }
.improvement-banner .score-desc { font-size:0.88rem; color:rgba(255,255,255,0.8); line-height:1.5; }

/* ── Force all main-column text to be visible (dark on light) ── */
.card-title { color: #c9a84c !important; }
.score-label { color: #5a6a7a !important; }
.wc-badge { color: #5a6a7a !important; background: #f5f0e8 !important; border-color: #d4c9b5 !important; }
.metric-chip { color: #5a6a7a !important; background: #f5f0e8 !important; }
.metric-chip b { color: #1a1a2e !important; }

/* Main content markdown text — must be dark */
section.main p,
section.main span,
section.main label,
section.main div:not([class*="sidebar"]) { color: #1a1a2e; }
section.main .stMarkdown p { color: #1a1a2e !important; }
section.main strong, section.main b { color: #1a1a2e !important; }

/* st.info / st.warning boxes */
div[data-testid="stAlert"] p { color: #1a1a2e !important; }

/* Comparison panel metric cards text */
.comparison-card-label { color: #5a6a7a !important; }
.comparison-card-val   { color: #1a1a2e !important; }

/* ── Layout containment — prevent output from leaking ── */
.output-box {
  background: white;
  border: 1.5px solid #c9a84c;
  border-radius: 10px;
  padding: 1.1rem 1.3rem;
  height: 400px;
  overflow-y: auto;
  overflow-x: hidden;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.9rem;
  line-height: 1.7;
  color: #1a1a2e;
  white-space: pre-wrap;
  word-break: break-word;
  box-sizing: border-box;
}
.output-box-para {
  background: white;
  border: 1.5px solid #c9a84c;
  border-radius: 10px;
  padding: 1.1rem 1.3rem;
  height: 340px;
  overflow-y: auto;
  overflow-x: hidden;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.9rem;
  line-height: 1.7;
  color: #1a1a2e;
  white-space: pre-wrap;
  word-break: break-word;
  box-sizing: border-box;
}
/* Force columns to not overflow their container */
[data-testid="column"] {
  overflow: hidden !important;
  min-width: 0 !important;
}
/* Comparison panel scores — prevent overflow */
[data-testid="stHorizontalBlock"] {
  flex-wrap: wrap !important;
}
</style>
""", unsafe_allow_html=True)

# ── SCORING ENGINE ─────────────────────────────────────────────────────────

def make_copy_btn(copy_id: str, text: str, label: str = "📋 Copy",
                  color: str = "#c9a84c", bg: str = "#1a1a2e", border: str = "#c9a84c") -> None:
    """Render a self-contained copy button via st.components — works inside Streamlit iframes."""
    import html as _html
    safe = _html.escape(text, quote=True)
    # This component renders in its OWN iframe so document.getElementById works perfectly.
    # The textarea lives in the same document as the button.
    html_src = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:transparent;">
<textarea id="cp" readonly style="position:absolute;left:-9999px;top:0;width:1px;height:1px;">{safe}</textarea>
<button id="btn"
  onclick="var el=document.getElementById('cp');
           el.select();el.setSelectionRange(0,99999);
           var ok=false;
           try{{ok=document.execCommand('copy');}}catch(e){{}}
           if(!ok && navigator.clipboard){{
             navigator.clipboard.writeText(el.value).then(function(){{
               document.getElementById('btn').innerHTML='✅ Copied!';
               setTimeout(function(){{document.getElementById('btn').innerHTML='{label}';}},2000);
             }});
           }} else {{
             document.getElementById('btn').innerHTML='✅ Copied!';
             setTimeout(function(){{document.getElementById('btn').innerHTML='{label}';}},2000);
           }}"
  style="background:{bg};color:{color};border:1.5px solid {border};
         border-radius:8px;padding:0.4rem 1.1rem;cursor:pointer;
         font-size:0.82rem;font-family:'DM Sans',sans-serif;
         font-weight:500;transition:all 0.2s;white-space:nowrap;">
  {label}
</button>
</body></html>"""
    components.html(html_src, height=46, scrolling=False)


def compute_scores(text: str) -> dict:
    if not text or not text.strip():
        return {}

    sentences  = _sent_tokenize(text)
    words_alpha = _word_tokenize(text)
    word_count  = len(words_alpha)
    sent_count  = max(len(sentences), 1)

    # Flesch Reading Ease
    flesch = _flesch_reading_ease(text)

    # Lexical Diversity (TTR)
    unique_words = set(words_alpha)
    ttr = (len(unique_words) / word_count * 100) if word_count > 0 else 0

    # Sentence Length Variation
    sent_lengths = [len(_word_tokenize(s)) for s in sentences]
    if len(sent_lengths) > 1:
        mean_sl   = sum(sent_lengths) / len(sent_lengths)
        variance  = sum((l - mean_sl) ** 2 for l in sent_lengths) / len(sent_lengths)
        sl_variation = min(100, math.sqrt(variance) * 5)
    else:
        sl_variation = 0.0

    avg_sent_len = word_count / sent_count

    # Burstiness
    if len(sent_lengths) > 2:
        diffs      = [abs(sent_lengths[i] - sent_lengths[i-1]) for i in range(1, len(sent_lengths))]
        burstiness = min(100, (sum(diffs) / len(diffs)) * 4)
    else:
        burstiness = 0.0

    # Contractions
    contractions = len(re.findall(
        r"\b(i'm|you're|he's|she's|it's|we're|they're|i've|you've|we've|they've|"
        r"i'd|you'd|he'd|she'd|we'd|they'd|i'll|you'll|he'll|she'll|we'll|they'll|"
        r"isn't|aren't|wasn't|weren't|don't|doesn't|didn't|won't|wouldn't|can't|"
        r"couldn't|shouldn't|haven't|hasn't|hadn't|that's|there's|here's|let's)\b",
        text.lower()
    ))
    contraction_score = min(100, (contractions / max(sent_count, 1)) * 40)

    # First-person
    first_person  = len(re.findall(r'\b(i|me|my|myself|we|our|us)\b', text.lower()))
    fp_score      = min(100, (first_person / max(word_count, 1)) * 500)

    # Passive voice
    passive_count = len(re.findall(r'\b(is|are|was|were|be|been|being)\s+\w+ed\b', text.lower()))
    passive_score = max(0, 100 - (passive_count / max(sent_count, 1)) * 60)

    # Transitions
    transition_words = [
        'however','therefore','moreover','furthermore','although',
        'despite','meanwhile','consequently','additionally','nevertheless',
        'on the other hand','in contrast','for instance','in other words',
        'as a result','similarly','in fact','of course','after all'
    ]
    transitions      = sum(1 for t in transition_words if t in text.lower())
    transition_score = min(100, transitions * 8)

    # Grade level
    grade = _flesch_kincaid_grade(text)

    # Composite humanness
    humanness = (
        flesch            * 0.20 +
        ttr               * 0.18 +
        sl_variation      * 0.15 +
        burstiness        * 0.12 +
        contraction_score * 0.10 +
        fp_score          * 0.08 +
        passive_score     * 0.10 +
        transition_score  * 0.07
    )
    humanness = round(min(100, max(0, humanness)), 1)

    return {
        "humanness":         humanness,
        "flesch":            round(flesch, 1),
        "ttr":               round(ttr, 1),
        "sl_variation":      round(sl_variation, 1),
        "burstiness":        round(burstiness, 1),
        "contraction_score": round(contraction_score, 1),
        "passive_score":     round(passive_score, 1),
        "transition_score":  round(transition_score, 1),
        "word_count":        word_count,
        "sent_count":        sent_count,
        "avg_sent_len":      round(avg_sent_len, 1),
        "grade_level":       round(grade, 1),
        "unique_words":      len(unique_words),
    }


def score_color(score: float) -> tuple:
    if score >= 75:   return ("#1a3a2e", "#6fcf97", "Excellent")
    elif score >= 55: return ("#2d3a1e", "#b5d97a", "Good")
    elif score >= 35: return ("#3a2d1a", "#e8c97a", "Fair")
    else:             return ("#3a1a1a", "#e87a7a", "Needs Work")


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
        ("Words",        sc.get("word_count", 0)),
        ("Sentences",    sc.get("sent_count", 0)),
        ("Avg Sent Len", sc.get("avg_sent_len", 0)),
        ("Grade Level",  sc.get("grade_level", 0)),
        ("Unique Words", sc.get("unique_words", 0)),
        ("Flesch Ease",  sc.get("flesch", 0)),
        ("Lexical Div%", sc.get("ttr", 0)),
        ("Rhythm Var",   sc.get("sl_variation", 0)),
    ]
    html = '<div class="metric-row">'
    for name, val in chips:
        html += f'<div class="metric-chip"><b>{val}</b> {name}</div>'
    html += "</div>"
    return html


# ── HUMANIZATION ENGINE ────────────────────────────────────────────────────

STYLE_PROMPTS = {
    "Academic": (
        "You are an expert academic editor with 20 years of experience. Your task is to rewrite the "
        "given text so it reads as if written by a real, thoughtful human scholar — NOT an AI. "
        "MANDATORY requirements for high humanness: "
        "(1) Vary sentence length dramatically — mix very short sentences (4-8 words) with long complex ones (25-40 words). "
        "(2) Use natural hedging: 'it appears that', 'the evidence suggests', 'one might argue'. "
        "(3) Add discourse connectors: 'That said,', 'Interestingly,', 'What is particularly striking here is'. "
        "(4) Occasionally use rhetorical questions to engage the reader. "
        "(5) Break ALL passive voice constructions into active voice. "
        "(6) Use 'we' and 'our' naturally where appropriate for academic writing. "
        "(7) Vary paragraph structure — some short (2 sentences), some longer. "
        "Preserve all original meaning and facts exactly."
    ),
    "Conversational": (
        "You are rewriting text to sound like a real human speaking naturally. "
        "MANDATORY requirements: "
        "(1) Use contractions throughout: it's, don't, they're, we've, can't, that's, it's been, we're. "
        "(2) Alternate sentence lengths wildly — some just 3-5 words, others 20-30 words. "
        "(3) Add personal asides: 'And honestly,', 'Here's the thing —', 'What's really interesting is'. "
        "(4) Use rhetorical questions: 'But why does this matter?', 'So what does this mean for us?'. "
        "(5) Use everyday vocabulary — replace formal words with simpler alternatives. "
        "(6) Use first-person 'I', 'we', 'you' naturally. "
        "(7) Add natural transition phrases: 'On top of that,', 'And yet,', 'At the end of the day'. "
        "Preserve all key facts and meaning."
    ),
    "Professional": (
        "You are a senior writer at a top consulting firm. Rewrite the text to sound like a confident, "
        "experienced human professional — authoritative yet natural, never robotic. "
        "MANDATORY requirements: "
        "(1) Mix short punchy sentences with longer analytical ones — never uniform length. "
        "(2) Use active voice for at least 85% of sentences. "
        "(3) Add professional transitions: 'That said,', 'More importantly,', 'This matters because'. "
        "(4) Use contractions where appropriate: it's, we've, doesn't, that's. "
        "(5) Use 'we' and 'our' to create a collaborative tone. "
        "(6) Begin some sentences with conjunctions for rhythm: 'And this is why...', 'But the challenge is'. "
        "(7) Vary paragraph length — punchy short paragraphs alongside fuller ones. "
        "Preserve every key idea and fact."
    ),
    "Journalistic": (
        "You are a senior writer at The Economist or The Atlantic. Rewrite using masterful journalistic craft. "
        "MANDATORY requirements: "
        "(1) Open with a short, punchy hook sentence (5-10 words maximum). "
        "(2) Vary sentence rhythm dramatically — short punchy sentences followed by long flowing ones. "
        "(3) Use specific, vivid details and concrete language. "
        "(4) Use active voice throughout. "
        "(5) Add journalist's transitions: 'The result?', 'Consider this:', 'Yet the picture is more complex.' "
        "(6) Use contractions: it's, that's, they're, we've. "
        "(7) Create narrative momentum — each sentence should pull the reader to the next. "
        "Keep all facts and key information."
    ),
    "Creative / Expressive": (
        "You are a celebrated literary writer. Transform this text into vivid, expressive prose. "
        "MANDATORY requirements: "
        "(1) Use striking sentence rhythm variation — very short sentences for impact, long flowing ones for depth. "
        "(2) Weave in metaphor, analogy, or sensory language naturally. "
        "(3) Use contractions and natural first-person voice. "
        "(4) Add emotional resonance: phrases that connect the ideas to human experience. "
        "(5) Use rhetorical devices: repetition for emphasis, questions for engagement. "
        "(6) Vary paragraph lengths — single-sentence paragraphs for punch, fuller ones for development. "
        "(7) Make transitions feel organic and conversational, not mechanical. "
        "Preserve all original meaning and ideas."
    ),
}

# ── Paraphraser prompts ───────────────────────────────────────────────────

PARAPHRASE_MODES = {
    "Standard": (
        "You are an expert paraphraser. Rewrite the following text using completely different "
        "words and sentence structures while preserving the exact original meaning. "
        "Output ONLY the paraphrased text with no commentary."
    ),
    "Simplify": (
        "You are a plain-language expert. Rewrite the following text in simpler, clearer language "
        "that anyone can understand. Use shorter sentences, common words, and active voice. "
        "Output ONLY the simplified text with no commentary."
    ),
    "Formal": (
        "You are a formal academic writer. Rewrite the following text in a highly formal, "
        "professional register using precise vocabulary and structured sentences. "
        "Output ONLY the formal text with no commentary."
    ),
    "Concise": (
        "You are an editor who specialises in conciseness. Rewrite the following text removing "
        "all redundancy, padding, and unnecessary words — make it as tight as possible "
        "while keeping every key idea. Output ONLY the concise text, no commentary."
    ),
    "Creative": (
        "You are a creative writer. Paraphrase the following text with vivid, expressive "
        "language — use fresh metaphors, varied rhythm, and engaging style. "
        "Preserve all meaning. Output ONLY the paraphrased text, no commentary."
    ),
}

# ── Grammar checker prompt ────────────────────────────────────────────────

GRAMMAR_SYSTEM = (
    "You are a professional copy-editor and grammar expert. "
    "Carefully proofread the following text and return a JSON response with exactly these keys:\n"
    "- \"corrected\": the fully corrected text\n"
    "- \"issues\": a list of objects each with keys \"original\", \"corrected\", \"type\", \"explanation\"\n"
    "Types: grammar, spelling, punctuation, style, wordiness, clarity\n"
    "Return ONLY valid JSON, nothing else."
)

INTENSITY_INSTRUCTIONS = {
    "Light": (
        "Lightly edit for naturalness. Fix the most robotic phrases and any sentences that are identical "
        "in length. Add 1-2 contractions and 1-2 transition phrases. Keep 80% of the original structure."
    ),
    "Moderate": (
        "Substantially rewrite for human naturalness. Restructure at least half the sentences. "
        "Vary sentence length so the shortest is under 8 words and longest is over 25 words. "
        "Add contractions, discourse markers, and active voice throughout. "
        "The result should feel like a thoughtful human writer, not an AI."
    ),
    "Deep": (
        "Completely transform this into natural, distinctly human writing. "
        "Every sentence must be restructured. Sentence lengths must vary dramatically. "
        "Use contractions freely. Add personality through transitions, rhetorical questions, and natural asides. "
        "Aggressively convert passive to active voice. "
        "The final text must score above 60 on Flesch Reading Ease and above 50 on humanness metrics. "
        "Preserve all meaning and facts — only the style and structure should change."
    ),
}


def chunk_text(text: str, max_words: int = 800) -> list:
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


def _build_prompt(style: str, intensity: str, chunk: str) -> tuple:
    system_prompt  = STYLE_PROMPTS[style]
    intensity_note = INTENSITY_INSTRUCTIONS[intensity]
    user_prompt = f"""{intensity_note}

CRITICAL RULES — follow these exactly:
1. Output ONLY the rewritten text — no preamble, no "Here is the rewritten text:", no commentary.
2. Preserve 100% of the original meaning, facts, and key points.
3. Do NOT add bullet points or numbered lists unless the original had them.
4. SENTENCE LENGTH VARIATION IS MANDATORY — your output must contain both very short sentences (under 8 words) AND long sentences (over 25 words). Uniform sentence length is a failure.
5. Use contractions naturally (it's, don't, we've, that's, they're, isn't, can't).
6. Use active voice for at least 80% of sentences.
7. Include at least 3 natural transition phrases (However, That said, What's more, Interestingly, As a result, In fact, Of course, And yet).
8. Do NOT start every sentence with "The" or with the same word pattern.

TEXT TO REWRITE:
\"\"\"
{chunk}
\"\"\"
"""
    return system_prompt, user_prompt


def humanize_chunk_ollama(ollama_url: str, model: str, chunk: str, style: str, intensity: str) -> str:
    system_prompt, user_prompt = _build_prompt(style, intensity, chunk)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": False,
        "options": {"num_predict": 2048},
    }
    resp = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def humanize_chunk_groq(api_key: str, model: str, chunk: str, style: str, intensity: str) -> str:
    system_prompt, user_prompt = _build_prompt(style, intensity, chunk)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": 2048,
        "temperature": 0.7,
    }
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers, json=payload, timeout=120
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def paraphrase_text(use_groq: bool, ollama_url: str, groq_key: str,
                    model: str, text: str, mode: str) -> str:
    system_prompt = PARAPHRASE_MODES[mode]
    user_msg = f"TEXT TO PARAPHRASE:\n\"\"\"\n{text}\n\"\"\""
    if use_groq:
        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
        payload = {"model": model,
                   "messages": [{"role":"system","content":system_prompt},
                                 {"role":"user","content":user_msg}],
                   "max_tokens": 2048, "temperature": 0.6}
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
                             headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    else:
        payload = {"model": model,
                   "messages": [{"role":"system","content":system_prompt},
                                 {"role":"user","content":user_msg}],
                   "stream": False, "options": {"num_predict": 2048}}
        resp = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()


def grammar_check(use_groq: bool, ollama_url: str, groq_key: str,
                  model: str, text: str) -> dict:
    import json
    user_msg = f"TEXT TO PROOFREAD:\n\"\"\"\n{text}\n\"\"\""
    if use_groq:
        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
        payload = {"model": model,
                   "messages": [{"role":"system","content":GRAMMAR_SYSTEM},
                                 {"role":"user","content":user_msg}],
                   "max_tokens": 3000, "temperature": 0.1}
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
                             headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
    else:
        payload = {"model": model,
                   "messages": [{"role":"system","content":GRAMMAR_SYSTEM},
                                 {"role":"user","content":user_msg}],
                   "stream": False, "options": {"num_predict": 3000}}
        resp = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=300)
        resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        return {"corrected": raw, "issues": []}


# ── SIDEBAR ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ✍️ HumanizeAI")
    st.markdown("*NYZTrade Analytics · Text Intelligence*")
    st.markdown("---")

    st.markdown("### ⚙️ Writing Style")
    style = st.selectbox("Target style", list(STYLE_PROMPTS.keys()), index=0, label_visibility="collapsed")

    st.markdown("### 🔧 Rewrite Intensity")
    intensity = st.radio("Intensity", ["Light", "Moderate", "Deep"], index=1, label_visibility="collapsed")

    # ── Backend selector ─────────────────────────────────
    st.markdown("### 🔌 Backend")
    backend = st.radio(
        "Backend", ["🦙 Ollama (Local)", "⚡ Groq (Cloud Free)"],
        index=0, label_visibility="collapsed",
    )

    st.markdown("---")

    if backend == "🦙 Ollama (Local)":
        st.markdown("### 🌐 Ollama URL")
        ollama_url = st.text_input(
            "Ollama URL", value="http://localhost:11434",
            label_visibility="collapsed",
            help="Default: http://localhost:11434",
        )
        groq_key = ""

        st.markdown("### 🤖 Model")
        available_models = []
        try:
            r = requests.get(f"{ollama_url}/api/tags", timeout=3)
            if r.status_code == 200:
                available_models = [m["name"] for m in r.json().get("models", [])]
        except Exception:
            pass

        OLLAMA_MODELS = ["llama3.2:latest", "llama3.1:latest", "llama3:latest",
                         "mistral:latest", "mixtral:latest", "gemma2:latest",
                         "phi3:latest", "qwen2.5:latest"]
        if available_models:
            model_choice = st.selectbox("Model", available_models, label_visibility="collapsed")
            st.markdown(
                f'<div style="font-size:0.72rem;color:#6fcf97;margin-top:0.3rem;">' +
                f'✅ {len(available_models)} local model(s) detected</div>',
                unsafe_allow_html=True
            )
        else:
            model_choice = st.selectbox("Model", OLLAMA_MODELS, label_visibility="collapsed")
            st.markdown(
                '<div style="font-size:0.72rem;color:#e8c97a;margin-top:0.3rem;">' +
                '⚠️ Ollama not running — start with <code>ollama serve</code></div>',
                unsafe_allow_html=True
            )
        st.markdown("""
        <div style="font-size:0.72rem;color:rgba(255,255,255,0.3);margin-top:0.8rem;line-height:1.5;">
        💻 Runs 100% locally · No internet needed<br>
        Install: <b>ollama.com/download</b>
        </div>""", unsafe_allow_html=True)

    else:  # Groq
        ollama_url = ""
        st.markdown("### 🔑 Groq API Key")
        groq_key = st.text_input(
            "Groq API Key", type="password",
            placeholder="gsk_...",
            label_visibility="collapsed",
            help="Free at console.groq.com — no credit card needed",
        )

        GROQ_MODELS = {
            "llama-3.3-70b-versatile": "Llama 3.3 70B · Best quality",
            "llama-3.1-8b-instant":    "Llama 3.1 8B · Fastest",
            "mixtral-8x7b-32768":      "Mixtral 8x7B · Long context",
            "gemma2-9b-it":            "Gemma 2 9B · Balanced",
        }
        model_choice = st.selectbox(
            "Model",
            list(GROQ_MODELS.keys()),
            format_func=lambda x: GROQ_MODELS[x],
            label_visibility="collapsed",
        )
        if groq_key:
            st.markdown(
                '<div style="font-size:0.72rem;color:#6fcf97;margin-top:0.3rem;">✅ API key entered</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div style="font-size:0.72rem;color:#e8c97a;margin-top:0.3rem;">' +
                '🔑 Get free key at <b>console.groq.com</b></div>',
                unsafe_allow_html=True
            )
        st.markdown("""
        <div style="font-size:0.72rem;color:rgba(255,255,255,0.3);margin-top:0.8rem;line-height:1.5;">
        ☁️ Cloud · Free tier · No credit card<br>
        ~300 req/day free on Groq
        </div>""", unsafe_allow_html=True)

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
    Processes 5000+ words in chunks.<br>
    Zero external scoring dependencies.
    </div>
    """, unsafe_allow_html=True)


# ── HERO BANNER ────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero-banner">
  <div class="hero-badge">v4.4 · Full Suite</div>
  <div class="hero-title">HumanizeAI</div>
  <div class="hero-sub">Humanizer · Paraphraser · Grammar Checker · Ollama & Groq · 8-dimension scoring</div>
</div>
""", unsafe_allow_html=True)


# ── SESSION STATE INIT ────────────────────────────────────────────────────
for key, default in [
    ("output_text", ""), ("paraphrase_out", ""),
    ("grammar_corrected", ""), ("grammar_issues", []),
    ("clear_input", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# Handle clear input flag before widget renders
if st.session_state.clear_input:
    st.session_state.input_text = ""
    st.session_state.output_text = ""
    st.session_state.clear_input = False

# ── TABS ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["✍️  Humanizer", "🔄  Paraphraser", "✅  Grammar Checker"])

# ══════════════════════════════════════════════════════════════════════════
# TAB 1 — HUMANIZER
# ══════════════════════════════════════════════════════════════════════════
with tab1:
    col_in, col_out = st.columns([1, 1], gap="large")

    with col_in:
        # ── Header row: title + paste/clear buttons ────────────────────
        hdr_left, hdr_right = st.columns([3, 2])
        with hdr_left:
            st.markdown('<div class="card-title">📄 Input Text</div>', unsafe_allow_html=True)
        with hdr_right:
            st.markdown('''
            <div style="display:flex;gap:0.5rem;justify-content:flex-end;padding-top:0.15rem;">
              <button id="paste-btn"
                onclick="(function(){{
                  if(navigator.clipboard && navigator.clipboard.readText){{
                    navigator.clipboard.readText().then(function(txt){{
                      var ta=window.parent.document.querySelector('textarea[data-testid=stTextArea]');
                      if(!ta)ta=window.parent.document.querySelector('textarea');
                      if(ta){{
                        var nativeInputValueSetter=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
                        nativeInputValueSetter.call(ta,txt);
                        ta.dispatchEvent(new Event('input',{{bubbles:true}}));
                      }}
                    }}).catch(function(){{alert('Paste: Please use Ctrl+V / Cmd+V in the text box directly');}});
                  }} else {{ alert('Paste: Please use Ctrl+V / Cmd+V in the text box directly'); }}
                }})();"
                style="background:#1a3a2e;color:#6fcf97;border:1px solid #4a7c59;
                       border-radius:7px;padding:0.3rem 0.75rem;cursor:pointer;
                       font-size:0.78rem;font-family:'DM Sans',sans-serif;">
                📋 Paste
              </button>
            </div>''', unsafe_allow_html=True)

        input_text = st.text_area(
            label="Input", height=360,
            placeholder="Paste your AI-generated text here (5000+ words supported)…",
            label_visibility="collapsed", key="input_text",
        )

        # ── Below textarea: word count + Clear button ──────────────────
        wc_in = len(input_text.split()) if input_text.strip() else 0
        sc_in = len(re.split(r'[.!?]+', input_text)) if input_text.strip() else 0
        badge_col, clear_col = st.columns([3, 1])
        with badge_col:
            st.markdown(f'<span class="wc-badge">📝 {wc_in:,} words · {sc_in} sentences</span>', unsafe_allow_html=True)
        with clear_col:
            if st.button("🗑️ Clear", key="clear_btn", use_container_width=True,
                         disabled=(not input_text.strip())):
                st.session_state.clear_input = True
                st.rerun()

        if input_text.strip():
            scores_in = compute_scores(input_text)
            st.markdown('<p style="color:#c9a84c;font-weight:700;margin-top:0.8rem;">Before — Humanness Analysis</p>', unsafe_allow_html=True)
            r1, r2, r3, r4 = st.columns(4)
            with r1: st.markdown(render_score_ring(scores_in["humanness"],    "Humanness"),   unsafe_allow_html=True)
            with r2: st.markdown(render_score_ring(scores_in["flesch"],       "Readability"), unsafe_allow_html=True)
            with r3: st.markdown(render_score_ring(scores_in["ttr"],          "Lexical Div"), unsafe_allow_html=True)
            with r4: st.markdown(render_score_ring(scores_in["sl_variation"], "Rhythm Var"),  unsafe_allow_html=True)
            st.markdown(render_metrics(scores_in), unsafe_allow_html=True)
        else:
            scores_in = {}

    with col_out:
        st.markdown('<div class="card-title">✨ Humanized Output</div>', unsafe_allow_html=True)
        output_text = st.session_state.output_text

        if output_text.strip():
            import html as _html
            _safe_out = _html.escape(output_text)
            st.markdown(
                f'<div class="output-box">{_safe_out}</div>',
                unsafe_allow_html=True,
            )
            # ── Copy button ────────────────────────────────────────────
            make_copy_btn("humanizer-out", output_text, "📋 Copy Text")

            scores_out = compute_scores(output_text)
            wc_out = scores_out.get("word_count", 0)
            sc_out = scores_out.get("sent_count", 0)
            st.markdown(f'<span class="wc-badge">📝 {wc_out:,} words · {sc_out} sentences</span>', unsafe_allow_html=True)
            st.markdown('<p style="color:#c9a84c;font-weight:700;margin-top:0.8rem;">After — Humanness Analysis</p>', unsafe_allow_html=True)
            r1, r2, r3, r4 = st.columns(4)
            with r1: st.markdown(render_score_ring(scores_out["humanness"],    "Humanness"),   unsafe_allow_html=True)
            with r2: st.markdown(render_score_ring(scores_out["flesch"],       "Readability"), unsafe_allow_html=True)
            with r3: st.markdown(render_score_ring(scores_out["ttr"],          "Lexical Div"), unsafe_allow_html=True)
            with r4: st.markdown(render_score_ring(scores_out["sl_variation"], "Rhythm Var"),  unsafe_allow_html=True)
            st.markdown(render_metrics(scores_out), unsafe_allow_html=True)
        else:
            st.markdown(
                '''<div style="background:white;border:1.5px dashed #d4c9b5;border-radius:10px;
                    min-height:380px;display:flex;align-items:center;justify-content:center;
                    flex-direction:column;gap:0.6rem;color:#9a8a7a;">
                  <div style="font-size:2rem;">✨</div>
                  <div style="font-size:0.9rem;font-family:DM Sans,sans-serif;">Humanized text will appear here</div>
                </div>''',
                unsafe_allow_html=True,
            )
            scores_out = {}

    # Action row
    st.markdown("<br>", unsafe_allow_html=True)
    btn_col, info_col = st.columns([2, 3])
    with btn_col:
        run_btn = st.button("✦ Humanize Text", type="primary", use_container_width=True, disabled=(not input_text.strip()))
    with info_col:
        if not input_text.strip():
            st.info("📄 Paste your text in the input panel above.")
        elif backend == "⚡ Groq (Cloud Free)" and not groq_key:
            st.warning("🔑 Enter your Groq API key in the sidebar. Free at console.groq.com")
        else:
            chunks = chunk_text(input_text)
            icon = "🦙" if "Ollama" in backend else "⚡"
            st.markdown(
                f'<div class="wc-badge">{icon} {len(chunks)} chunk{"s" if len(chunks)>1 else ""} '
                f'· {model_choice.split(":")[0]} · {intensity}</div>',
                unsafe_allow_html=True,
            )

# ══════════════════════════════════════════════════════════════════════════
# TAB 2 — PARAPHRASER
# ══════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="card-title">🔄 Paraphraser</div>', unsafe_allow_html=True)

    p_col1, p_col2 = st.columns([1, 1], gap="large")

    with p_col1:
        st.markdown('<p style="color:#c9a84c;font-weight:700;">Input Text</p>', unsafe_allow_html=True)
        para_input = st.text_area("Para input", height=320,
            placeholder="Paste text to paraphrase…",
            label_visibility="collapsed", key="para_input")

        p_mode_col, p_btn_col = st.columns([2, 1])
        with p_mode_col:
            para_mode = st.selectbox("Mode", list(PARAPHRASE_MODES.keys()),
                                     label_visibility="collapsed", key="para_mode")
        with p_btn_col:
            para_btn = st.button("🔄 Paraphrase", type="primary",
                                 use_container_width=True,
                                 disabled=(not para_input.strip()))

        if para_input.strip():
            wc_p = len(para_input.split())
            st.markdown(f'<span class="wc-badge">📝 {wc_p:,} words</span>', unsafe_allow_html=True)

    with p_col2:
        st.markdown('<p style="color:#c9a84c;font-weight:700;">Paraphrased Output</p>', unsafe_allow_html=True)
        para_out = st.session_state.paraphrase_out

        if para_out.strip():
            import html as _html
            _safe_para = _html.escape(para_out)
            st.markdown(
                f'<div class="output-box-para">{_safe_para}</div>',
                unsafe_allow_html=True,
            )
            make_copy_btn("para-out", para_out, "📋 Copy")
            wc_po = len(para_out.split())
            st.markdown(f'<span class="wc-badge">📝 {wc_po:,} words</span>', unsafe_allow_html=True)
        else:
            st.markdown(
                '''<div style="background:white;border:1.5px dashed #d4c9b5;border-radius:10px;
                    min-height:320px;display:flex;align-items:center;justify-content:center;
                    flex-direction:column;gap:0.5rem;color:#9a8a7a;">
                  <div style="font-size:2rem;">🔄</div>
                  <div style="font-size:0.9rem;">Paraphrased text will appear here</div>
                </div>''', unsafe_allow_html=True)

    # Paraphrase processing
    if para_btn:
        if backend == "⚡ Groq (Cloud Free)" and not groq_key:
            st.error("🔑 Enter your Groq API key in the sidebar.")
        else:
            use_groq_p = (backend == "⚡ Groq (Cloud Free)")
            with st.spinner(f"Paraphrasing in {para_mode} mode…"):
                try:
                    result = paraphrase_text(use_groq_p, ollama_url, groq_key, model_choice, para_input, para_mode)
                    st.session_state.paraphrase_out = result
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {str(e)}")

# ══════════════════════════════════════════════════════════════════════════
# TAB 3 — GRAMMAR CHECKER
# ══════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="card-title">✅ Grammar & Style Checker</div>', unsafe_allow_html=True)

    g_col1, g_col2 = st.columns([1, 1], gap="large")

    with g_col1:
        st.markdown('<p style="color:#c9a84c;font-weight:700;">Input Text</p>', unsafe_allow_html=True)
        gram_input = st.text_area("Grammar input", height=320,
            placeholder="Paste text to check for grammar, spelling, and style…",
            label_visibility="collapsed", key="gram_input")
        gram_btn = st.button("✅ Check Grammar", type="primary",
                             use_container_width=True,
                             disabled=(not gram_input.strip()))
        if gram_input.strip():
            wc_g = len(gram_input.split())
            st.markdown(f'<span class="wc-badge">📝 {wc_g:,} words</span>', unsafe_allow_html=True)

    with g_col2:
        st.markdown('<p style="color:#c9a84c;font-weight:700;">Corrected Text</p>', unsafe_allow_html=True)
        gram_corrected = st.session_state.grammar_corrected

        if gram_corrected.strip():
            import html as _html
            _safe_gram = _html.escape(gram_corrected)
            st.markdown(
                f'<div style="background:white;border:1.5px solid #4a7c59;border-radius:10px;padding:1.1rem 1.3rem;height:260px;overflow-y:auto;font-family:DM Sans,sans-serif;font-size:0.9rem;line-height:1.7;color:#1a1a2e;white-space:pre-wrap;word-break:break-word;">{_safe_gram}</div>',
                unsafe_allow_html=True,
            )
            make_copy_btn("gram-out", gram_corrected, "📋 Copy Corrected", "#6fcf97", "#1a3a2e", "#4a7c59")

            # Issues table
            issues = st.session_state.grammar_issues
            if issues:
                st.markdown(f'<p style="color:#c9a84c;font-weight:700;margin-top:1rem;">⚠️ {len(issues)} Issue(s) Found</p>', unsafe_allow_html=True)
                type_colors = {
                    "grammar":     "#e87a7a", "spelling":  "#e8a87a",
                    "punctuation": "#e8d47a", "style":     "#a8d47a",
                    "wordiness":   "#7ab8e8", "clarity":   "#b87ae8",
                }
                for iss in issues:
                    t = iss.get("type","other")
                    tc = type_colors.get(t, "#aaa")
                    orig = iss.get("original","")
                    corr = iss.get("corrected","")
                    expl = iss.get("explanation","")
                    st.markdown(f'''
                    <div style="background:white;border-left:4px solid {tc};border-radius:0 8px 8px 0;
                         padding:0.7rem 1rem;margin-bottom:0.5rem;">
                      <div style="display:flex;gap:0.8rem;align-items:center;margin-bottom:0.3rem;">
                        <span style="background:{tc}22;color:{tc};border-radius:4px;padding:0.1rem 0.5rem;
                               font-size:0.7rem;font-weight:700;text-transform:uppercase;">{t}</span>
                      </div>
                      <div style="font-size:0.82rem;color:#5a6a7a;">
                        <span style="color:#e87a7a;text-decoration:line-through;">{orig}</span>
                        <span style="color:#1a1a2e;margin:0 0.4rem;">→</span>
                        <span style="color:#4a7c59;font-weight:600;">{corr}</span>
                      </div>
                      <div style="font-size:0.78rem;color:#7a8a9a;margin-top:0.3rem;">{expl}</div>
                    </div>''', unsafe_allow_html=True)
            else:
                st.markdown('<p style="color:#6fcf97;font-weight:600;margin-top:0.8rem;">✅ No issues found — text looks great!</p>', unsafe_allow_html=True)
        else:
            st.markdown(
                '''<div style="background:white;border:1.5px dashed #d4c9b5;border-radius:10px;
                    min-height:320px;display:flex;align-items:center;justify-content:center;
                    flex-direction:column;gap:0.5rem;color:#9a8a7a;">
                  <div style="font-size:2rem;">✅</div>
                  <div style="font-size:0.9rem;">Grammar report will appear here</div>
                </div>''', unsafe_allow_html=True)

    # Grammar processing
    if gram_btn:
        if backend == "⚡ Groq (Cloud Free)" and not groq_key:
            st.error("🔑 Enter your Groq API key in the sidebar.")
        else:
            use_groq_g = (backend == "⚡ Groq (Cloud Free)")
            with st.spinner("Checking grammar and style…"):
                try:
                    result = grammar_check(use_groq_g, ollama_url, groq_key, model_choice, gram_input)
                    st.session_state.grammar_corrected = result.get("corrected", "")
                    st.session_state.grammar_issues    = result.get("issues", [])
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {str(e)}")


# ── PROCESSING LOGIC ───────────────────────────────────────────────────────

if run_btn:
    if not input_text.strip():
        st.error("Please enter some text to humanize.")
    elif backend == "⚡ Groq (Cloud Free)" and not groq_key:
        st.error("🔑 Please enter your Groq API key in the sidebar.")
    else:
        use_groq = (backend == "⚡ Groq (Cloud Free)")
        try:
            # ── Pre-flight check ──────────────────────────────────────────
            if not use_groq:
                try:
                    ping = requests.get(f"{ollama_url}/api/tags", timeout=5)
                    ping.raise_for_status()
                except Exception:
                    st.error(
                        f"❌ Cannot reach Ollama at **{ollama_url}**. "
                        "Make sure Ollama is running (`ollama serve`) and the URL is correct."
                    )
                    st.stop()
            else:
                # Light Groq auth check
                test_resp = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {groq_key}"}, timeout=10
                )
                if test_resp.status_code == 401:
                    st.error("❌ Invalid Groq API key. Check it at console.groq.com")
                    st.stop()

            chunks = chunk_text(input_text)
            n = len(chunks)
            progress_bar = st.progress(0, text="Initialising…")
            status_box   = st.empty()
            results = []
            icon = "⚡" if use_groq else "🦙"
            backend_label = f"Groq/{model_choice}" if use_groq else model_choice

            for i, chunk in enumerate(chunks):
                status_box.markdown(
                    f'<div class="wc-badge">{icon} Processing chunk {i+1}/{n} ' +
                    f'({len(chunk.split())} words) via {backend_label}…</div>',
                    unsafe_allow_html=True,
                )
                if use_groq:
                    humanized = humanize_chunk_groq(groq_key, model_choice, chunk, style, intensity)
                else:
                    humanized = humanize_chunk_ollama(ollama_url, model_choice, chunk, style, intensity)
                results.append(humanized)
                progress_bar.progress((i + 1) / n, text=f"Chunk {i+1}/{n} complete")

            progress_bar.progress(1.0, text="✓ Complete!")
            status_box.empty()
            st.session_state.output_text = "\n\n".join(results)
            st.rerun()

        except requests.exceptions.ConnectionError as e:
            if use_groq:
                st.error("❌ Cannot reach Groq API. Check your internet connection.")
            else:
                st.error(f"❌ Connection refused at {ollama_url}. Run `ollama serve` first.")
        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out. Try again — the model may still be loading.")
        except requests.exceptions.HTTPError as e:
            if use_groq and e.response.status_code == 429:
                st.error("⚠️ Groq rate limit hit. Wait a moment and try again (free tier: ~30 req/min).")
            else:
                st.error(f"❌ HTTP Error: {str(e)}")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")


# ── COMPARISON PANEL ───────────────────────────────────────────────────────

if scores_in and scores_out:
    st.markdown("---")
    st.markdown('<div class="card-title" style="font-size:1.15rem;">📊 Before vs After — Full Comparison</div>', unsafe_allow_html=True)

    delta      = scores_out["humanness"] - scores_in["humanness"]
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
        ("Humanness Score",    "humanness",        "Higher = more natural"),
        ("Flesch Readability", "flesch",            "Higher = easier to read"),
        ("Lexical Diversity",  "ttr",               "Higher = richer vocabulary"),
        ("Rhythm Variation",   "sl_variation",      "Higher = more varied sentences"),
        ("Burstiness",         "burstiness",        "Higher = more human rhythm"),
        ("Passive Voice Score","passive_score",     "Higher = more active voice"),
        ("Transition Score",   "transition_score",  "Higher = better flow"),
        ("Grade Level",        "grade_level",       "Lower = more accessible"),
    ]

    c1, c2, c3, c4 = st.columns(4)
    cols = [c1, c2, c3, c4]
    for idx, (label, key, hint) in enumerate(metrics_to_compare):
        v_before = scores_in.get(key, 0)
        v_after  = scores_out.get(key, 0)
        d        = v_after - v_before
        sign     = "+" if d >= 0 else ""
        col_d    = "#6fcf97" if d >= 0 else "#e87a7a"
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
