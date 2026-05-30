import streamlit as st
from PIL import Image, ImageDraw
from io import BytesIO
import requests
import time
import base64

from frontend.ui import chip_line, location_tags, progress_text, severity_badge

BACKEND_CITIZEN_URL = "http://127.0.0.1:8000/citizen-upload"


def _init_state():
    if "citizen_history" not in st.session_state:
        st.session_state.citizen_history = []
    if "reports" not in st.session_state:
        st.session_state.reports = []


def _to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _build_overlay(image_bytes: bytes, mask_b64: str):
    try:
        base = Image.open(BytesIO(image_bytes)).convert("RGBA")
        mask_bytes = base64.b64decode(mask_b64)
        mask = Image.open(BytesIO(mask_bytes)).convert("L").resize(base.size)
        overlay = Image.new("RGBA", base.size, (255, 0, 0, 0))
        overlay_data = []
        mask_pixels = list(mask.getdata())
        for px in mask_pixels:
            overlay_data.append((255, 0, 0, 90) if px > 0 else (255, 0, 0, 0))
        overlay.putdata(overlay_data)
        return Image.alpha_composite(base, overlay).convert("RGB")
    except Exception:
        return None


def _severity_to_rgba(severity: str):
    sev = (severity or "").strip().lower()
    if sev == "red":
        return (255, 0, 0, 110)
    if sev == "yellow":
        return (255, 215, 0, 110)
    if sev == "green":
        return (0, 200, 0, 110)
    return (255, 0, 0, 110)


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
                        draw.polygon(pts, fill=_severity_to_rgba(pothole.get("severity")), outline=_severity_to_rgba(pothole.get("severity")))
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


def run():
    _init_state()
    st.markdown("## Citizen Reporting Portal")
    st.caption("Upload pothole images, attach useful location tags, and track your report history.")

    if st.session_state.get("user_role") != "citizen":
        st.info("Use the login portal to access this page.")
        return

    top1, top2, top3 = st.columns(3)
    top1.metric("Recent Reports", len(st.session_state.citizen_history))
    top2.metric("Submitted by You", len(st.session_state.citizen_history))
    top3.metric("Current User", st.session_state.get("username", "Citizen"))

    st.write("---")
    left, right = st.columns([1.2, 0.95], gap="large")
    with left:
        st.markdown('<div class="avisens-card">', unsafe_allow_html=True)
        st.markdown("### New Report")
        uploaded = st.file_uploader("Upload image", type=["jpg", "jpeg", "png"], key="citizen_upload")
        desc = st.text_area("Description", placeholder="e.g. waterlogging, accident risk, traffic obstruction, deep crack")
        st.markdown("#### GPS Location")
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            lat = st.text_input("Latitude", placeholder="13.0843", key="citizen_lat")
        with c2:
            lon = st.text_input("Longitude", placeholder="80.2705", key="citizen_lon")
        with c3:
            st.write("\n")
            st.button("Use Current Location", disabled=True, help="Browser geolocation placeholder")
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="avisens-card">', unsafe_allow_html=True)
        st.markdown("### Location Tags")
        loc_tags = location_tags(lat if lat else None, lon if lon else None, source="citizen", description=desc)
        st.markdown(chip_line(loc_tags), unsafe_allow_html=True)
        st.caption("Use GPS coordinates and the map link to make each report actionable.")
        st.markdown("### Report Status")
        st.markdown(f"{severity_badge('Green')} {severity_badge('Yellow')} {severity_badge('Red')}", unsafe_allow_html=True)
        st.caption("Status appears after submission and updates in the history cards.")
        st.markdown('</div>', unsafe_allow_html=True)

    if uploaded:
        img_bytes = uploaded.read()
        img = Image.open(BytesIO(img_bytes))
        st.markdown('<div class="avisens-card">', unsafe_allow_html=True)
        st.markdown("### Preview")
        st.image(img, caption="Uploaded image preview", width=640)
        if st.button("Submit Report", use_container_width=True):
            with st.spinner("Submitting report..."):
                try:
                    files = {"image": (uploaded.name, img_bytes, uploaded.type)}
                    data = {"source": "citizen", "description": desc}
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
                        overlay_img = None
                        inference_block = report.get("inference", {}) if isinstance(report.get("inference"), dict) else {}
                        pothole_results = report.get("results", []) if isinstance(report.get("results", []), list) else []
                        overlay_img = _build_multi_overlay(img_bytes, pothole_results, inference_block.get("mask"))
                        entry = {
                            "image": img_bytes,
                            "severity": severity_block.get("severity_label") if severity_block else None,
                            "severity_score": composite_score,
                            "confidence": report.get("inference", {}).get("confidence"),
                            "timestamp": timestamp,
                            "status": "Reported",
                            "raw": report,
                            "overlay": overlay_img,
                            "potholes": pothole_results,
                            "location_tags": loc_tags,
                            "action_plan": severity_block.get("action_plan"),
                        }
                        st.session_state.citizen_history.insert(0, entry)
                        report_for_feed = {
                            "image": img_bytes,
                            "severity": entry['severity'],
                            "severity_score": entry['severity_score'],
                            "action_plan": severity_block.get("action_plan"),
                            "confidence": entry['confidence'],
                            "gps": {"lat": _to_float(lat), "lon": _to_float(lon)},
                            "timestamp": timestamp,
                            "status": entry['status'],
                            "source": "citizen",
                            "raw": report,
                            "potholes": pothole_results,
                            "overlay": overlay_img,
                            "location_tags": loc_tags,
                        }
                        st.session_state.reports.insert(0, report_for_feed)
                        st.success("Report successfully submitted to road authorities.")
                        st.markdown(f"**Severity:** {severity_badge(entry['severity'])}", unsafe_allow_html=True)
                        st.write(f"**Composite Score:** {progress_text(entry['severity_score'])}")
                        st.write(f"**Confidence:** {entry['confidence']:.2%}" if entry.get('confidence') is not None else "**Confidence:** --")
                        st.write(f"**Action:** {severity_block.get('action_plan')}")
                        st.markdown(chip_line(loc_tags), unsafe_allow_html=True)
                        if overlay_img is not None:
                            st.image(overlay_img, caption="Segmented overlay", width=640)

                except requests.exceptions.RequestException as e:
                    st.error(f"Request failed: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    st.write("---")
    st.subheader("Your Recent Reports")
    for i, r in enumerate(st.session_state.citizen_history[:20]):
        st.markdown('<div class="avisens-card" style="margin-bottom:1rem;">', unsafe_allow_html=True)
        cimg, cmeta, cstatus = st.columns([1, 2.2, 1.1])
        with cimg:
            try:
                im = Image.open(BytesIO(r["image"]))
                st.image(im, width=160)
            except Exception:
                st.write("[image]")
        with cmeta:
            st.markdown(f"**Severity:** {severity_badge(r.get('severity'))}", unsafe_allow_html=True)
            st.write(f"**Composite Score:** {progress_text(r.get('severity_score'))}")
            st.write(f"**Confidence:** {r.get('confidence'):.2%}" if r.get('confidence') is not None else "**Confidence:** --")
            st.write(f"**Time:** {r.get('timestamp')}")
            st.markdown(chip_line(r.get("location_tags") or []), unsafe_allow_html=True)
            if r.get("overlay") is not None:
                st.image(r.get("overlay"), caption="Segmented overlay", width=320)
            potholes = r.get("potholes") or []
            if potholes:
                with st.expander("Per pothole results", expanded=False):
                    for p in potholes:
                        st.write(f"- {p.get('severity')} | {p.get('composite_score')} / 100 | action: {p.get('action_plan')}")
        with cstatus:
            st.markdown('<div class="stat-shell">', unsafe_allow_html=True)
            st.write(f"**Status:** {r.get('status')}")
            st.write(f"**Action:** {r.get('action_plan') or 'Monitor and reassess'}")
            with st.expander("Report Details"):
                st.write(r.get('raw'))
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
