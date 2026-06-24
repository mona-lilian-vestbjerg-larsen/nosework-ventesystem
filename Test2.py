import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# ==================================================
# PAGE SETUP
# ==================================================

st.set_page_config(layout="wide")
st_autorefresh(interval=3000, key="refresh")

st.markdown("""
<style>
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: normal;
    }
</style>
""", unsafe_allow_html=True)

# ==================================================
# CONFIG
# ==================================================

ADMIN_PASSWORD = "nosework"

SHEET_NAME = "NoseWork"
WORKSHEET_NAME = "Ark1"

SPOG_KOLONNE = "Søg"
STARTNR_KOLONNE = "Startnummer"
FORER_KOLONNE = "Fører"
HUND_KOLONNE = "Hund"
ORDER_KOLONNE = "Rækkefølge"

ANTAL_NAESTE_VISNING = 5

# ==================================================
# GOOGLE SHEETS
# ==================================================

@st.cache_resource
def connect():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )

    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)

sheet = connect()

# ==================================================
# LOAD DATA
# ==================================================

@st.cache_data(ttl=3)
def load_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    flows = {}

    for _, row in df.iterrows():
        flow_name = str(row[SPOG_KOLONNE]).strip()

        if flow_name not in flows:
            flows[flow_name] = {
                "queue": [],
                "done": []
            }

        flows[flow_name]["queue"].append(row)

    for f in flows:
        flows[f]["queue"] = sorted(flows[f]["queue"], key=lambda x: x[ORDER_KOLONNE])

    return flows

# ==================================================
# SAVE DATA (only saves active queue)
# ==================================================

def save_all(flows):
    rows = []

    for flow_name, flow_data in flows.items():
        entries = flow_data["queue"]

        for i, e in enumerate(entries):
            rows.append({
                SPOG_KOLONNE: flow_name,
                STARTNR_KOLONNE: e[STARTNR_KOLONNE],
                FORER_KOLONNE: e[FORER_KOLONNE],
                HUND_KOLONNE: e[HUND_KOLONNE],
                ORDER_KOLONNE: i + 1
            })

    df = pd.DataFrame(rows)
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

# ==================================================
# HELPERS
# ==================================================

def format_entry(e):
    return f"{e[STARTNR_KOLONNE]} - {e[FORER_KOLONNE]} ({e[HUND_KOLONNE]})"

def avancer(flow):
    if flows[flow]["queue"]:
        finished = flows[flow]["queue"].pop(0)
        flows[flow]["done"].append(finished)
        save_all(flows)

def fortryd(flow):
    if flows[flow]["done"]:
        back = flows[flow]["done"].pop()
        flows[flow]["queue"].insert(0, back)
        save_all(flows)

# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.title("Kontrolpanel")

mode_choice = st.sidebar.radio("Visning", ["Offentlig Skærm", "Administration"])
layout_choice = st.sidebar.radio("Layout", ["Mobil", "Skærm"])

mode = "admin" if mode_choice == "Administration" else "public"
is_screen = layout_choice == "Skærm"

flows = load_data()

# ==================================================
# PASSWORD PROTECTION
# ==================================================

admin_logged_in = False

if mode == "admin":

    if "admin_ok" not in st.session_state:
        st.session_state.admin_ok = False

    if not st.session_state.admin_ok:
        st.title("🔒 Administration login")

        with st.form("login_form"):
            password = st.text_input("Indtast kode", type="password")
            submitted = st.form_submit_button("Log ind")

        if submitted:
            if password.strip() == ADMIN_PASSWORD:
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("Forkert kode")

    admin_logged_in = st.session_state.admin_ok

# ==================================================
# DISPLAY FUNCTION
# ==================================================

def vis_flow(flow_name, flow_dict):
    queue = flow_dict["queue"]

    if not queue:
        st.write("Ingen deltagere")
        return

    nu = format_entry(queue[0])
    naeste = format_entry(queue[1]) if len(queue) > 1 else "-"

    st.markdown("### 🔍 SØGER")
    st.metric("", nu)

    st.divider()

    st.markdown("### ⏳ PÅ VENTEPLADS")
    st.metric("", naeste)

    st.divider()

    st.markdown("### 👉 NÆSTE")

    for e in queue[2:2 + ANTAL_NAESTE_VISNING]:
        st.write(format_entry(e))

# ==================================================
# PUBLIC VIEW
# ==================================================

if mode == "public":

    st.title("NoseWork Ventesystem")

    if is_screen:
        cols = st.columns(len(flows))

        for col, (flow_name, flow) in zip(cols, flows.items()):
            with col:
                st.header(flow_name)
                vis_flow(flow_name, flow)

    else:
        tabs = st.tabs(list(flows.keys()))

        for tab, (flow_name, flow) in zip(tabs, flows.items()):
            with tab:
                vis_flow(flow_name, flow)

# ==================================================
# ADMIN VIEW
# ==================================================

if mode == "admin" and admin_logged_in:

    st.title("Administration")

    tabs = st.tabs(list(flows.keys()))

    for tab, flow_name in zip(tabs, flows.keys()):
        with tab:

            flow = flows[flow_name]
            queue = flow["queue"]
            done = flow["done"]

            st.subheader(flow_name)

            if queue:
                st.metric("Søger", format_entry(queue[0]))
            if len(queue) > 1:
                st.metric("På venteplads", format_entry(queue[1]))

            col1, col2 = st.columns(2)

            if col1.button("▶️ Næste", key=f"adv_{flow_name}"):
                avancer(flow_name)
                st.rerun()

            if col2.button("↩️ Fortryd", key=f"undo_{flow_name}"):
                fortryd(flow_name)
                st.rerun()

            st.divider()

            # ACTIVE QUEUE
            for idx, e in enumerate(queue):

                colA, colB, colC, colD = st.columns([6,1,1,1])

                marker = ""
                if idx == 0:
                    marker = " 🔴 SØGER"
                elif idx == 1:
                    marker = " 🟡 PÅ VENTEPLADS"
                elif idx == 2:
                    marker = " 🟢 NÆSTE"

                colA.write(f"{format_entry(e)}{marker}")

                if colB.button("⬆️", key=f"up_{flow_name}_{idx}") and idx > 0:
                    queue[idx], queue[idx-1] = queue[idx-1], queue[idx]
                    save_all(flows)
                    st.rerun()

                if colC.button("⬇️", key=f"down_{flow_name}_{idx}") and idx < len(queue)-1:
                    queue[idx], queue[idx+1] = queue[idx+1], queue[idx]
                    save_all(flows)
                    st.rerun()

                if colD.button("❌", key=f"del_{flow_name}_{idx}"):
                    queue.pop(idx)
                    save_all(flows)
                    st.rerun()

            st.divider()

            # ✅ DONE SECTION
            st.markdown("### ✅ Allerede søgt")

            for e in reversed(done):
                st.write(format_entry(e))
