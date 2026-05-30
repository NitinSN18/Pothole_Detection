from __future__ import annotations

from urllib.parse import urlencode

import streamlit as st


def inject_global_styles():
    st.markdown(
        """
        <style>
        .stApp {
            background: radial-gradient(circle at top, #0f172a 0%, #071018 45%, #050b10 100%);
            color: #e5eef7;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .avisens-card {
            background: rgba(9, 15, 23, 0.88);
            border: 1px solid rgba(77, 128, 255, 0.18);
            border-radius: 18px;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
            padding: 1.15rem 1.2rem;
        }
        .avisens-hero {
            background: linear-gradient(135deg, rgba(20,28,44,0.96), rgba(7,16,24,0.88));
            border: 1px solid rgba(59, 130, 246, 0.25);
            border-radius: 28px;
            padding: 2.4rem 2rem;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.28);
        }
        .avisens-title {
            font-size: 3rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            margin-bottom: 0.2rem;
        }
        .avisens-tagline {
            font-size: 1.05rem;
            color: rgba(229, 238, 247, 0.82);
        }
        .avisens-badge {
            display: inline-block;
            padding: 0.32rem 0.72rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 700;
            margin: 0.12rem 0.25rem 0.12rem 0;
            border: 1px solid transparent;
        }
        .badge-green { background: rgba(16, 185, 129, 0.18); color: #8ef0be; border-color: rgba(16, 185, 129, 0.34); }
        .badge-yellow { background: rgba(245, 158, 11, 0.18); color: #fde68a; border-color: rgba(245, 158, 11, 0.34); }
        .badge-red { background: rgba(239, 68, 68, 0.18); color: #fca5a5; border-color: rgba(239, 68, 68, 0.34); }
        .badge-blue { background: rgba(59, 130, 246, 0.18); color: #bfdbfe; border-color: rgba(59, 130, 246, 0.34); }
        .badge-slate { background: rgba(148, 163, 184, 0.16); color: #e2e8f0; border-color: rgba(148, 163, 184, 0.25); }
        .stat-shell {
            background: rgba(10, 15, 24, 0.92);
            border: 1px solid rgba(120, 144, 156, 0.18);
            border-radius: 16px;
            padding: 1rem 1.1rem;
        }
        .card-image {
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .stButton > button {
            border-radius: 12px;
            border: 1px solid rgba(59, 130, 246, 0.3);
            background: linear-gradient(135deg, #1d4ed8, #2563eb);
            color: white;
            padding: 0.55rem 1rem;
            font-weight: 700;
        }
        .stButton > button:hover {
            border-color: rgba(96, 165, 250, 0.65);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def severity_badge(label: str) -> str:
    sev = (label or "").strip().lower()
    cls = "badge-slate"
    if sev == "green":
        cls = "badge-green"
    elif sev == "yellow":
        cls = "badge-yellow"
    elif sev == "red":
        cls = "badge-red"
    return f'<span class="avisens-badge {cls}">{label or "Unknown"}</span>'


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
