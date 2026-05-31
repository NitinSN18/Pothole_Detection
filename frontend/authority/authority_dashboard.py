from io import BytesIO

import pandas as pd
import pydeck as pdk
import streamlit as st
from PIL import Image

from frontend.ui import chip_line, location_tags, progress_text, severity_badge

STATUS_FLOW = ["Reported", "Under Review", "Assigned", "Repair In Progress", "Resolved"]


def _init_state():
    if "reports" not in st.session_state:
        st.session_state.reports = []
    if "citizen_history" not in st.session_state:
        st.session_state.citizen_history = []
    st.session_state.setdefault("authority_last_seen_count", 0)


def _notify_new_reports(count: int):
    if count <= 0:
        return
    message = f"{count} new pothole report{'s' if count != 1 else ''} uploaded."
    if hasattr(st, "toast"):
        st.toast(message, icon="📣")
    else:
        st.info(message)


def _severity_rank(label: str) -> int:
    sev = (label or "").strip().lower()
    return {"green": 0, "yellow": 1, "red": 2}.get(sev, 3)


def _sync_citizen_history(report_id: str | None, status: str):
    if not report_id:
        return
    for entry in st.session_state.citizen_history:
        if entry.get("report_id") == report_id:
            entry["status"] = status
            break


def _map_color(label: str):
    sev = (label or "").strip().lower()
    if sev == "red":
        return [248, 113, 113, 190]
    if sev == "yellow":
        return [250, 204, 21, 180]
    if sev == "green":
        return [52, 211, 153, 170]
    return [148, 163, 184, 140]


def run():
    _init_state()
    st.markdown("## Government Authority Dashboard")

    if st.session_state.get("user_role") != "authority":
        st.info("Use the authority login screen to access this dashboard.")
        return

    reports = st.session_state.reports
    new_count = max(0, len(reports) - int(st.session_state.get("authority_last_seen_count", 0)))
    if new_count:
        _notify_new_reports(new_count)
        st.session_state.authority_last_seen_count = len(reports)
    total = len(reports)
    critical = sum(1 for r in reports if (r.get("severity") or "").lower() == "red")
    pending = sum(1 for r in reports if r.get("status") != "Resolved")
    resolved = sum(1 for r in reports if r.get("status") == "Resolved")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown('<div class="metric-card"><div class="field-label">Total Reports</div>', unsafe_allow_html=True)
        st.markdown(f"### {total}")
        st.markdown("</div>", unsafe_allow_html=True)
    with m2:
        st.markdown('<div class="metric-card"><div class="field-label">Critical Reports</div>', unsafe_allow_html=True)
        st.markdown(f"### {critical}")
        st.markdown("</div>", unsafe_allow_html=True)
    with m3:
        st.markdown('<div class="metric-card"><div class="field-label">Pending Repairs</div>', unsafe_allow_html=True)
        st.markdown(f"### {pending}")
        st.markdown("</div>", unsafe_allow_html=True)
    with m4:
        st.markdown('<div class="metric-card"><div class="field-label">Resolved Repairs</div>', unsafe_allow_html=True)
        st.markdown(f"### {resolved}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    filter_col, status_col, sort_col = st.columns([1.4, 1.4, 1])
    with filter_col:
        severity_filter = st.multiselect("Severity filters", ["Green", "Yellow", "Red"], default=["Green", "Yellow", "Red"])
    with status_col:
        status_filter = st.multiselect("Status filters", STATUS_FLOW, default=STATUS_FLOW)
    with sort_col:
        sort_mode = st.selectbox("Sort by", ["Newest", "Oldest", "Severity"], index=0)

    def match(r):
        if severity_filter and (r.get("severity") or "") not in severity_filter:
            return False
        if status_filter and (r.get("status") or "") not in status_filter:
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
        st.info("No reports available yet. Citizen submissions will appear here.")
        return

    emergency = [r for r in filtered if (r.get("severity") or "").lower() == "red"]
    if emergency:
        st.markdown("### Emergency Dispatch (RED)")
        em_cols = st.columns(min(3, len(emergency)))
        for idx, r in enumerate(emergency[:3]):
            with em_cols[idx]:
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.markdown(severity_badge("Red", "Critical"), unsafe_allow_html=True)
                st.write(f"**GPS:** {r.get('gps')}")
                st.write(f"**Time:** {r.get('timestamp')}")
                st.write(f"**Confidence:** {r.get('confidence'):.2%}" if r.get("confidence") is not None else "**Confidence:** --")
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Live Report Feed")
    for idx, r in enumerate(filtered):
        st.markdown('<div class="glass-card" style="margin-bottom:1rem;">', unsafe_allow_html=True)
        col_img, col_meta, col_status = st.columns([1.1, 2.2, 1.1])
        with col_img:
            try:
                im = Image.open(BytesIO(r["image"]))
                st.image(im, width=180)
            except Exception:
                st.write("[image]")
            if r.get("overlay") is not None:
                st.image(r.get("overlay"), caption="Segmented preview", width=180)
        with col_meta:
            st.markdown(severity_badge(r.get("severity"), r.get("severity_class")), unsafe_allow_html=True)
            st.write(f"**Composite Score:** {progress_text(r.get('severity_score'))}")
            st.write(f"**Confidence:** {r.get('confidence'):.2%}" if r.get("confidence") is not None else "**Confidence:** --")
            st.write(f"**GPS:** {r.get('gps')}")
            st.write(f"**Timestamp:** {r.get('timestamp')}")
            st.write(f"**Source:** {r.get('source', 'citizen').title()}")
            if r.get("action_plan"):
                st.write(f"**Action:** {r.get('action_plan')}")
            if r.get("location_tags"):
                st.markdown(chip_line(r.get("location_tags")), unsafe_allow_html=True)
            else:
                gps = r.get("gps") or {}
                st.markdown(chip_line(location_tags(gps.get("lat"), gps.get("lon"), source=r.get("source", "citizen"))), unsafe_allow_html=True)
        with col_status:
            st.markdown(f'<span class="status-pill">{r.get("status")}</span>', unsafe_allow_html=True)
            new_status = st.selectbox(
                f"Update status {idx}",
                STATUS_FLOW,
                index=STATUS_FLOW.index(r.get("status")) if r.get("status") in STATUS_FLOW else 0,
                key=f"status_{idx}",
            )
            if st.button("Apply", key=f"apply_{idx}", type="primary"):
                r["status"] = new_status
                _sync_citizen_history(r.get("report_id"), new_status)
                st.success(f"Status updated to {new_status}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Smart City Map")
    rows = []
    for r in reports:
        gps = r.get("gps") or {}
        lat = gps.get("lat")
        lon = gps.get("lon")
        if lat is None or lon is None:
            continue
        try:
            rows.append(
                {
                    "lat": float(lat),
                    "lon": float(lon),
                    "severity": r.get("severity"),
                    "color": _map_color(r.get("severity")),
                }
            )
        except Exception:
            continue

    if rows:
        df = pd.DataFrame(rows)
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius=40,
            pickable=True,
        )
        view_state = pdk.ViewState(latitude=df["lat"].mean(), longitude=df["lon"].mean(), zoom=11, pitch=35)
        deck = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{severity} severity"})
        st.pydeck_chart(deck, use_container_width=True)
    else:
        st.info("No GPS-enabled reports yet. Map will populate as reports arrive.")
