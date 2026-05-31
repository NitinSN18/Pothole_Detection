import base64
import time
from io import BytesIO
from uuid import uuid4

import requests
import streamlit as st
from PIL import Image, ImageDraw

from frontend.ui import chip_line, location_tags, progress_text, severity_badge

BACKEND_CITIZEN_URL = "http://127.0.0.1:8000/citizen-upload"
STATUS_FLOW = ["Reported", "Under Review", "Assigned", "Repair In Progress", "Resolved"]


def _init_state():
    if "citizen_history" not in st.session_state:
        st.session_state.citizen_history = []
    if "reports" not in st.session_state:
        st.session_state.reports = []
    st.session_state.setdefault("citizen_last_report", None)


def _to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _severity_to_rgba(severity: str):
    sev = (severity or "").strip().lower()
    if sev == "red":
        return (255, 77, 79, 140)
    if sev == "yellow":
        return (255, 215, 0, 140)
    if sev == "green":
        return (52, 211, 153, 120)
    return (255, 77, 79, 140)


def _build_multi_overlay(image_bytes: bytes, potholes: list, fallback_mask_b64: str = None):
    try:
        base = Image.open(BytesIO(image_bytes)).convert("RGBA")
        overlay = Image.new("RGBA", base.size, (255, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")

        if potholes:
            for pothole in potholes:
                contour = pothole.get("contour")
                if not contour:
                    continue
                try:
                    pts = [(int(x), int(y)) for x, y in contour]
                    if len(pts) >= 3:
                        color = _severity_to_rgba(pothole.get("severity"))
                        draw.polygon(pts, fill=color, outline=color)
                except Exception:
                    continue
        elif fallback_mask_b64:
            mask_bytes = base64.b64decode(fallback_mask_b64)
            mask = Image.open(BytesIO(mask_bytes)).convert("L").resize(base.size)
            mask_pixels = list(mask.getdata())
            overlay_data = [(_severity_to_rgba("red") if px > 0 else (255, 0, 0, 0)) for px in mask_pixels]
            overlay.putdata(overlay_data)

        return Image.alpha_composite(base, overlay).convert("RGB")
    except Exception:
        return None


def _render_last_report(last_report: dict):
    severity = last_report.get("severity")
    severity_class = last_report.get("severity_class")
    confidence = last_report.get("confidence")
    action_plan = last_report.get("action_plan")
    overlay_img = last_report.get("overlay")
    base_img = last_report.get("image")

    st.markdown(severity_badge(severity, severity_class), unsafe_allow_html=True)
    st.write(f"**Composite Score:** {progress_text(last_report.get('severity_score'))}")
    st.write(f"**Confidence:** {confidence:.2%}" if confidence is not None else "**Confidence:** --")
    st.write(f"**Action Recommendation:** {action_plan or 'Monitor and reassess'}")
    st.write("**Report Successfully Sent To Authorities**")

    img_col1, img_col2 = st.columns(2)
    with img_col1:
        if base_img is not None:
            st.image(base_img, caption="Original image", use_container_width=True)
    with img_col2:
        if overlay_img is not None:
            st.image(overlay_img, caption="YOLO segmentation overlay", use_container_width=True)


def run():
    _init_state()
    # Header
    st.markdown(
        """
        <div style="display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-bottom:1rem;">
            <div>
                <h1 style="margin:0; color:var(--navy); font-size:1.8rem;">Citizen Portal</h1>
                <div style="color:var(--muted);">Report potholes quickly and track municipal actions.</div>
            </div>
            <div style="text-align:right; color:var(--muted);">Quick tips: upload a clear image & include GPS for faster action</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("user_role") != "citizen":
        st.info("Use the login portal to access this page.")
        return

    # 60/40 two-column layout (left: form, right: analysis)
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown('<div class="portal-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Submit a Pothole Report</div>', unsafe_allow_html=True)
        # Upload area with prominent dashed box
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        uploaded = st.file_uploader("Upload pothole image", type=["jpg", "jpeg", "png"], help="Preferred: clear daytime photo, visible pothole")
        st.markdown('</div>', unsafe_allow_html=True)

        with st.form("citizen_report_form", clear_on_submit=False):
            g_force = st.slider("Severity Data (G-force)", min_value=0.0, max_value=5.0, value=1.0, step=0.1, format="%.1f G")

            st.markdown('<div style="font-weight:600; font-size: 1.05rem; margin-top: 0.5rem; margin-bottom: 0.2rem; color:var(--navy);">GPS Coordinates</div>', unsafe_allow_html=True)
            cols = st.columns([1, 1])
            with cols[0]:
                lat = st.text_input("GPS Latitude", placeholder="13.0843")
            with cols[1]:
                lon = st.text_input("GPS Longitude", placeholder="80.2705")

            desc = st.text_area("Road description", placeholder="Describe the road condition, traffic risk, or waterlogging.", height=120)

            # helpful microcopy and CTA
            st.markdown('<div style="color:var(--muted); font-size:0.92rem; margin-bottom:0.4rem;">Attach GPS coordinates when possible — helps authorities locate the defect faster.</div>', unsafe_allow_html=True)
            submitted = st.form_submit_button("Submit report", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)

        if submitted:
            if not uploaded:
                st.error("Upload a pothole image before submitting.")
            else:
                img_bytes = uploaded.read()
                with st.spinner("Submitting report..."):
                    try:
                        files = {"image": (uploaded.name, img_bytes, uploaded.type)}
                        data = {"source": "citizen", "description": desc, "g_force": str(g_force)}
                        if lat:
                            data["latitude"] = lat
                        if lon:
                            data["longitude"] = lon

                        resp = requests.post(BACKEND_CITIZEN_URL, files=files, data=data, timeout=30)
                        if resp.status_code != 200:
                            st.error(f"Failed to submit: {resp.status_code} {resp.text}")
                        else:
                            j = resp.json()
                            report = j.get("report") or j
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                            severity_block = report.get("severity", {}) if isinstance(report.get("severity"), dict) else {}
                            composite_score = severity_block.get("composite_score", severity_block.get("severity_score"))
                            inference_block = report.get("inference", {}) if isinstance(report.get("inference"), dict) else {}
                            pothole_results = report.get("results", []) if isinstance(report.get("results", []), list) else []
                            overlay_img = _build_multi_overlay(img_bytes, pothole_results, inference_block.get("mask"))
                            loc_tags = location_tags(lat if lat else None, lon if lon else None, source="citizen", description=desc)
                            loc_tags.append(("Severity Data", f"{g_force:.1f} G"))
                            report_id = str(uuid4())

                            entry = {
                                "report_id": report_id,
                                "image": img_bytes,
                                "severity": severity_block.get("severity_label") if severity_block else None,
                                "severity_class": severity_block.get("severity_class"),
                                "severity_score": composite_score,
                                "confidence": report.get("inference", {}).get("confidence"),
                                "timestamp": timestamp,
                                "status": STATUS_FLOW[0],
                                "raw": report,
                                "overlay": overlay_img,
                                "potholes": pothole_results,
                                "location_tags": loc_tags,
                                "action_plan": severity_block.get("action_plan"),
                            }
                            st.session_state.citizen_history.insert(0, entry)
                            st.session_state.citizen_last_report = entry

                            report_for_feed = {
                                "report_id": report_id,
                                "image": img_bytes,
                                "severity": entry["severity"],
                                "severity_class": entry["severity_class"],
                                "severity_score": entry["severity_score"],
                                "action_plan": severity_block.get("action_plan"),
                                "confidence": entry["confidence"],
                                "gps": {"lat": _to_float(lat), "lon": _to_float(lon)},
                                "timestamp": timestamp,
                                "status": entry["status"],
                                "source": "citizen",
                                "raw": report,
                                "potholes": pothole_results,
                                "overlay": overlay_img,
                                "location_tags": loc_tags,
                                "description": desc,
                            }
                            st.session_state.reports.insert(0, report_for_feed)
                            st.success("Report successfully submitted — authorities have been notified.")

                    except requests.exceptions.RequestException as e:
                        st.error(f"Request failed: {e}")

    with right:
        st.markdown('<div class="portal-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Latest Analysis</div>', unsafe_allow_html=True)
        last_report = st.session_state.get("citizen_last_report")
        if last_report:
            # compact summary card
            st.markdown('<div style="margin-bottom:0.6rem;">', unsafe_allow_html=True)
            st.markdown(severity_badge(last_report.get('severity'), last_report.get('severity_class')), unsafe_allow_html=True)
            st.write(f"**Composite Score:** {progress_text(last_report.get('severity_score'))}")
            st.write(f"**Confidence:** {last_report.get('confidence', '--') if last_report.get('confidence') is not None else '--'}")
            st.markdown('</div>', unsafe_allow_html=True)
            _render_last_report(last_report)
        else:
            # friendly placeholder with subtle illustration
            st.markdown(
                '<div class="analysis-placeholder">'
                '<div style="font-size:2.1rem;">📭</div>'
                '<div><strong>No recent reports.</strong><div style="color:var(--muted);">Submit a new report to view analysis and severity recommendations.</div></div>'
                '</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("## Citizen History")
    if not st.session_state.citizen_history:
        st.markdown('<div class="ghost-note">No past reports. Your submitted reports will appear here.</div>', unsafe_allow_html=True)
    for r in st.session_state.citizen_history[:20]:
        st.markdown('<div class="portal-card" style="margin-bottom:1rem; display:flex; gap:1rem; align-items:center;">', unsafe_allow_html=True)
        # thumbnail + meta
        try:
            im = Image.open(BytesIO(r["image"]))
            st.image(im, width=150)
        except Exception:
            st.write("[image]")
        st.markdown('<div style="flex:1;">', unsafe_allow_html=True)
        st.markdown(severity_badge(r.get("severity"), r.get("severity_class")), unsafe_allow_html=True)
        st.markdown(f"<div style=\"font-weight:700; margin-top:0.25rem;\">Score: {progress_text(r.get('severity_score'))}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style=\"color:var(--muted);\">{r.get('timestamp')}</div>", unsafe_allow_html=True)
        st.markdown(chip_line(r.get("location_tags") or []), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div><span class="status-pill">{r.get("status")}</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
