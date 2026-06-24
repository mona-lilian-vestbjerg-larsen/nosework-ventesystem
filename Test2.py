import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# ==================================================
# PAGE SETUP
# ==================================================

st.set_page_config(layout="wide")

if st.query_params.get("autorefresh", "1") == "1":
    st_autorefresh(interval=2000, key="global_refresh")

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
# LOAD / SAVE
# ==================================================

@st.cache_data(ttl=3)
def load_data():
    df = pd.DataFrame(sheet.get_all_records())

    flows = {}
    for _, row in df.iterrows():
        name = str(row[SPOG_KOLONNE]).strip()

        if name not in flows:
            flows[name] = []

        flows[name].append(row)

    for f in flows:
        flows[f] = sorted(flows[f], key=lambda x: x[ORDER_KOLONNE])

    return flows


def save_all(flows):
    rows = []
    for flow_name, entries in flows.items():
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
    sheet.update([df.columns.tolist()] + df.values.tolist())

# ==================================================
# SESSION STATE (CRITICAL)
# ==================================================

if "original_flows" not in st.session_state:
    original = load_data()

    st.session_state.original_flows = {
        k: list(v) for k, v in original.items()
    }

    st.session_state.flows = {
        k: list(v) for k, v in original.items()
    }

if "done_flows" not in st.session_state:
    st.session_state.done_flows = {
        f: [] for f in st.session_state.flows
    }

for f in st.session_state.flows:
    if f not in st.session_state.done_flows:
        st.session_state.done_flows[f] = []


# ==================================================
# HELPERS
# ==================================================

def format_entry(e):
    return f"{e[STARTNR_KOLONNE]} - {e[FORER_KOLONNE]} ({e[HUND_KOLONNE]})"

def avancer(flow):
    if flows[flow]:
        finished = flows[flow].pop(0)
        st.session_state.done_flows[flow].append(finished)
        save_all(flows)
        st.cache_data.clear()

def fortryd(flow):
    if st.session_state.done_flows[flow]:
        back = st.session_state.done_flows[flow].pop()
        flows[flow].insert(0, back)
        save_all(flows)
        st.cache_data.clear()

# ✅ ALWAYS SAFE RESET
def reset_flow(flow):
    flows[flow] = list(st.session_state.original_flows[flow])
    st.session_state.done_flows[flow] = []
    save_all(flows)

# ✅ SAFE CLEAR (no data loss)
def clear_done(flow):
    flows[flow] = st.session_state.done_flows[flow] + flows[flow]
    st.session_state.done_flows[flow] = []
    save_all(flows)

# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.title("Kontrol")

mode = st.sidebar.radio("Visning", ["Offentlig Skærm", "Administration"])
layout = st.sidebar.radio("Layout", ["Mobil", "Skærm"])

is_admin = mode == "Administration"
is_screen = layout == "Skærm"

if is_admin:
    flows = st.session_state.flows
else:
    flows = load_data()

# ==================================================
# LOGIN
# ==================================================

admin_logged_in = False

if is_admin:

    if "admin_ok" not in st.session_state:
        st.session_state.admin_ok = False

    if not st.session_state.admin_ok:
        st.title("🔒 Login")

        with st.form("login"):
            pw = st.text_input("Kode", type="password")
            ok = st.form_submit_button("Log ind")

        if ok:
            if pw == ADMIN_PASSWORD:
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("Forkert kode")

    admin_logged_in = st.session_state.admin_ok

# ==================================================
# DISPLAY
# ==================================================

def vis_flow(name, flow):
    if not flow:
        st.markdown("### ✅ FÆRDIG")
        st.markdown("Alle hunde har gennemført")
        return

    st.metric("🔍 SØGER", format_entry(flow[0]))
    st.metric("⏳ PÅ VENTEPLADS", format_entry(flow[1]) if len(flow) > 1 else "-")

    st.markdown("### 👉 NÆSTE")
    for e in flow[2:2+ANTAL_NAESTE_VISNING]:
        st.write(format_entry(e))

# ==================================================
# PUBLIC
# ==================================================

if not is_admin:

    st.title("NoseWork")

    if is_screen:
        all_names = list(st.session_state.original_flows.keys())
        
        cols = st.columns(len(all_names))
        
        for col, name in zip(cols, all_names):
            flow = flows.get(name, [])
        
            with col:
                st.header(name)
                vis_flow(name, flow)

    else:
        all_names = list(st.session_state.original_flows.keys())
        
        tabs = st.tabs(all_names)
        
        for tab, name in zip(tabs, all_names):
            flow = flows.get(name, [])
        
            with tab:
                vis_flow(name, flow)

# ==================================================
# ADMIN
# ==================================================

if is_admin and admin_logged_in:

    st.title("Administration")

    all_names = list(st.session_state.original_flows.keys())
    
    tabs = st.tabs(all_names)
    
    for tab, name in zip(tabs, all_names):
        flow = flows.get(name, [])

        with tab:

            flow = flows.get(name, [])
            done = st.session_state.done_flows.get(name, [])
            
            st.subheader(name)

            if not flow:
                st.markdown("### ✅ FÆRDIG")

            # ✅ Buttons INSIDE TAB
            if st.button("🔄 Genstart", key=f"reset_{name}"):
                reset_flow(name)
                st.rerun()

            if flow:
                st.metric("Søger", format_entry(flow[0]))
            if len(flow) > 1:
                st.metric("På venteplads", format_entry(flow[1]))

            col1, col2 = st.columns(2)
            
            if col1.button("▶️ Næste", key=f"next_{name}"):
                avancer(name)
                st.rerun()

            if col2.button("↩️ Fortryd", key=f"undo_{name}"):
                fortryd(name)
                st.rerun()
            
            st.divider()

            # Active queue
            for i, e in enumerate(flow):
                marker = ""
                if i == 0:
                    marker = " 🔴"
                elif i == 1:
                    marker = " 🟡"
                elif i == 2:
                    marker = " 🟢"

                st.write(format_entry(e) + marker)

            st.divider()

            # Done
            st.markdown("### ✅ Allerede søgt")
            for e in done:
                st.write(format_entry(e))
