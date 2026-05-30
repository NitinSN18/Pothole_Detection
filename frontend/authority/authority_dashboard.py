import streamlit as st
from PIL import Image
from io import BytesIO
import pandas as pd
import time

from frontend.ui import chip_line, location_tags, progress_text, severity_badge


def _init_state():
    if "reports" not in st.session_state:
        st.session_state.reports = []


def _severity_rank(label: str) -> int:
    sev = (label or "").strip().lower()
    return {"green": 0, "yellow": 1, "red": 2}.get(sev, 3)


def run():
    _init_state()
    st.markdown("## Government Authority Dashboard")
    st.caption("Live pothole feed, emergency hazards, status controls, and city monitoring view.")

    if st.session_state.get("user_role") != "authority":
        st.info("Use the authority login screen to access this dashboard.")
        return

    with st.sidebar:
        st.markdown("### Control Panel")
        severity_filter = st.selectbox("Severity", ["All", "Green", "Yellow", "Red"], index=0)
        unresolved_only = st.checkbox("Unresolved only", value=False)
        sort_mode = st.selectbox("Sort by", ["Newest", "Oldest", "Severity"], index=0)
        search_text = st.text_input("Search source / location", "")
        st.markdown("---")
        st.markdown("**Navigation**")
        st.write("Live Feed")
        st.write("Emergency Hazards")
        st.write("Analytics")
        st.write("Map Placeholder")

    total = len(st.session_state.reports)
    severe = sum(1 for r in st.session_state.reports if (r.get("severity") or "").lower() == "red")
    unresolved = sum(1 for r in st.session_state.reports if r.get("status") != "Resolved")
    resolved = sum(1 for r in st.session_state.reports if r.get("status") == "Resolved")
    yellow = sum(1 for r in st.session_state.reports if (r.get("severity") or "").lower() == "yellow")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Reports", total)
    m2.metric("Severe (Red)", severe)
    m3.metric("Moderate (Yellow)", yellow)
    m4.metric("Resolved", resolved)

    st.write("---")

    reports = st.session_state.reports

    def match(r):
        if severity_filter != "All" and (r.get("severity") or "") != severity_filter:
            return False
        if unresolved_only and r.get("status") == "Resolved":
            return False
        if search_text:
            s = search_text.lower()
            if s not in str(r.get("gps", "")).lower() and s not in str(r.get("source", "")).lower():
                return False
        return True

    filtered = [r for r in reports if match(r)]

    if sort_mode == "Newest":
        filtered = sorted(filtered, key=lambda item: item.get("timestamp", ""), reverse=True)
    elif sort_mode == "Oldest":
        filtered = sorted(filtered, key=lambda item: item.get("timestamp", ""))
    else:
        filtered = sorted(filtered, key=lambda item: _severity_rank(item.get("severity")), reverse=True)

    if not filtered:
        st.info("No reports to show. Citizen submissions will appear here.")
        st.write("You can also add demo reports by uploading in Citizen portal.")
        return

    emergency = [r for r in filtered if (r.get("severity") or "").lower() == "red"]
    if emergency:
        st.markdown("### Immediate Attention Required")
        for r in emergency[:3]:
            st.markdown('<div class="avisens-card">', unsafe_allow_html=True)
            st.markdown(f"{severity_badge('Red')} **{r.get('source', 'citizen').title()}** - {r.get('timestamp')}", unsafe_allow_html=True)
            st.write(f"Composite Score: {progress_text(r.get('severity_score'))}")
            st.write(f"Location: {r.get('gps')}")
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Live Pothole Reports Feed")
    for idx, r in enumerate(filtered):
        cols = st.columns([1.05, 2.6, 1.35])
        with cols[0]:
            try:
                im = Image.open(BytesIO(r["image"]))
                st.image(im, width=180)
            except Exception:
                st.write("[image]")
        with cols[1]:
            st.markdown(f"**Severity:** {severity_badge(r.get('severity'))}", unsafe_allow_html=True)
            st.write(f"**Composite Score:** {progress_text(r.get('severity_score'))}")
            st.write(f"**Confidence:** {r.get('confidence'):.2%}" if r.get('confidence') is not None else "**Confidence:** --")
            st.write(f"**Source:** {r.get('source')}")
            st.write(f"**Time:** {r.get('timestamp')}")
            st.write(f"**Status:** {r.get('status')}")
            if r.get('action_plan'):
                st.write(f"**Action:** {r.get('action_plan')}")
            if r.get('location_tags'):
                st.markdown(chip_line(r.get('location_tags')), unsafe_allow_html=True)
            else:
                gps = r.get('gps') or {}
                st.markdown(chip_line(location_tags(gps.get('lat'), gps.get('lon'), source=r.get('source', 'citizen'))), unsafe_allow_html=True)
            if r.get("overlay") is not None:
                st.image(r.get("overlay"), caption="Segmented highlight", width=420)
        with cols[2]:
            st.markdown('<div class="avisens-card">', unsafe_allow_html=True)
            st.write(f"**Current Status:** {r.get('status')}")
            new_status = st.selectbox(
                f"Update status {idx}",
                ['Reported', 'Under Review', 'Repair Assigned', 'Repair In Progress', 'Resolved'],
                index=['Reported', 'Under Review', 'Repair Assigned', 'Repair In Progress', 'Resolved'].index(r.get('status')) if r.get('status') in ['Reported', 'Under Review', 'Repair Assigned', 'Repair In Progress', 'Resolved'] else 0,
                key=f"status_{idx}",
            )
            if st.button(f"Set status {idx}", key=f"set_status_{idx}"):
                r['status'] = new_status
                st.success(f"Status updated to {new_status}")
            if r.get("potholes"):
                with st.expander("Per pothole scores"):
                    for p in r.get("potholes", []):
                        st.write(f"- {p.get('severity')} | {p.get('composite_score')} / 100")
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.write("---")
    st.subheader("City Road Monitoring Map")
    st.caption("Map placeholder for future GIS integration.")
    try:
        rows = []
        for r in st.session_state.reports:
            gps = r.get('gps') or {}
            lat = gps.get('lat')
            lon = gps.get('lon')
            if lat is not None and lon is not None:
                try:
                    rows.append({"lat": float(lat), "lon": float(lon)})
                except Exception:
                    continue
        if rows:
            df = pd.DataFrame(rows)
            st.map(df)
        else:
            st.info("Map placeholder — no GPS-enabled reports yet.")
    except Exception:
        st.info("Map placeholder (unable to render coordinates).")
