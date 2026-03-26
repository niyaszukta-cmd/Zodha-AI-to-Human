import streamlit as st
import streamlit.components.v1 as components
import requests
import re
import time
import math
import json
import os

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

GROQ_MODELS = {
    "llama-3.3-70b-versatile": "Llama 3.3 70B · Best quality",
    "llama-3.1-8b-instant":    "Llama 3.1 8B · Fastest",
    "mixtral-8x7b-32768":      "Mixtral 8x7B · Long context",
    "gemma2-9b-it":            "Gemma 2 9B · Balanced",
}

# Admin password — set via environment variable or change here
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "nyztrade2026")

# ══════════════════════════════════════════════════════════════════════════════
# ZERO-DEPENDENCY READABILITY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _count_syllables(word):
    word = word.lower().strip('.,!?;:\'\'"()')
    if not word: return 0
    if len(word) <= 3: return 1
    word = re.sub(r'(?:[^laeiouy]es|ed|[^laeiouy]e)$', '', word)
    word = re.sub(r'^y', '', word)
    return max(1, len(re.findall(r'[aeiouy]{1,2}', word)))

def _flesch_reading_ease(text):
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    words = re.findall(r'\b[a-zA-Z]+\b', text)
    if not sentences or not words: return 50.0
    syllables = sum(_count_syllables(w) for w in words)
    score = 206.835 - 1.015*(len(words)/len(sentences)) - 84.6*(syllables/len(words))
    return round(max(0.0, min(100.0, score)), 1)

def _flesch_kincaid_grade(text):
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    words = re.findall(r'\b[a-zA-Z]+\b', text)
    if not sentences or not words: return 10.0
    syllables = sum(_count_syllables(w) for w in words)
    grade = 0.39*(len(words)/len(sentences)) + 11.8*(syllables/len(words)) - 15.59
    return round(max(0.0, grade), 1)

def _sent_tokenize(text):
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p.strip()] or [text]

def _word_tokenize(text):
    return re.findall(r'\b[a-zA-Z]+\b', text.lower())

def compute_scores(text):
    if not text or not text.strip(): return {}
    sentences    = _sent_tokenize(text)
    words_alpha  = _word_tokenize(text)
    word_count   = len(words_alpha)
    sent_count   = max(len(sentences), 1)
    flesch       = _flesch_reading_ease(text)
    unique_words = set(words_alpha)
    ttr          = (len(unique_words)/word_count*100) if word_count > 0 else 0
    sent_lengths = [len(_word_tokenize(s)) for s in sentences]
    sl_variation = 0.0
    if len(sent_lengths) > 1:
        mean_sl = sum(sent_lengths)/len(sent_lengths)
        sl_variation = min(100, math.sqrt(sum((l-mean_sl)**2 for l in sent_lengths)/len(sent_lengths))*5)
    avg_sent_len = word_count/sent_count
    burstiness   = 0.0
    if len(sent_lengths) > 2:
        diffs = [abs(sent_lengths[i]-sent_lengths[i-1]) for i in range(1, len(sent_lengths))]
        burstiness = min(100,(sum(diffs)/len(diffs))*4)
    contractions = len(re.findall(
        r"\b(i'm|you're|he's|she's|it's|we're|they're|i've|you've|we've|they've|"
        r"i'd|you'd|he'd|she'd|we'd|they'd|i'll|you'll|he'll|she'll|we'll|they'll|"
        r"isn't|aren't|wasn't|weren't|don't|doesn't|didn't|won't|wouldn't|can't|"
        r"couldn't|shouldn't|haven't|hasn't|hadn't|that's|there's|here's|let's)\b",
        text.lower()))
    contraction_score = min(100,(contractions/max(sent_count,1))*40)
    first_person  = len(re.findall(r'\b(i|me|my|myself|we|our|us)\b', text.lower()))
    fp_score      = min(100,(first_person/max(word_count,1))*500)
    passive_count = len(re.findall(r'\b(is|are|was|were|be|been|being)\s+\w+ed\b', text.lower()))
    passive_score = max(0, 100-(passive_count/max(sent_count,1))*60)
    transition_words = ['however','therefore','moreover','furthermore','although',
        'despite','meanwhile','consequently','additionally','nevertheless',
        'on the other hand','in contrast','for instance','in other words',
        'as a result','similarly','in fact','of course','after all']
    transition_score = min(100, sum(1 for t in transition_words if t in text.lower())*8)
    grade     = _flesch_kincaid_grade(text)
    humanness = round(min(100,max(0,
        flesch*0.20 + ttr*0.18 + sl_variation*0.15 + burstiness*0.12 +
        contraction_score*0.10 + fp_score*0.08 + passive_score*0.10 + transition_score*0.07
    )),1)
    return {"humanness":humanness,"flesch":round(flesch,1),"ttr":round(ttr,1),
            "sl_variation":round(sl_variation,1),"burstiness":round(burstiness,1),
            "contraction_score":round(contraction_score,1),"passive_score":round(passive_score,1),
            "transition_score":round(transition_score,1),"word_count":word_count,
            "sent_count":sent_count,"avg_sent_len":round(avg_sent_len,1),
            "grade_level":round(grade,1),"unique_words":len(unique_words)}

def score_color(score):
    if score>=75:   return("#1a3a2e","#6fcf97","Excellent")
    elif score>=55: return("#2d3a1e","#b5d97a","Good")
    elif score>=35: return("#3a2d1a","#e8c97a","Fair")
    else:           return("#3a1a1a","#e87a7a","Needs Work")

def render_score_ring(score, label):
    bg,fg,grade_lbl = score_color(score)
    return f"""<div class="score-ring-wrap">
      <div class="score-ring" style="background:{bg};color:{fg};box-shadow:0 0 0 3px {fg}30,0 4px 16px rgba(0,0,0,0.2);">
        {score:.0f}</div>
      <div class="score-label">{label}</div>
      <div class="score-label" style="color:{fg};font-size:0.68rem;">{grade_lbl}</div>
    </div>"""

def render_metrics(sc):
    chips=[("Words",sc.get("word_count",0)),("Sentences",sc.get("sent_count",0)),
           ("Avg Len",sc.get("avg_sent_len",0)),("Grade",sc.get("grade_level",0)),
           ("Unique",sc.get("unique_words",0)),("Flesch",sc.get("flesch",0)),
           ("Lex Div%",sc.get("ttr",0)),("Rhythm",sc.get("sl_variation",0))]
    html='<div class="metric-row">'
    for name,val in chips:
        html+=f'<div class="metric-chip"><b>{val}</b> {name}</div>'
    return html+"</div>"

def make_copy_btn(copy_id, text, label="📋 Copy", color="#c9a84c", bg="#1a1a2e", border="#c9a84c"):
    import html as _html
    safe = _html.escape(text, quote=True)
    html_src = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:transparent;">
<textarea id="cp" readonly style="position:absolute;left:-9999px;top:0;width:1px;height:1px;">{safe}</textarea>
<button id="btn" onclick="var el=document.getElementById('cp');el.select();el.setSelectionRange(0,99999);
  var ok=false;try{{ok=document.execCommand('copy');}}catch(e){{}}
  if(!ok&&navigator.clipboard){{navigator.clipboard.writeText(el.value).then(function(){{
    document.getElementById('btn').innerHTML='✅ Copied!';
    setTimeout(function(){{document.getElementById('btn').innerHTML='{label}';}},2000);}});}}
  else{{document.getElementById('btn').innerHTML='✅ Copied!';
    setTimeout(function(){{document.getElementById('btn').innerHTML='{label}';}},2000);}}"
  style="background:{bg};color:{color};border:1.5px solid {border};border-radius:8px;
         padding:0.4rem 1.1rem;cursor:pointer;font-size:0.82rem;
         font-family:'DM Sans',sans-serif;font-weight:500;transition:all 0.2s;white-space:nowrap;">
  {label}</button></body></html>"""
    components.html(html_src, height=46, scrolling=False)

# ══════════════════════════════════════════════════════════════════════════════
# AI PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

STYLE_PROMPTS = {
    "Academic": (
        "You are a senior academic editor at a Tier-1 research journal with 20 years of experience. "
        "Rewrite so it reads as authored by a distinguished human scholar — NOT generated by AI. "
        "\n\nSTRICT ACADEMIC REGISTER (non-negotiable):"
        "\n• NEVER use contractions (it's→it is, don't→do not, we've→we have). "
        "\n• NEVER use informal phrases, slang, or casual asides. "
        "\n• Maintain formal scholarly register throughout. "
        "\n\nHUMANNESS TECHNIQUES:"
        "\n• Vary sentence length: concise assertions (10-15 words) mixed with complex sentences (30-45 words). "
        "\n• Use scholarly hedging: 'the evidence suggests', 'it appears that', 'one may argue'. "
        "\n• Insert discourse markers: 'Notably,', 'Crucially,', 'Of particular significance is'. "
        "\n• Use precise domain-specific vocabulary — do not simplify technical terms. "
        "\n• Active constructions: 'The analysis reveals' not 'It was revealed by the analysis'. "
        "\n\nPreserve 100% of original meaning, all data, all citations, and all technical terminology."
    ),
    "Conversational": (
        "Rewrite to sound like a knowledgeable person explaining naturally and engagingly. "
        "\n• Use contractions freely: it's, don't, we've, can't, that's, they're. "
        "\n• Alternate sentence lengths — short (4-8 words) for impact, longer for explanation. "
        "\n• Use rhetorical questions: 'But why does this matter?' "
        "\n• Add natural connectives: 'On top of that,', 'Here's the thing —'. "
        "\n• Use first-person (I, we, you) to create connection. "
        "\nPreserve all key facts and meaning."
    ),
    "Professional": (
        "Rewrite as a senior professional writer — authoritative, confident, natural, never stiff. "
        "\n• Avoid contractions in formal contexts (prefer 'does not' over 'doesn't'). "
        "\n• Mix short declarative sentences with longer analytical ones. "
        "\n• Active voice for 80%+ sentences. "
        "\n• Deploy transitions: 'More importantly,', 'That said,', 'In practice,'. "
        "\n• Vary paragraph length. "
        "\nPreserve every key idea and fact."
    ),
    "Journalistic": (
        "Rewrite as a senior writer at The Economist or The Atlantic. "
        "\n• Open with a short punchy hook (8-12 words). "
        "\n• Vary rhythm dramatically. Active voice throughout. "
        "\n• Journalist transitions: 'The result?', 'Consider this:', 'Yet the picture is more complex.' "
        "\n• Sparse contractions (Economist style). "
        "\n• Create narrative momentum. "
        "\nKeep all facts."
    ),
    "Creative": (
        "Transform into vivid expressive prose preserving all meaning. "
        "\n• Striking sentence rhythm variation. "
        "\n• Metaphor, analogy, sensory language where natural. "
        "\n• Vary paragraph lengths — single-sentence paragraphs for punch. "
        "\n• Selective contractions for natural voice. "
        "\nPreserve all original ideas."
    ),
}

PARAPHRASE_MODES = {
    "Standard": "Rewrite using completely different words and structures while preserving exact meaning. Output ONLY the paraphrased text.",
    "Simplify": "Rewrite in simpler, clearer language. Shorter sentences, common words, active voice. Output ONLY the simplified text.",
    "Formal":   "Rewrite in highly formal academic register. Precise vocabulary, structured sentences. Output ONLY the formal text.",
    "Concise":  "Remove all redundancy — make it as tight as possible while keeping every key idea. Output ONLY the concise text.",
    "Creative": "Paraphrase with vivid expressive language, fresh metaphors, varied rhythm. Output ONLY the paraphrased text.",
}

GRAMMAR_SYSTEM = (
    "You are a professional copy-editor. Proofread and return a JSON response with exactly these keys:\n"
    "- \"corrected\": the fully corrected text\n"
    "- \"issues\": list of objects with keys \"original\", \"corrected\", \"type\", \"explanation\"\n"
    "Types: grammar, spelling, punctuation, style, wordiness, clarity\n"
    "Return ONLY valid JSON."
)

INTENSITY_INSTRUCTIONS = {
    "Light":    "Lightly edit for naturalness. Fix robotic phrases, add 2-3 varied sentence lengths and transitions. Keep 80% of original structure. Do NOT add informal language to formal/academic text.",
    "Moderate": "Substantially rewrite for human naturalness. Restructure half the sentences. Vary length (shortest 8-12 words, longest 28-40 words). For Academic/Professional: NO contractions. For Conversational/Journalistic: contractions welcome.",
    "Deep":     "Completely transform into rich natural human writing appropriate to the chosen style. Every sentence restructured. Dramatic length variation. For ACADEMIC: scholarly discourse markers, hedging, NEVER contractions. For CONVERSATIONAL: contractions freely, rhetorical questions. Preserve 100% of original meaning and data.",
}

_STYLE_REGISTER_RULES = {
    "Academic":      "REGISTER: Absolutely NO contractions. NO informal language. Humanness via rhythm variation, hedging, and discourse markers only.",
    "Conversational":"REGISTER: Contractions freely. Warm, engaging, natural. Rhetorical questions and personal voice encouraged.",
    "Professional":  "REGISTER: Avoid contractions in formal contexts. Confident, polished, formal-natural.",
    "Journalistic":  "REGISTER: Sparse purposeful contractions (Economist style). Punchy, direct, active voice.",
    "Creative":      "REGISTER: Selective contractions for natural voice. Expressive, vivid, literary quality.",
}

def _build_prompt(style, intensity, chunk):
    system = STYLE_PROMPTS[style]
    note   = INTENSITY_INSTRUCTIONS[intensity]
    reg    = _STYLE_REGISTER_RULES[style]
    user   = f"""{note}\n\n{reg}\n\nABSOLUTE RULES:\n1. Output ONLY the rewritten text — no preamble, no commentary.\n2. Preserve 100% of original meaning, data, statistics, technical terms, citations.\n3. No bullet points unless original had them.\n4. SENTENCE LENGTH VARIATION IS MANDATORY — concise (10-15 words) AND complex (28-40 words) sentences.\n5. No consecutive sentences starting with the same word.\n6. At least 3 appropriate transition phrases for the register.\n7. Do NOT invent new facts.\n\nTEXT TO REWRITE:\n\"\"\"\n{chunk}\n\"\"\"\n"""
    return system, user

def chunk_text(text, max_words=800):
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks, current, current_wc = [], [], 0
    for para in paragraphs:
        wc = len(para.split())
        if current_wc + wc > max_words and current:
            chunks.append('\n\n'.join(current))
            current, current_wc = [para], wc
        else:
            current.append(para); current_wc += wc
    if current: chunks.append('\n\n'.join(current))
    return chunks if chunks else [text]

def call_groq(api_key, model, system_prompt, user_prompt, max_tokens=2048, stream=False):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model,
               "messages": [{"role":"system","content":system_prompt},
                             {"role":"user","content":user_prompt}],
               "max_tokens": max_tokens, "temperature": 0.7, "stream": stream}
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
                         headers=headers, json=payload, timeout=120, stream=stream)
    resp.raise_for_status()
    return resp

def stream_groq(api_key, model, system_prompt, user_prompt, max_tokens=2048):
    resp = call_groq(api_key, model, system_prompt, user_prompt, max_tokens, stream=True)
    for line in resp.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = line[6:]
                if data == '[DONE]': break
                try:
                    chunk = json.loads(data)
                    delta = chunk['choices'][0]['delta'].get('content','')
                    if delta: yield delta
                except: continue

def humanize_streaming(api_key, model, chunk, style, intensity, placeholder):
    system, user = _build_prompt(style, intensity, chunk)
    full_text = ""
    import html as _html
    for token in stream_groq(api_key, model, system, user):
        full_text += token
        safe = _html.escape(full_text)
        placeholder.markdown(
            f'<div class="output-box" style="min-height:100px;">{safe}▌</div>',
            unsafe_allow_html=True)
    safe = _html.escape(full_text)
    placeholder.markdown(f'<div class="output-box">{safe}</div>', unsafe_allow_html=True)
    return full_text

def paraphrase_text(api_key, model, text, mode):
    resp = call_groq(api_key, model, PARAPHRASE_MODES[mode],
                     f"TEXT TO PARAPHRASE:\n\"\"\"\n{text}\n\"\"\"", stream=False)
    return resp.json()["choices"][0]["message"]["content"].strip()

def grammar_check(api_key, model, text):
    resp = call_groq(api_key, model, GRAMMAR_SYSTEM,
                     f"TEXT TO PROOFREAD:\n\"\"\"\n{text}\n\"\"\"", max_tokens=3000, stream=False)
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    raw = re.sub(r"^```(?:json)?\s*","",raw); raw=re.sub(r"\s*```$","",raw)
    try: return json.loads(raw)
    except: return {"corrected":raw,"issues":[]}

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG & CSS
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="HumanizeAI · NYZTrade", page_icon="✍️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
:root{--ink:#1a1a2e;--cream:#faf7f2;--gold:#c9a84c;--gold-lt:#e8d5a3;--rust:#b5451b;--slate:#5a6a7a;--border:#d4c9b5;}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;background-color:var(--cream)!important;color:var(--ink);}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding-top:1.2rem!important;max-width:1400px!important;}
.hero-banner{background:linear-gradient(135deg,var(--ink) 0%,#2d2d4e 60%,#1a3a2e 100%);border-radius:16px;padding:1.5rem 2.5rem 1.3rem;margin-bottom:1.5rem;position:relative;overflow:hidden;}
.hero-title{font-family:'Playfair Display',serif;font-size:2.2rem;font-weight:900;color:var(--gold);margin:0 0 0.2rem;position:relative;}
.hero-sub{font-size:0.9rem;color:rgba(255,255,255,0.6);margin:0;position:relative;}
.hero-badge{position:absolute;top:1.2rem;right:2rem;background:rgba(201,168,76,0.15);border:1px solid rgba(201,168,76,0.4);color:var(--gold);border-radius:20px;padding:0.3rem 0.9rem;font-size:0.75rem;font-family:'DM Mono',monospace;letter-spacing:1px;text-transform:uppercase;}
.card-title{font-family:'Playfair Display',serif;font-size:1.05rem;font-weight:700;color:#c9a84c!important;margin-bottom:0.8rem;padding-bottom:0.5rem;border-bottom:2px solid #c9a84c;}
.score-ring-wrap{display:flex;flex-direction:column;align-items:center;gap:0.3rem;}
.score-ring{width:80px;height:80px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:'Playfair Display',serif;font-size:1.5rem;font-weight:900;}
.score-label{font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--slate);text-align:center;}
.metric-row{display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:0.4rem;}
.metric-chip{background:#f5f0e8;border:1px solid var(--border);border-radius:7px;padding:0.35rem 0.7rem;font-size:0.78rem;color:#5a6a7a;}
.metric-chip b{color:#1a1a2e;font-weight:600;}
.output-box{background:white;border:1.5px solid #c9a84c;border-radius:10px;padding:1rem 1.2rem;height:380px;overflow-y:auto;overflow-x:hidden;font-family:'DM Sans',sans-serif;font-size:0.9rem;line-height:1.7;color:#1a1a2e;white-space:pre-wrap;word-break:break-word;box-sizing:border-box;}
.output-box-sm{background:white;border:1.5px solid #c9a84c;border-radius:10px;padding:1rem 1.2rem;height:320px;overflow-y:auto;font-family:'DM Sans',sans-serif;font-size:0.9rem;line-height:1.7;color:#1a1a2e;white-space:pre-wrap;word-break:break-word;}
.wc-badge{display:inline-block;background:#f5f0e8;border:1px solid var(--border);border-radius:6px;padding:0.2rem 0.6rem;font-family:'DM Mono',monospace;font-size:0.75rem;color:#5a6a7a;margin-top:0.3rem;}
textarea{font-family:'DM Sans',sans-serif!important;font-size:0.9rem!important;line-height:1.65!important;border-radius:10px!important;border:1.5px solid var(--border)!important;background:white!important;color:#1a1a2e!important;}
div[data-testid="stButton"]>button[kind="primary"]{background:linear-gradient(135deg,var(--ink),#2d2d4e)!important;color:var(--gold)!important;border:1.5px solid var(--gold)!important;border-radius:10px!important;font-family:'DM Sans',sans-serif!important;font-weight:600!important;transition:all 0.25s!important;}
div[data-testid="stButton"]>button[kind="primary"]:hover{transform:translateY(-2px)!important;box-shadow:0 6px 20px rgba(26,26,46,0.3)!important;}
div[data-testid="stRadio"] label{border:1px solid rgba(201,168,76,0.4)!important;border-radius:8px!important;padding:0.4rem 0.9rem!important;background:#f5f0e8!important;}
div[data-testid="stRadio"] label>div,div[data-testid="stRadio"] label span,div[data-testid="stRadio"] label p{color:#1a1a2e!important;font-weight:500!important;}
[data-testid="stSidebar"]{background:var(--ink)!important;border-right:1px solid rgba(201,168,76,0.2)!important;}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] span:not([data-testid]),[data-testid="stSidebar"] .stMarkdown p{color:rgba(255,255,255,0.85)!important;}
[data-testid="stSidebar"] h3{color:var(--gold)!important;font-family:'Playfair Display',serif!important;}
[data-testid="stSidebar"] input{background:rgba(255,255,255,0.08)!important;color:white!important;border:1px solid rgba(201,168,76,0.4)!important;border-radius:8px!important;}
[data-testid="stSidebar"] input::placeholder{color:rgba(255,255,255,0.35)!important;}
[data-testid="column"]{overflow:hidden!important;min-width:0!important;}
section.main .stMarkdown p{color:#1a1a2e!important;}
section.main strong,section.main b{color:#1a1a2e!important;}
div[data-testid="stAlert"] p{color:#1a1a2e!important;}
.improvement-banner{background:linear-gradient(135deg,#1a3a2e,#2d4a1e);border:1px solid rgba(74,124,89,0.5);border-radius:12px;padding:1rem 1.5rem;display:flex;align-items:center;gap:1rem;margin:1rem 0;}
.improvement-banner .score-delta{font-family:'Playfair Display',serif;font-size:2rem;font-weight:900;white-space:nowrap;}
.improvement-banner .score-desc{font-size:0.88rem;color:rgba(255,255,255,0.8);line-height:1.5;}
/* Admin panel */
.admin-hero{background:linear-gradient(135deg,#0d0d1a 0%,#1a0a2e 50%,#0a1a2e 100%);border-radius:16px;padding:1.5rem 2.5rem;margin-bottom:1.5rem;position:relative;}
.admin-hero-title{font-family:'Playfair Display',serif;font-size:2rem;font-weight:900;color:#b87ae8;}
.admin-badge{position:absolute;top:1.2rem;right:2rem;background:rgba(184,122,232,0.15);border:1px solid rgba(184,122,232,0.4);color:#b87ae8;border-radius:20px;padding:0.3rem 0.9rem;font-size:0.75rem;font-family:'DM Mono',monospace;text-transform:uppercase;letter-spacing:1px;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for k,v in [("output_text",""),("paraphrase_out",""),
             ("grammar_corrected",""),("grammar_issues",[]),
             ("clear_input",False),("show_admin",False),("admin_auth",False)]:
    if k not in st.session_state: st.session_state[k]=v

if st.session_state.clear_input:
    st.session_state.input_text=""
    st.session_state.output_text=""
    st.session_state.clear_input=False

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN PANEL (hidden, password-protected overlay)
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.show_admin:
    if not st.session_state.admin_auth:
        st.markdown("""<div class="admin-hero">
          <div class="admin-badge">Admin</div>
          <div class="admin-hero-title">🛡️ Admin Access</div>
          <div style="color:rgba(255,255,255,0.5);font-size:0.88rem;">NYZTrade Analytics</div>
        </div>""", unsafe_allow_html=True)
        _, cc, _ = st.columns([1,1.2,1])
        with cc:
            with st.container(border=True):
                pw = st.text_input("Admin Password", type="password",
                                   placeholder="Enter admin password", label_visibility="collapsed")
                if st.button("🔐 Enter", type="primary", use_container_width=True):
                    if pw == ADMIN_PASSWORD:
                        st.session_state.admin_auth = True
                        st.rerun()
                    else:
                        st.error("❌ Incorrect password.")
            if st.button("← Back to App", use_container_width=True):
                st.session_state.show_admin = False
                st.rerun()
        st.stop()

    # ── ADMIN DASHBOARD ──────────────────────────────────────────────────────
    st.markdown("""<div class="admin-hero">
      <div class="admin-badge">Admin · NYZTrade</div>
      <div class="admin-hero-title">🛡️ Admin Dashboard</div>
      <div style="color:rgba(255,255,255,0.5);font-size:0.88rem;">HumanizeAI · Platform Settings</div>
    </div>""", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown('<div style="color:#b87ae8;font-family:Playfair Display,serif;font-weight:700;font-size:1rem;padding:0.5rem 0;">🛡️ Admin Mode</div>', unsafe_allow_html=True)
        if st.button("← Exit Admin", use_container_width=True):
            st.session_state.show_admin = False
            st.session_state.admin_auth = False
            st.rerun()

    adm_tab1, adm_tab2 = st.tabs(["⚙️ API Key Settings", "📊 App Info"])

    with adm_tab1:
        st.markdown('<div class="card-title">⚙️ Groq API Key</div>', unsafe_allow_html=True)
        st.markdown('<p style="color:#5a6a7a;font-size:0.88rem;">Set a platform-wide Groq API key. This is used by the app automatically — no need to enter it in the sidebar each session.</p>', unsafe_allow_html=True)

        # Store key in st.secrets or session — for Streamlit Cloud use secrets.toml
        stored_key = st.session_state.get("platform_groq_key", os.environ.get("GROQ_API_KEY",""))
        new_key = st.text_input("Groq API Key", value=stored_key, type="password",
                                 placeholder="gsk_...", label_visibility="collapsed")
        if st.button("💾 Save Key for this Session", type="primary"):
            st.session_state.platform_groq_key = new_key
            st.success("✅ Key saved for this session. To persist across restarts, add GROQ_API_KEY to Streamlit secrets.")

        st.markdown("---")
        st.markdown("**To set permanently on Streamlit Cloud:**")
        st.code('''# In Streamlit Cloud → Settings → Secrets:
GROQ_API_KEY = "gsk_your_key_here"
ADMIN_PASSWORD = "your_admin_password"''', language="toml")

    with adm_tab2:
        st.markdown('<div class="card-title">📊 App Info</div>', unsafe_allow_html=True)
        info_items = [
            ("Version", "v5.4 · NYZTrade"),
            ("Mode", "Single-user · No login required"),
            ("Tools", "Humanizer · Paraphraser · Grammar Checker"),
            ("Backend", "Groq API (streaming)"),
            ("Models", ", ".join(GROQ_MODELS.keys())),
            ("Max Words/Session", "Unlimited"),
        ]
        for label, val in info_items:
            st.markdown(f"""<div style="background:white;border:1px solid #d4c9b5;border-radius:8px;
                 padding:0.6rem 1rem;margin-bottom:0.4rem;display:flex;justify-content:space-between;">
              <span style="color:#5a6a7a;font-size:0.85rem;">{label}</span>
              <span style="font-weight:600;color:#1a1a2e;font-size:0.85rem;">{val}</span>
            </div>""", unsafe_allow_html=True)

    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP — No login, opens directly
# ══════════════════════════════════════════════════════════════════════════════

# ── SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="font-family:Playfair Display,serif;font-size:1.1rem;color:#c9a84c;font-weight:700;margin-bottom:1rem;">✍️ HumanizeAI</div>', unsafe_allow_html=True)

    st.markdown("### ⚙️ Style")
    style = st.selectbox("Style", list(STYLE_PROMPTS.keys()), label_visibility="collapsed")
    st.markdown("### 🔧 Intensity")
    intensity = st.radio("Intensity", ["Light","Moderate","Deep"], index=1, label_visibility="collapsed")
    st.markdown("### 🤖 Model")
    model_choice = st.selectbox("Model", list(GROQ_MODELS.keys()),
                                format_func=lambda x: GROQ_MODELS[x],
                                label_visibility="collapsed")
    st.markdown("### 🔑 Groq API Key")

    # Resolve key: sidebar input > session platform key > env var
    env_key = os.environ.get("GROQ_API_KEY","")
    platform_key = st.session_state.get("platform_groq_key", env_key)
    saved_key = st.text_input("Groq Key", value=platform_key, type="password",
                              placeholder="gsk_...  (or set in Admin)", label_visibility="collapsed")
    if saved_key != platform_key:
        st.session_state.platform_groq_key = saved_key
    groq_key = saved_key or platform_key or env_key

    if groq_key:
        st.markdown('<div style="font-size:0.72rem;color:#6fcf97;margin-top:0.2rem;">✅ API key ready</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:0.72rem;color:#e8c97a;margin-top:0.2rem;">🔑 Add key or set GROQ_API_KEY in secrets</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""<div style="font-size:0.72rem;color:rgba(255,255,255,0.35);line-height:1.7;">
    • Academic · Conversational · Professional<br>
    • Journalistic · Creative styles<br>
    • Real-time streaming output<br>
    • 5000+ words · 8-dimension scoring
    </div>""", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🛡️ Admin", use_container_width=True, key="open_admin"):
        st.session_state.show_admin = True
        st.rerun()

# ── HERO ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <div class="hero-badge">v5.4 · NYZTrade</div>
  <div class="hero-title">HumanizeAI</div>
  <div class="hero-sub">Humanizer · Paraphraser · Grammar Checker · Ollama & Groq · 8-dimension humanness scoring</div>
</div>""", unsafe_allow_html=True)

# ── TABS ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["✍️  Humanizer", "🔄  Paraphraser", "✅  Grammar Checker"])
scores_in = {}
scores_out = {}

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — HUMANIZER
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    col_in, col_out = st.columns([1,1], gap="large")

    with col_in:
        h1,h2 = st.columns([3,1])
        with h1: st.markdown('<div class="card-title">📄 Input Text</div>', unsafe_allow_html=True)
        with h2:
            components.html("""<!DOCTYPE html><html><body style="margin:0;padding:4px 0 0;background:transparent;">
<button onclick="if(navigator.clipboard&&navigator.clipboard.readText){navigator.clipboard.readText().then(function(t){
  var f=window.parent.document.querySelectorAll('textarea');
  for(var i=0;i<f.length;i++){var n=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
    n.call(f[i],t);f[i].dispatchEvent(new Event('input',{bubbles:true}));break;}
}).catch(function(){alert('Use Ctrl+V / Cmd+V in the text box');});}
else{alert('Use Ctrl+V / Cmd+V in the text box');}"
style="background:#1a3a2e;color:#6fcf97;border:1px solid #4a7c59;border-radius:7px;
       padding:0.3rem 0.8rem;cursor:pointer;font-size:0.76rem;font-family:'DM Sans',sans-serif;
       width:100%;white-space:nowrap;">📋 Paste</button>
</body></html>""", height=40, scrolling=False)

        input_text = st.text_area("Input", height=350,
            placeholder="Paste AI-generated text here (5000+ words supported)…",
            label_visibility="collapsed", key="input_text")

        wc_in = len(input_text.split()) if input_text.strip() else 0
        bc,cc = st.columns([3,1])
        with bc: st.markdown(f'<span class="wc-badge">📝 {wc_in:,} words</span>', unsafe_allow_html=True)
        with cc:
            if st.button("🗑️ Clear", key="clear_btn", use_container_width=True, disabled=(not input_text.strip())):
                st.session_state.clear_input=True; st.rerun()

        if input_text.strip():
            scores_in = compute_scores(input_text)
            st.markdown('<p style="color:#c9a84c;font-weight:700;margin-top:0.6rem;">Before — Humanness</p>', unsafe_allow_html=True)
            r1,r2,r3,r4=st.columns(4)
            with r1: st.markdown(render_score_ring(scores_in["humanness"],"Humanness"),unsafe_allow_html=True)
            with r2: st.markdown(render_score_ring(scores_in["flesch"],"Readability"),unsafe_allow_html=True)
            with r3: st.markdown(render_score_ring(scores_in["ttr"],"Lexical Div"),unsafe_allow_html=True)
            with r4: st.markdown(render_score_ring(scores_in["sl_variation"],"Rhythm"),unsafe_allow_html=True)
            st.markdown(render_metrics(scores_in), unsafe_allow_html=True)

    with col_out:
        st.markdown('<div class="card-title">✨ Humanized Output</div>', unsafe_allow_html=True)
        output_text = st.session_state.output_text
        stream_placeholder = st.empty()

        if output_text.strip():
            import html as _html
            stream_placeholder.markdown(
                f'<div class="output-box">{_html.escape(output_text)}</div>',
                unsafe_allow_html=True)
            make_copy_btn("humanizer-out", output_text, "📋 Copy Text")
            scores_out = compute_scores(output_text)
            wc_out = scores_out.get("word_count",0)
            st.markdown(f'<span class="wc-badge">📝 {wc_out:,} words</span>', unsafe_allow_html=True)
            st.markdown('<p style="color:#c9a84c;font-weight:700;margin-top:0.6rem;">After — Humanness</p>', unsafe_allow_html=True)
            r1,r2,r3,r4=st.columns(4)
            with r1: st.markdown(render_score_ring(scores_out["humanness"],"Humanness"),unsafe_allow_html=True)
            with r2: st.markdown(render_score_ring(scores_out["flesch"],"Readability"),unsafe_allow_html=True)
            with r3: st.markdown(render_score_ring(scores_out["ttr"],"Lexical Div"),unsafe_allow_html=True)
            with r4: st.markdown(render_score_ring(scores_out["sl_variation"],"Rhythm"),unsafe_allow_html=True)
            st.markdown(render_metrics(scores_out), unsafe_allow_html=True)
        else:
            stream_placeholder.markdown(
                '''<div style="background:white;border:1.5px dashed #d4c9b5;border-radius:10px;
                   min-height:380px;display:flex;align-items:center;justify-content:center;
                   flex-direction:column;gap:0.6rem;color:#9a8a7a;">
                 <div style="font-size:2rem;">✨</div>
                 <div style="font-size:0.9rem;">Humanized text streams here in real-time</div>
               </div>''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    btn_c, info_c = st.columns([2,3])
    with btn_c:
        run_btn = st.button("⚡ Humanize (Streaming)", type="primary",
                            use_container_width=True, disabled=(not input_text.strip()))
    with info_c:
        if not groq_key:
            st.warning("🔑 Add your Groq API key in the sidebar")
        elif not input_text.strip():
            st.info("📄 Paste text above to begin.")
        else:
            chunks = chunk_text(input_text)
            st.markdown(
                f'<div class="wc-badge">⚡ {len(chunks)} chunk(s) · {GROQ_MODELS[model_choice].split(" · ")[0]} · {intensity}</div>',
                unsafe_allow_html=True)

    if run_btn:
        if not groq_key:
            st.error("🔑 Please add your Groq API key in the sidebar.")
        elif not input_text.strip():
            st.error("Please enter text.")
        else:
            try:
                chunks  = chunk_text(input_text)
                n       = len(chunks)
                results = []
                progress_bar = st.progress(0, text="Starting stream…")
                for i, chunk in enumerate(chunks):
                    progress_bar.progress(i/n, text=f"⚡ Streaming chunk {i+1}/{n}…")
                    if n > 1:
                        temp_ph = st.empty()
                        text_out = humanize_streaming(groq_key, model_choice, chunk, style, intensity, temp_ph)
                        temp_ph.empty()
                    else:
                        text_out = humanize_streaming(groq_key, model_choice, chunk, style, intensity, stream_placeholder)
                    results.append(text_out)
                progress_bar.progress(1.0, text="✅ Complete!")
                st.session_state.output_text = "\n\n".join(results)
                time.sleep(0.3)
                st.rerun()
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    st.error("⚠️ Groq rate limit. Wait 1 minute and try again.")
                elif e.response.status_code == 401:
                    st.error("❌ Invalid Groq API key.")
                else:
                    st.error(f"❌ HTTP Error: {e}")
            except Exception as e:
                st.error(f"❌ {str(e)}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PARAPHRASER
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="card-title">🔄 Paraphraser</div>', unsafe_allow_html=True)
    p1,p2 = st.columns([1,1], gap="large")
    with p1:
        st.markdown('<p style="color:#c9a84c;font-weight:700;">Input</p>', unsafe_allow_html=True)
        para_input = st.text_area("Para",height=300,placeholder="Paste text to paraphrase…",
                                  label_visibility="collapsed",key="para_input")
        pm,pb = st.columns([2,1])
        with pm: para_mode=st.selectbox("Mode",list(PARAPHRASE_MODES.keys()),label_visibility="collapsed",key="para_mode")
        with pb: para_btn=st.button("🔄 Paraphrase",type="primary",use_container_width=True,disabled=(not para_input.strip()))
        if para_input.strip():
            st.markdown(f'<span class="wc-badge">📝 {len(para_input.split()):,} words</span>',unsafe_allow_html=True)
    with p2:
        st.markdown('<p style="color:#c9a84c;font-weight:700;">Output</p>', unsafe_allow_html=True)
        para_out = st.session_state.paraphrase_out
        if para_out.strip():
            import html as _html
            st.markdown(f'<div class="output-box-sm">{_html.escape(para_out)}</div>',unsafe_allow_html=True)
            make_copy_btn("para-out",para_out,"📋 Copy")
            st.markdown(f'<span class="wc-badge">📝 {len(para_out.split()):,} words</span>',unsafe_allow_html=True)
        else:
            st.markdown('''<div style="background:white;border:1.5px dashed #d4c9b5;border-radius:10px;
                min-height:300px;display:flex;align-items:center;justify-content:center;
                flex-direction:column;gap:0.5rem;color:#9a8a7a;">
              <div style="font-size:2rem;">🔄</div><div style="font-size:0.9rem;">Paraphrased text here</div>
            </div>''', unsafe_allow_html=True)
    if para_btn:
        if not groq_key: st.error("🔑 Add Groq API key in sidebar.")
        else:
            with st.spinner(f"Paraphrasing ({para_mode})…"):
                try:
                    result = paraphrase_text(groq_key,model_choice,para_input,para_mode)
                    st.session_state.paraphrase_out = result
                    st.rerun()
                except Exception as e: st.error(f"❌ {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — GRAMMAR CHECKER
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="card-title">✅ Grammar & Style Checker</div>', unsafe_allow_html=True)
    g1,g2 = st.columns([1,1], gap="large")
    with g1:
        st.markdown('<p style="color:#c9a84c;font-weight:700;">Input</p>', unsafe_allow_html=True)
        gram_input = st.text_area("Grammar",height=300,
            placeholder="Paste text to proofread…",label_visibility="collapsed",key="gram_input")
        gram_btn = st.button("✅ Check Grammar",type="primary",use_container_width=True,disabled=(not gram_input.strip()))
        if gram_input.strip():
            st.markdown(f'<span class="wc-badge">📝 {len(gram_input.split()):,} words</span>',unsafe_allow_html=True)
    with g2:
        st.markdown('<p style="color:#c9a84c;font-weight:700;">Corrected Text</p>', unsafe_allow_html=True)
        gram_corrected = st.session_state.grammar_corrected
        if gram_corrected.strip():
            import html as _html
            st.markdown(f'<div style="background:white;border:1.5px solid #4a7c59;border-radius:10px;padding:1rem 1.2rem;height:220px;overflow-y:auto;font-family:DM Sans,sans-serif;font-size:0.9rem;line-height:1.7;color:#1a1a2e;white-space:pre-wrap;word-break:break-word;">{_html.escape(gram_corrected)}</div>',unsafe_allow_html=True)
            make_copy_btn("gram-out",gram_corrected,"📋 Copy Corrected","#6fcf97","#1a3a2e","#4a7c59")
            issues = st.session_state.grammar_issues
            if issues:
                st.markdown(f'<p style="color:#c9a84c;font-weight:700;margin-top:0.8rem;">⚠️ {len(issues)} Issue(s)</p>',unsafe_allow_html=True)
                type_colors={"grammar":"#e87a7a","spelling":"#e8a87a","punctuation":"#e8d47a",
                             "style":"#a8d47a","wordiness":"#7ab8e8","clarity":"#b87ae8"}
                for iss in issues:
                    t=iss.get("type","other"); tc=type_colors.get(t,"#aaa")
                    orig=_html.escape(iss.get("original","")); corr=_html.escape(iss.get("corrected",""))
                    expl=_html.escape(iss.get("explanation",""))
                    st.markdown(f'''<div style="background:white;border-left:4px solid {tc};border-radius:0 8px 8px 0;
                         padding:0.6rem 0.9rem;margin-bottom:0.4rem;">
                      <span style="background:{tc}22;color:{tc};border-radius:4px;padding:0.1rem 0.4rem;
                             font-size:0.68rem;font-weight:700;text-transform:uppercase;">{t}</span>
                      <div style="font-size:0.82rem;color:#5a6a7a;margin-top:0.3rem;">
                        <span style="color:#e87a7a;text-decoration:line-through;">{orig}</span>
                        <span style="margin:0 0.3rem;">→</span>
                        <span style="color:#4a7c59;font-weight:600;">{corr}</span>
                      </div>
                      <div style="font-size:0.75rem;color:#7a8a9a;margin-top:0.2rem;">{expl}</div>
                    </div>''', unsafe_allow_html=True)
            else:
                st.markdown('<p style="color:#6fcf97;font-weight:600;">✅ No issues — text looks great!</p>',unsafe_allow_html=True)
        else:
            st.markdown('''<div style="background:white;border:1.5px dashed #d4c9b5;border-radius:10px;
                min-height:300px;display:flex;align-items:center;justify-content:center;
                flex-direction:column;gap:0.5rem;color:#9a8a7a;">
              <div style="font-size:2rem;">✅</div><div style="font-size:0.9rem;">Grammar report here</div>
            </div>''', unsafe_allow_html=True)
    if gram_btn:
        if not groq_key: st.error("🔑 Add Groq API key in sidebar.")
        else:
            with st.spinner("Checking grammar…"):
                try:
                    result=grammar_check(groq_key,model_choice,gram_input)
                    st.session_state.grammar_corrected=result.get("corrected","")
                    st.session_state.grammar_issues=result.get("issues",[])
                    st.rerun()
                except Exception as e: st.error(f"❌ {e}")

# ══════════════════════════════════════════════════════════════════════════════
# COMPARISON PANEL
# ══════════════════════════════════════════════════════════════════════════════
if scores_in and scores_out:
    st.markdown("---")
    st.markdown('<div class="card-title" style="font-size:1.1rem;">📊 Before vs After</div>', unsafe_allow_html=True)
    delta=scores_out["humanness"]-scores_in["humanness"]
    delta_sign="+" if delta>=0 else ""
    delta_color="#6fcf97" if delta>=0 else "#e87a7a"
    st.markdown(f"""<div class="improvement-banner">
      <div class="score-delta" style="color:{delta_color};">{delta_sign}{delta:.1f}</div>
      <div class="score-desc"><b>Humanness Score Change</b><br>
        Before: <b>{scores_in['humanness']}</b> → After: <b>{scores_out['humanness']}</b><br>
        {style} · {intensity} · {GROQ_MODELS.get(model_choice,model_choice)}</div>
    </div>""", unsafe_allow_html=True)
    metrics=[("Humanness","humanness","Higher = more natural"),
             ("Flesch","flesch","Higher = easier"),
             ("Lexical Div","ttr","Higher = richer vocab"),
             ("Rhythm Var","sl_variation","Higher = more varied"),
             ("Burstiness","burstiness","Higher = human rhythm"),
             ("Passive Voice","passive_score","Higher = active voice"),
             ("Transitions","transition_score","Higher = better flow"),
             ("Grade Level","grade_level","Lower = accessible")]
    c1,c2,c3,c4=st.columns(4)
    cols=[c1,c2,c3,c4]
    for idx,(label,key,hint) in enumerate(metrics):
        vb=scores_in.get(key,0); va=scores_out.get(key,0); d=va-vb
        sign="+" if d>=0 else ""
        cd="#6fcf97" if d>=0 else "#e87a7a"
        if key=="grade_level": cd="#6fcf97" if d<=0 else "#e87a7a"
        with cols[idx%4]:
            st.markdown(f"""<div style="background:white;border:1px solid #d4c9b5;border-radius:10px;
                  padding:0.8rem;margin-bottom:0.7rem;text-align:center;">
              <div style="font-size:0.68rem;color:#5a6a7a;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:0.4rem;">{label}</div>
              <div style="display:flex;justify-content:space-around;align-items:center;">
                <div><div style="font-size:1.2rem;font-weight:700;color:#1a1a2e;">{vb}</div>
                     <div style="font-size:0.65rem;color:#9a8a7a;">Before</div></div>
                <div style="color:#c9a84c;">→</div>
                <div><div style="font-size:1.2rem;font-weight:700;color:#1a1a2e;">{va}</div>
                     <div style="font-size:0.65rem;color:#9a8a7a;">After</div></div>
              </div>
              <div style="font-size:0.8rem;font-weight:700;color:{cd};margin-top:0.3rem;">{sign}{d:.1f}</div>
              <div style="font-size:0.63rem;color:#9a8a7a;margin-top:0.1rem;">{hint}</div>
            </div>""", unsafe_allow_html=True)
    dc,_,_ = st.columns([1,1,1])
    with dc:
        st.download_button("⬇️ Download Output", data=st.session_state.output_text,
                           file_name="humanized_output.txt", mime="text/plain",
                           use_container_width=True)
