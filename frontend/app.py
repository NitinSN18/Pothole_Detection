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


def _rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    st.stop()


def _logout():
    for key in ["user_role", "username"]:
        st.session_state.pop(key, None)
    st.session_state.route = "landing"
    _rerun()


def _landing_page():
    st.markdown(
        """
        <div class="avisens-hero" style="max-width: 980px; margin: 3rem auto 1rem auto; text-align: center;">
            <div style="margin-bottom: 0.75rem;">
                <span class="avisens-badge badge-blue">Smart City Operations</span>
                <span class="avisens-badge badge-slate">AI Road Monitoring</span>
            </div>
            <div class="avisens-title">AVISENS</div>
            <div class="avisens-tagline">AI-powered Road Accountability Platform</div>
            <div style="margin-top: 2rem; color: rgba(229,238,247,0.8); max-width: 760px; margin-left: auto; margin-right: auto;">
                Crowdsourced pothole reporting, infrastructure transparency, and municipal response in one clean smart-city interface.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1.05, 1])
    with c1:
        st.markdown('<div class="avisens-card" style="min-height: 220px;">', unsafe_allow_html=True)
        st.markdown("### Citizen Login")
        st.write("Report potholes, add GPS, track status, and view recent submissions.")
        st.markdown('</div>', unsafe_allow_html=True)
        if st.button("Open Citizen Portal", use_container_width=True):
            st.session_state.route = "citizen_login"
            _rerun()
    with c2:
        st.markdown('<div class="avisens-card" style="min-height: 220px;">', unsafe_allow_html=True)
        st.markdown("### Government Authority Login")
        st.write("Monitor live feed, manage repair status, and prioritize hazards.")
        st.markdown('</div>', unsafe_allow_html=True)
        if st.button("Open Authority Portal", use_container_width=True):
            st.session_state.route = "authority_login"
            _rerun()
    with c3:
        st.empty()


def _citizen_login():
    st.markdown(
        """
        <div style="max-width: 700px; margin: 3rem auto 1rem auto;">
            <div class="avisens-card">
                <div style="margin-bottom: 0.6rem;">""",
        unsafe_allow_html=True,
    )
    st.markdown("### Citizen Login")
    st.write("Enter any name and value to access the citizen reporting portal.")

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name", key="citizen_name_login")
    with col2:
        token = st.text_input("Any value", type="password", key="citizen_pass_login")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Login as Citizen", use_container_width=True):
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


def _authority_login():
    st.markdown("### Government Authority Login")
    st.write("Hardcoded demo credentials: username `official`, password `avisens2026`.")
    col1, col2 = st.columns(2)
    with col1:
        user = st.text_input("Username", key="authority_user_login")
    with col2:
        pwd = st.text_input("Password", type="password", key="authority_pass_login")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Login as Authority", use_container_width=True):
            if user == "official" and pwd == "avisens2026":
                st.session_state.user_role = "authority"
                st.session_state.username = user
                st.session_state.route = "authority_dashboard"
                _rerun()
            else:
                st.error("Invalid authority credentials.")
    with b2:
        if st.button("Back to Home", use_container_width=True):
            st.session_state.route = "landing"
            _rerun()


def _auth_shell(title: str):
    left, center, right = st.columns([1.1, 2.7, 1.2])
    with center:
        st.markdown(
            f"""
            <div class="avisens-hero" style="padding: 1.2rem 1.5rem; margin-bottom: 1rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; gap:1rem; flex-wrap:wrap;">
                    <div>
                        <div class="avisens-title" style="font-size:2rem; margin-bottom:0.15rem;">AVISENS</div>
                        <div class="avisens-tagline">AI-powered Road Accountability Platform</div>
                    </div>
                    <div>{role_badge(st.session_state.get('user_role', ''))}</div>
                </div>
                <div style="margin-top:0.8rem; font-size:1.1rem; color:#dbeafe;">{title}</div>
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
