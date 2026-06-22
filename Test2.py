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
    /* ONLY the dog/handler text */
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: normal;
    }
</style>
""", unsafe_allow_html=True)

# ==================================================
# CONFIG
# ==================================================

ADMIN_PASSWORD = "nosework"   # ← change this to your own

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

    creds_dict = st.secrets["gcp_service_account"]

    creds = Credentials.from_service_account_info(
        creds_dict,
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
            flows[flow_name] = []

        flows[flow_name].append(row)

    for f in flows:
        flows[f] = sorted(flows[f], key=lambda x: x[ORDER_KOLONNE])

    return flows

# ==================================================
# SAVE DATA
# ==================================================

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
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

# ==================================================
# HELPERS
# ==================================================

def format_entry(e):
    return f"{e[STARTNR_KOLONNE]} - {e[FORER_KOLONNE]} ({e[HUND_KOLONNE]})"

def avancer(flow):
    flows[flow].append(flows[flow].pop(0))
    save_all(flows)

def fortryd(flow):
    flows[flow].insert(0, flows[flow].pop())
    save_all(flows)

# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.title("Kontrolpanel")

mode_choice = st.sidebar.radio(
    "Visning",
    ["Offentlig Skærm", "Administration"]
)

layout_choice = st.sidebar.radio(
    "Layout",
    ["Skærm", "Mobil"]
)

mode = "admin" if mode_choice == "Administration" else "public"
is_mobile = layout_choice == "Mobil"

# ==================================================
# LOAD FLOWS
# ==================================================

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

def vis_flow(flow_name, flow):
    if not flow:
        st.write("Ingen deltagere")
        return

    nu = format_entry(flow[0])
    naeste = format_entry(flow[1]) if len(flow) > 1 else "-"

    st.markdown("### 🔍 SØGER")
    st.metric("", nu)

    st.divider()

    st.markdown("### ⏳ PÅ VENTEPLADS")
    st.metric("", naeste)

    st.divider()

    st.markdown("### 👉 NÆSTE")

    for e in flow[2:2 + ANTAL_NAESTE_VISNING]:
        st.write(format_entry(e))

# ==================================================
# PUBLIC VIEW
# ==================================================

if mode == "public":

    st.title("NoseWork Ventesystem")

    if is_mobile:
        tabs = st.tabs(list(flows.keys()))

        for tab, (flow_name, flow) in zip(tabs, flows.items()):
            with tab:
                vis_flow(flow_name, flow)

    else:
        cols = st.columns(len(flows))

        for col, (flow_name, flow) in zip(cols, flows.items()):
            with col:
                st.header(flow_name)
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

            st.subheader(flow_name)

            if flow:
                st.metric("Søger", format_entry(flow[0]))
            if len(flow) > 1:
                st.metric("På venteplads", format_entry(flow[1]))

            col1, col2 = st.columns(2)

            if col1.button("▶️ Næste", key=f"adv_{flow_name}"):
                avancer(flow_name)
                st.rerun()

            if col2.button("↩️ Fortryd", key=f"undo_{flow_name}"):
                fortryd(flow_name)
                st.rerun()

            st.divider()

            
            for idx, e in enumerate(flow):

                colA, colB, colC, colD = st.columns([6,1,1,1])

                marker = ""
                if idx == 0:
                    marker = " 🔴 SØGER"
                elif idx == 1:
                    marker = " 🟡 PÅ VENTEPLADS"
                elif idx == 2:
                    marker = " 🟢 NÆSTE"

