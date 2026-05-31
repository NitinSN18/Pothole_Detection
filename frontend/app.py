import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from frontend.authority.authority_dashboard import run as run_authority_dashboard
from frontend.citizen.citizen_dashboard import run as run_citizen_dashboard
from frontend.ui import inject_global_styles, role_badge


st.set_page_config(page_title="AVISENS", layout="wide", initial_sidebar_state="collapsed")
inject_global_styles()


def _init_state():
    st.session_state.setdefault("route", "landing")
    st.session_state.setdefault("user_role", None)
    st.session_state.setdefault("username", None)
    st.session_state.setdefault("font_scale", 1.0)
    st.session_state.setdefault("high_contrast", False)


def _rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    st.stop()


def _logout():
    for key in ["user_role", "username"]:
        st.session_state.pop(key, None)
    st.session_state.route = "landing"
    _rerun()


def _adjust_font(delta: float):
    updated = st.session_state.get("font_scale", 1.0) + delta
    st.session_state.font_scale = min(1.2, max(0.9, updated))
    _rerun()


def _toggle_contrast():
    st.session_state.high_contrast = not st.session_state.get("high_contrast", False)
    _rerun()


def _landing_page():
    st.markdown(
        """
        <a class="skip-link" href="#main-content">Skip to main content</a>
        <div class="gov-topstrip">
            <div class="gov-topstrip-inner">
                <div>भारत सरकार | Government of India</div>
                <div class="gov-strip-tools">
                    <span>Accessibility: Font Controls &amp; Contrast</span>
                </div>
            </div>
        </div>
        <div class="gov-header">
            <div class="gov-header-inner">
                <div class="gov-brand">
                    <img class="gov-emblem" src="https://upload.wikimedia.org/wikipedia/commons/5/55/Emblem_of_India.svg" alt="Indian National Emblem">
                    <div>
                        <div class="gov-title-hi">सड़क परिवहन और राजमार्ग मंत्रालय</div>
                        <div class="gov-title-en">Ministry of Road Transport &amp; Highways</div>
                        <div class="gov-title-sub">Government of India | AVISENS Road Accountability Platform</div>
                    </div>
                </div>
                <div class="gov-title-en">Ministry of Infrastructure Monitoring</div>
            </div>
        </div>
        <nav class="gov-nav" aria-label="Primary">
            <div class="gov-nav-inner">
                <ul>
                    <li><a href="#">Home</a></li>
                    <li>About
                        <div class="dropdown">
                            <a href="#">Ministry Overview</a>
                            <a href="#">Mission &amp; Vision</a>
                            <a href="#">Leadership</a>
                        </div>
                    </li>
                    <li>Services
                        <div class="dropdown">
                            <a href="#services">Citizen Reporting</a>
                            <a href="#services">RoadWatch Analytics</a>
                            <a href="#services">Municipal Response</a>
                        </div>
                    </li>
                    <li><a href="#contact">Contact</a></li>
                </ul>
                <div class="gov-search" role="search">
                    <span aria-hidden="true">🔍</span>
                    <input type="text" aria-label="Search portal" placeholder="Search the portal">
                </div>
            </div>
        </nav>
        """,
        unsafe_allow_html=True,
    )

    tools_label, tools_minus, tools_plus, tools_contrast = st.columns([2.5, 1, 1, 1.5])
    with tools_label:
        st.markdown("**Accessibility Tools**")
    with tools_minus:
        if st.button("A-", use_container_width=True):
            _adjust_font(-0.05)
    with tools_plus:
        if st.button("A+", use_container_width=True):
            _adjust_font(0.05)
    with tools_contrast:
        if st.button("High Contrast", use_container_width=True):
            _toggle_contrast()

    st.markdown(
        """
        <div class="gov-hero" id="main-content" style="background-image: url('https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=1600&q=80');">
            <div class="gov-hero-overlay"></div>
            <div class="gov-hero-content">
                <div class="gov-hero-title">AI-Powered Road Accountability Portal</div>
                <div class="gov-hero-text">
                    Transparent, data-driven road maintenance with real-time citizen reporting and municipal response tracking.
                </div>
                <a class="gov-cta" href="#services">Report a Road Issue</a>
                <a class="gov-cta secondary" href="#services" style="margin-left:0.5rem;">Authority Access</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div id="services"></div>', unsafe_allow_html=True)
    cta1, cta2 = st.columns([1, 1])
    with cta1:
        if st.button("Citizen Services Portal", use_container_width=True, type="primary"):
            st.session_state.route = "citizen_login"
            _rerun()
    with cta2:
        if st.button("Authority Login", use_container_width=True, type="primary"):
            st.session_state.route = "authority_login"
            _rerun()

    st.markdown(
        """
        <div class="gov-footer" id="contact">
            <div class="gov-footer-inner">
                <div>
                    <h4>Site Map</h4>
                    <a href="#">Home</a>
                    <a href="#services">Citizen Services</a>
                    <a href="#services">Authority Access</a>
                </div>
                <div>
                    <h4>Policies</h4>
                    <a href="#">Privacy Policy</a>
                    <a href="#">Hyperlinking Policy</a>
                    <a href="#">Copyright Policy</a>
                    <a href="#">Terms &amp; Conditions</a>
                </div>
                <div>
                    <h4>Help &amp; Accessibility</h4>
                    <a href="#">Accessibility Statement</a>
                    <a href="#">Screen Reader Access</a>
                    <a href="#">Contact Support</a>
                </div>
                <div>
                    <h4>Visitor Count</h4>
                    <div class="visitor-count">00256891</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _citizen_login():
    st.markdown(
        """
        <div style="max-width: 700px; margin: 3rem auto 1rem auto;">
            <div class="glass-card">
                <div style="margin-bottom: 0.6rem;">""",
        unsafe_allow_html=True,
    )
    st.markdown("### Citizen Login")
    st.write("Authenticate to access the citizen reporting portal.")

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name", key="citizen_name_login")
    with col2:
        token = st.text_input("Any value", type="password", key="citizen_pass_login")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Login as Citizen", use_container_width=True, type="primary"):
            if not name.strip() or not token.strip():
                st.error("Enter both fields to continue.")
            else:
                st.session_state.user_role = "citizen"
                st.session_state.username = name.strip()
                st.session_state.route = "citizen_dashboard"
                _rerun()
    with b2:
        if st.button("Back to Home", use_container_width=True):
            st.session_state.route = "landing"
            _rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)


def _authority_login():
    st.markdown('<div class="glass-card" style="max-width: 720px; margin: 2rem auto;">', unsafe_allow_html=True)
    st.markdown("### Government Authority Login")
    st.write("Demo credentials: username `official`, password `avisens2026`.")
    col1, col2 = st.columns(2)
    with col1:
        user = st.text_input("Username", key="authority_user_login")
    with col2:
        pwd = st.text_input("Password", type="password", key="authority_pass_login")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Login as Authority", use_container_width=True, type="primary"):
            if user == "official" and pwd == "avisens2026":
                st.session_state.user_role = "authority"
                st.session_state.username = user
                st.session_state.authority_last_seen_count = 0
                st.session_state.route = "authority_dashboard"
                _rerun()
            else:
                st.error("Invalid authority credentials.")
    with b2:
        if st.button("Back to Home", use_container_width=True):
            st.session_state.route = "landing"
            _rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _auth_shell(title: str):
    left, center, right = st.columns([1.1, 2.7, 1.2])
    with center:
        st.markdown(
            f"""
            <div class="gov-card" style="padding: 1rem 1.2rem; margin-bottom: 1rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; gap:1rem; flex-wrap:wrap;">
                    <div>
                        <div style="font-size:1.3rem; font-weight:700; color:var(--navy);">AVISENS</div>
                        <div style="color:var(--muted);">AI Powered Road Accountability Platform</div>
                    </div>
                    <div>{role_badge(st.session_state.get('user_role', ''))}</div>
                </div>
                <div style="margin-top:0.6rem; font-size:1.05rem; color:var(--text);">{title}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main():
    _init_state()

    if st.session_state.route == "landing":
        _landing_page()
        return

    if st.session_state.route == "citizen_login":
        _citizen_login()
        return

    if st.session_state.route == "authority_login":
        _authority_login()
        return

    if st.session_state.route == "citizen_dashboard":
        _auth_shell("Citizen Reporting Portal")
        cols = st.columns([4, 1])
        with cols[1]:
            if st.button("Logout", use_container_width=True):
                _logout()
        run_citizen_dashboard()
        return

    if st.session_state.route == "authority_dashboard":
        _auth_shell("Municipal Monitoring Dashboard")
        cols = st.columns([4, 1])
        with cols[1]:
            if st.button("Logout", use_container_width=True):
                _logout()
        run_authority_dashboard()
        return

    st.session_state.route = "landing"
    _rerun()


if __name__ == "__main__":
    main()
