from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st


def _background_data_uri() -> str | None:
    path = Path("/Users/avinash/Documents/1.jpg")
    if not path.exists():
        return None
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{data}"


def _watermark_data_uri() -> str | None:
    path = Path(__file__).resolve().parent / "assets" / "indian_emblem_watermark.jpg"
    if not path.exists():
        return None
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{data}"


def inject_global_styles():
    font_scale = float(st.session_state.get("font_scale", 1.0))
    high_contrast = bool(st.session_state.get("high_contrast", False))

    navy = "#0A2647" if not high_contrast else "#000000"
    accent = "#FF9933"
    green = "#138808"
    bg = "#F4F6F9" if not high_contrast else "#ffffff"
    text = "#0A2647" if not high_contrast else "#000000"
    muted = "#4b5d73" if not high_contrast else "#1b1b1b"
    border = "#cfd8e3" if not high_contrast else "#000000"
    footer_bg = "#07203a" if not high_contrast else "#000000"

    bg_uri = _background_data_uri()
    bg_css = f"background-image: url('{bg_uri}');" if bg_uri else ""
    watermark_uri = _watermark_data_uri()
    watermark_css = f"background-image: url('{watermark_uri}');" if watermark_uri else ""

    st.markdown(
        f"""
        <style>
        /* ── Google Fonts ── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap');

        /* ── Design tokens ── */
        :root {{
            --navy: {navy};
            --accent: {accent};
            --green: {green};
            --bg: {bg};
            --text: {text};
            --muted: {muted};
            --border: {border};
            --footer: {footer_bg};
            --card-radius: 8px;
            --shadow-sm: 0 2px 8px rgba(10,38,71,0.04);
            --shadow-md: 0 8px 24px rgba(10,38,71,0.06);
            --shadow-lg: 0 16px 40px rgba(10,38,71,0.08);
            --transition: 0.2s ease;
        }}

        /* ── Base reset ── */
        html {{
            font-size: {16 * font_scale}px;
        }}
        body, .stApp {{
            background-color: var(--bg) !important;
            color: var(--text) !important;
            font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
        }}

        /* ── Hide Streamlit chrome ── */
        #MainMenu {{ visibility: hidden; }}
        header[data-testid="stHeader"] {{ background: transparent !important; }}
        footer {{ visibility: hidden !important; }}
        [data-testid="stDecoration"] {{ display: none !important; }}
        .stDeployButton {{ display: none !important; }}

        /* ── Background image layer (::before) ── */
        body::before {{
            content: "";
            position: fixed;
            inset: 0;
            {bg_css}
            background-position: center right;
            background-repeat: no-repeat;
            background-size: cover;
            opacity: 0.06;
            pointer-events: none;
            z-index: 0;
        }}

        /* ── Watermark layer (::after — separate from background) ── */
        .stApp::after {{
            content: "";
            position: fixed;
            inset: 0;
            {watermark_css}
            background-position: center center;
            background-repeat: no-repeat;
            background-size: 32vw;
            opacity: 0.04;
            pointer-events: none;
            z-index: 0;
        }}

        .block-container {{
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
            position: relative;
            z-index: 1;
        }}

        /* ── Links ── */
        a {{ color: var(--navy); text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}

        /* ── Skip link (accessibility) ── */
        .skip-link {{
            position: absolute; left: -999px; top: 8px;
            background: var(--accent); color: #111827;
            padding: 0.4rem 0.75rem; font-weight: 600;
            border: 1px solid #b45309; z-index: 9999;
        }}
        .skip-link:focus {{ left: 16px; }}

        /* ═══════════════════════════════════════════
           GOVERNMENT HEADER SYSTEM
           ═══════════════════════════════════════════ */

        /* ── Tricolor ribbon (decorative top border) ── */
        .gov-tricolor {{
            height: 4px;
            background: linear-gradient(to right, {accent} 33.3%, #ffffff 33.3%, #ffffff 66.6%, {green} 66.6%);
        }}

        /* ── Top strip ── */
        .gov-topstrip {{
            background: var(--navy) !important;
            color: #ffffff;
            padding: 0.45rem 1.5rem;
            font-size: 0.88rem;
            border-bottom: 2px solid {accent};
            position: relative; z-index: 1;
        }}
        .gov-topstrip-inner {{
            display: flex; align-items: center;
            justify-content: space-between; gap: 1rem;
            max-width: 1200px; margin: 0 auto;
        }}
        .gov-strip-tools {{
            display: flex; gap: 0.35rem; align-items: center;
            font-size: 0.82rem; opacity: 0.9;
        }}

        /* ── Main header ── */
        .gov-header {{
            background: #ffffff !important;
            border-bottom: 4px solid transparent !important;
            border-image: linear-gradient(to right, {accent} 33.3%, #ffffff 33.3%, #ffffff 66.6%, {green} 66.6%) 1 !important;
            box-shadow: var(--shadow-sm) !important;
            position: relative; z-index: 1;
        }}
        .gov-header-inner {{
            max-width: 1200px; margin: 0 auto;
            padding: 0.85rem 1.5rem;
            display: flex; justify-content: space-between;
            align-items: center; gap: 1rem; flex-wrap: wrap;
        }}
        .gov-brand {{
            display: flex; gap: 0.9rem; align-items: center;
        }}
        .gov-emblem {{
            width: 56px; height: 56px; object-fit: contain;
            filter: drop-shadow(0 1px 2px rgba(0,0,0,0.1));
        }}
        .gov-title-hi {{
            font-family: 'Noto Sans Devanagari', 'Inter', sans-serif;
            font-weight: 700; font-size: 1.1rem; color: var(--navy);
        }}
        .gov-title-en {{
            font-weight: 600; font-size: 0.92rem; color: var(--muted);
        }}
        .gov-title-sub {{
            font-size: 0.82rem; color: var(--muted); letter-spacing: 0.02em;
        }}

        /* ── Navigation bar ── */
        .gov-nav {{
            background: #0B1D33 !important;
            border-bottom: 3px solid {green} !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
            position: relative; z-index: 1;
        }}
        .gov-nav-inner {{
            max-width: 1200px; margin: 0 auto;
            padding: 0.4rem 1.5rem;
            display: flex; justify-content: space-between;
            align-items: center; gap: 1rem; flex-wrap: wrap;
        }}
        .gov-nav ul {{
            list-style: none; display: flex;
            gap: 1.5rem; padding: 0; margin: 0; color: #ffffff;
        }}
        .gov-nav li {{
            position: relative; font-size: 0.92rem;
            font-weight: 500; cursor: pointer;
            padding: 0.35rem 0;
        }}
        .gov-nav li::after {{
            content: ''; display: block;
            width: 0; height: 2px; margin-top: 2px;
            background: var(--accent);
            transition: width 0.3s ease;
        }}
        .gov-nav li:hover::after {{ width: 100%; }}
        .gov-nav li:hover {{ color: var(--accent) !important; }}
        .gov-nav a {{ color: #ffffff; text-decoration: none; }}
        .gov-nav a:hover {{ color: var(--accent); text-decoration: none; }}
        .gov-nav .dropdown {{
            position: absolute; top: 2rem; left: 0;
            background: #ffffff; color: #0f172a;
            min-width: 200px; border: 1px solid var(--border);
            border-radius: 6px; padding: 0.5rem 0;
            display: none; z-index: 10;
            box-shadow: var(--shadow-lg);
        }}
        .gov-nav li:hover .dropdown {{ display: block; }}
        .gov-nav .dropdown a {{
            color: #0f172a; display: block;
            padding: 0.5rem 1rem; font-size: 0.88rem;
            transition: background var(--transition);
        }}
        .gov-nav .dropdown a:hover {{
            background: rgba(10,38,71,0.04); text-decoration: none;
        }}

        /* ── Search box in nav ── */
        .gov-search {{
            display: flex; align-items: center;
            gap: 0.4rem; background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px; padding: 0.3rem 0.6rem;
            transition: all var(--transition);
        }}
        .gov-search:focus-within {{
            background: rgba(255,255,255,0.15);
            border-color: var(--accent);
        }}
        .gov-search input {{
            border: none; outline: none;
            font-size: 0.88rem; width: 160px;
            background: transparent; color: #ffffff;
        }}
        .gov-search input::placeholder {{ color: rgba(255,255,255,0.5); }}

        /* ═══════════════════════════════════════════
           HERO SECTION
           ═══════════════════════════════════════════ */
        .gov-hero {{
            max-width: 1200px; margin: 1.5rem auto;
            min-height: 320px; border-radius: var(--card-radius);
            background-size: cover; background-position: center;
            position: relative; overflow: hidden;
            box-shadow: var(--shadow-lg);
        }}
        .gov-hero-overlay {{
            position: absolute; inset: 0;
            background: linear-gradient(135deg, rgba(10,38,71,0.75), rgba(11,29,51,0.55));
        }}
        .gov-hero-content {{
            position: relative; padding: 2.5rem;
            max-width: 640px; color: #ffffff;
        }}
        .gov-hero-title {{
            font-size: 2.2rem; font-weight: 700;
            margin-bottom: 0.7rem; line-height: 1.2;
            letter-spacing: -0.01em;
        }}
        .gov-hero-text {{
            font-size: 1.02rem; margin-bottom: 1.2rem;
            line-height: 1.6; opacity: 0.92;
        }}

        /* ── CTA buttons in hero ── */
        .gov-cta {{
            display: inline-block;
            background: var(--accent); color: #ffffff;
            padding: 0.55rem 1.2rem;
            border: none; border-radius: 6px;
            font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.04em; font-size: 0.88rem;
            transition: all var(--transition);
            text-decoration: none;
            box-shadow: 0 4px 12px rgba(255,153,51,0.3);
        }}
        .gov-cta:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 18px rgba(255,153,51,0.4);
            text-decoration: none; color: #ffffff;
        }}
        .gov-cta.secondary {{
            background: rgba(255,255,255,0.15);
            backdrop-filter: blur(4px);
            color: #ffffff; border: 1px solid rgba(255,255,255,0.3);
            box-shadow: none;
        }}
        .gov-cta.secondary:hover {{
            background: rgba(255,255,255,0.25);
            box-shadow: 0 4px 12px rgba(255,255,255,0.1);
        }}

        /* ═══════════════════════════════════════════
           CARDS
           ═══════════════════════════════════════════ */
        .gov-card, .glass-card {{
            background: #ffffff; border: 1px solid var(--border);
            border-radius: var(--card-radius); padding: 1.1rem 1.2rem;
            box-shadow: var(--shadow-sm);
            transition: transform var(--transition), box-shadow var(--transition);
        }}
        .gov-card:hover, .glass-card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }}
        .portal-card {{
            background: #ffffff; border: 1px solid var(--border);
            border-top: 4px solid {accent};
            border-radius: var(--card-radius);
            padding: 1.3rem 1.4rem;
            box-shadow: var(--shadow-md);
            transition: transform var(--transition), box-shadow var(--transition);
        }}
        .portal-card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }}
        .metric-card {{
            background: #ffffff; border: 1px solid var(--border);
            border-left: 5px solid {green};
            border-radius: var(--card-radius);
            padding: 1.1rem 1.2rem;
            box-shadow: var(--shadow-sm);
            transition: all var(--transition);
        }}
        .metric-card:hover {{
            border-left-width: 7px;
            box-shadow: var(--shadow-md);
        }}

        /* ── Section titles ── */
        .section-title {{
            font-size: 1.08rem; font-weight: 700;
            color: var(--navy); margin-bottom: 0.7rem;
            letter-spacing: -0.01em;
        }}

        /* ── Upload box ── */
        .upload-box {{
            border: 2px dashed var(--border);
            border-radius: var(--card-radius);
            padding: 1rem; text-align: center;
            background: rgba(10,38,71,0.015);
            margin-bottom: 0.8rem;
            transition: all var(--transition);
        }}
        .upload-box:hover {{
            border-color: var(--accent);
            background: rgba(255,153,51,0.02);
        }}

        /* ═══════════════════════════════════════════
           BADGES & PILLS
           ═══════════════════════════════════════════ */
        .avisens-badge {{
            display: inline-block;
            padding: 0.22rem 0.55rem;
            border-radius: 4px;
            font-size: 0.78rem; font-weight: 700;
            margin: 0.12rem 0.25rem 0.12rem 0;
            letter-spacing: 0.03em;
            border: 1px solid transparent;
        }}
        .badge-green {{ background: #e8f5e9; color: #2e7d32; border-color: #a5d6a7; }}
        .badge-yellow {{ background: #fff8e1; color: #e65100; border-color: #ffe082; }}
        .badge-red {{ background: #ffebee; color: #c62828; border-color: #ef9a9a; }}
        .badge-blue {{ background: #e3f2fd; color: #1565c0; border-color: #90caf9; }}
        .badge-slate {{ background: #f1f5f9; color: #334155; border-color: #e2e8f0; }}

        .status-pill {{
            font-size: 0.78rem; padding: 0.22rem 0.65rem;
            border-radius: 20px; border: 1px solid var(--border);
            color: var(--text); background: #f8fafc;
            font-weight: 600;
        }}

        /* ── Field labels / helper text ── */
        .field-label {{
            color: var(--muted); font-size: 0.82rem;
            letter-spacing: 0.04em; text-transform: uppercase;
            font-weight: 600;
        }}
        .ghost-note {{
            color: var(--muted); font-size: 0.92rem;
            padding: 1rem 0;
        }}

        /* ═══════════════════════════════════════════
           STREAMLIT WIDGET OVERRIDES
           ═══════════════════════════════════════════ */

        /* ── Buttons ── */
        .stButton > button {{
            border-radius: 8px !important;
            transition: all var(--transition) !important;
            font-weight: 600 !important;
            border: 1.5px solid var(--navy) !important;
            color: var(--navy) !important;
            background-color: #ffffff !important;
        }}
        .stButton > button:hover {{
            background-color: var(--navy) !important;
            color: #ffffff !important;
            box-shadow: 0 4px 14px rgba(10,38,71,0.18) !important;
        }}
        .stButton > button[kind="primary"],
        .stFormSubmitButton > button {{
            background: linear-gradient(135deg, {accent}, #e67e22) !important;
            color: #ffffff !important;
            border: none !important;
            font-weight: 700 !important;
            box-shadow: 0 4px 12px rgba(255,153,51,0.25) !important;
            letter-spacing: 0.02em !important;
        }}
        .stButton > button[kind="primary"]:hover,
        .stFormSubmitButton > button:hover {{
            box-shadow: 0 6px 18px rgba(255,153,51,0.4) !important;
            transform: translateY(-1px) !important;
        }}

        /* ── File Uploader ── */
        .stFileUploader section {{
            border: 2px dashed var(--navy) !important;
            background-color: rgba(10,38,71,0.015) !important;
            border-radius: var(--card-radius) !important;
            padding: 1.2rem !important;
            transition: all var(--transition) !important;
        }}
        .stFileUploader section:hover {{
            background-color: rgba(10,38,71,0.03) !important;
            border-color: var(--accent) !important;
        }}
        /* Browse / upload button — always visible */
        .stFileUploader button,
        .stFileUploader [role="button"],
        .stFileUploader [data-testid="stBaseButton-secondary"],
        [data-testid="stFileUploader"] button,
        [data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"],
        .stFileUploader small + div button {{
            opacity: 1 !important;
            visibility: visible !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            color: var(--navy) !important;
            background-color: #ffffff !important;
            border: 1.5px solid var(--navy) !important;
            padding: 0.45rem 1.1rem !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
            transition: all var(--transition) !important;
            cursor: pointer !important;
        }}
        .stFileUploader button:hover,
        .stFileUploader [role="button"]:hover,
        .stFileUploader [data-testid="stBaseButton-secondary"]:hover,
        [data-testid="stFileUploader"] button:hover,
        [data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"]:hover {{
            background-color: var(--navy) !important;
            color: #ffffff !important;
            box-shadow: 0 4px 14px rgba(10,38,71,0.18) !important;
        }}

        /* ── Help tooltip icon — always visible ── */
        .stTooltipIcon,
        [data-testid="stTooltipIcon"],
        .stTooltipHoverTarget,
        .stTooltipHoverTarget svg,
        [data-testid="stTooltipIcon"] svg,
        div[data-testid="stTooltipIcon"] {{
            opacity: 1 !important;
            visibility: visible !important;
            color: var(--navy) !important;
            fill: var(--navy) !important;
        }}

        /* ── Text inputs ── */
        .stTextInput input, .stTextArea textarea {{
            padding: 0.65rem 0.8rem !important;
            border-radius: 8px !important;
            border: 1.5px solid var(--border) !important;
            background: #ffffff !important;
            color: var(--text) !important;
            font-size: 0.92rem !important;
            transition: border-color var(--transition), box-shadow var(--transition) !important;
        }}
        .stTextInput input:focus, .stTextArea textarea:focus {{
            outline: none !important;
            border-color: var(--navy) !important;
            box-shadow: 0 0 0 3px rgba(10,38,71,0.08) !important;
        }}

        /* ── Selectbox & Multiselect ── */
        .stSelectbox > div > div,
        .stMultiSelect > div > div {{
            border-radius: 8px !important;
            border-color: var(--border) !important;
        }}
        .stSelectbox [data-baseweb="select"],
        .stMultiSelect [data-baseweb="select"] {{
            border-radius: 8px !important;
        }}

        /* ── Slider ── */
        .stSlider [data-baseweb="slider"] [role="slider"] {{
            background-color: var(--navy) !important;
            border-color: var(--navy) !important;
        }}
        .stSlider [data-testid="stThumbValue"] {{
            color: var(--navy) !important;
            font-weight: 700 !important;
        }}

        /* ── Portal layout grid ── */
        .portal-grid {{
            display: grid;
            grid-template-columns: 3fr 2fr;
            gap: 1.5rem; margin-top: 1.2rem;
        }}
        @media (max-width: 1100px) {{
            .portal-grid {{ grid-template-columns: 1fr !important; }}
        }}

        /* ── Analysis placeholder ── */
        .analysis-placeholder {{
            display: grid !important; gap: 0.8rem !important;
            color: var(--muted) !important; font-size: 0.98rem !important;
            align-items: center; justify-items: center;
            padding: 2rem 0.4rem;
        }}

        /* ── History rows ── */
        .history-header {{
            display: grid;
            grid-template-columns: 1.1fr 1fr 1.2fr 0.8fr 0.9fr;
            gap: 0.8rem; font-size: 0.8rem; font-weight: 700;
            color: var(--muted); text-transform: uppercase;
            margin: 1.2rem 0 0.5rem 0;
        }}
        .history-row {{
            display: grid;
            grid-template-columns: 1.1fr 1fr 1.2fr 0.8fr 0.9fr;
            gap: 0.8rem; align-items: center;
            padding: 0.65rem 0.4rem;
            border-bottom: 1px solid var(--border);
        }}
        .history-thumb {{
            width: 56px; height: 42px;
            border-radius: 8px; object-fit: cover;
            border: 1px solid var(--border);
        }}

        /* ═══════════════════════════════════════════
           FOOTER
           ═══════════════════════════════════════════ */
        .gov-footer {{
            background: #091c30 !important;
            color: #e2e8f0;
            padding: 2.5rem 1.5rem;
            margin-top: 2.5rem;
            border-top: 4px solid {accent};
            position: relative; z-index: 1;
        }}
        .gov-footer-inner {{
            max-width: 1200px; margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1.5rem;
        }}
        .gov-footer h4 {{
            font-size: 0.95rem; margin-bottom: 0.7rem;
            color: #ffffff; letter-spacing: 0.02em;
        }}
        .gov-footer a {{
            color: rgba(255,255,255,0.7); font-size: 0.85rem;
            display: block; margin-bottom: 0.4rem;
            transition: color var(--transition);
        }}
        .gov-footer a:hover {{
            color: var(--accent); text-decoration: none;
        }}
        .visitor-count {{
            background: #040c14;
            padding: 0.45rem 0.7rem;
            border: 1px solid #102a45;
            display: inline-block; margin-top: 0.5rem;
            font-weight: 600; color: #26a69a;
            font-family: 'Courier New', monospace;
            font-size: 1.1rem; letter-spacing: 3px;
            border-radius: 4px;
        }}

        /* ── Gov list (used in footer etc) ── */
        .gov-list {{
            list-style: none; padding: 0; margin: 0;
        }}
        .gov-list li {{
            display: flex; justify-content: space-between;
            padding: 0.5rem 0; border-bottom: 1px solid var(--border);
            font-size: 0.95rem;
        }}
        .gov-list span {{
            color: var(--muted); font-size: 0.85rem;
        }}

        /* ── Responsive ── */
        @media (max-width: 900px) {{
            .gov-header-inner, .gov-nav-inner {{
                flex-direction: column; align-items: flex-start;
            }}
            .gov-hero-content {{ padding: 1.8rem; }}
            .gov-hero-title {{ font-size: 1.6rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def severity_badge(label: str, severity_class: str | None = None) -> str:
    sev = (label or "").strip().lower()
    cls = "badge-slate"
    if sev == "green":
        cls = "badge-green"
    elif sev == "yellow":
        cls = "badge-yellow"
    elif sev == "red":
        cls = "badge-red"
    suffix = f" · {severity_class}" if severity_class else ""
    return f'<span class="avisens-badge {cls}">{label or "Unknown"}{suffix}</span>'


def role_badge(role: str) -> str:
    return f'<span class="avisens-badge badge-blue">{role}</span>'


def location_tags(lat: str | None, lon: str | None, source: str = "citizen", description: str | None = None):
    tags = []
    if lat and lon:
        tags.append(("GPS", f"{lat}, {lon}"))
        try:
            map_q = urlencode({"q": f"{lat},{lon}"})
            tags.append(("Map", f"https://www.google.com/maps/search/?api=1&{map_q}"))
        except Exception:
            pass
    if description:
        tags.append(("Note", description.strip()[:42]))
    tags.append(("Source", source.title()))
    return tags


def chip_line(tags):
    parts = []
    for key, value in tags:
        if isinstance(value, str) and value.startswith("http"):
            parts.append(f'<a class="avisens-badge badge-blue" href="{value}" target="_blank">{key}: Open Map</a>')
        else:
            parts.append(f'<span class="avisens-badge badge-slate">{key}: {value}</span>')
    return "".join(parts)


def progress_text(score: float | None) -> str:
    if score is None:
        return "--"
    return f"{float(score):.1f} / 100"
