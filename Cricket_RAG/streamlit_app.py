from __future__ import annotations

import sys
import json
from pathlib import Path
import streamlit as st

# Make project root importable
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.extract_text import extract_text
from modules.parse_players import parse_players
from modules.rag_store import PlayerRAGStore
from modules.team_builder import build_balanced_teams
from modules.scheduler import round_robin_pairs, assign_time_slots


# -------------------- Paths --------------------
BASE = ROOT
UPLOADS = BASE / "data" / "uploads"
STORE = BASE / "data" / "store"
UPLOADS.mkdir(parents=True, exist_ok=True)
STORE.mkdir(parents=True, exist_ok=True)

# -------------------- Streamlit setup --------------------
st.set_page_config(page_title="Cricket RAG Team & Scheduler", layout="wide")
st.title("🏏 Cricket Team Generator + Match Scheduler (RAG)")

# Session state
if "players" not in st.session_state:
    st.session_state.players = []
if "rag_built" not in st.session_state:
    st.session_state.rag_built = False

@st.cache_resource
def get_rag_store() -> PlayerRAGStore:
    return PlayerRAGStore(STORE)

rag = get_rag_store()

# -------------------- Sidebar --------------------
with st.sidebar:
    st.header("Settings")
    num_teams = st.slider("Number of teams", 2, 10, 2, 1)
    team_size = st.number_input("Players per team", min_value=5, max_value=15, value=11, step=1)

    st.subheader("Time slots")
    slots_text = st.text_area(
        "One slot per line",
        value="Sat 6:00-9:00 PM\nSun 6:00-9:00 PM\nWed 7:00-10:00 PM",
        height=120
    )
    time_slots = [s.strip() for s in slots_text.splitlines() if s.strip()]

    st.subheader("Generation Mode")
    use_rag = st.toggle("Use RAG (FAISS) store", value=True)
    st.caption("If OFF, it uses players stored in session after upload.")


tab1, tab2 = st.tabs(["1) Upload", "2) Generate"])


# =========================
# TAB 1: Upload
# =========================
with tab1:
    st.subheader("Upload player list (PDF or DOCX)")
    uploaded = st.file_uploader("Choose a file", type=["pdf", "docx"])

    if uploaded:
        save_path = UPLOADS / uploaded.name
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())

        st.success(f"Saved file: {save_path.name}")

        with st.spinner("Extracting text..."):
            text = extract_text(save_path)

        if not text.strip():
            st.error("No text extracted. If your PDF is scanned image, OCR is needed.")
        else:
            st.text_area("Extracted text (preview)", text[:4000], height=220)

            with st.spinner("Parsing players..."):
                players = parse_players(text)

            if len(players) < 2:
                st.error("Could not detect enough players. Please check your document format.")
                st.stop()

            # Store in session
            st.session_state.players = players
            st.session_state.rag_built = False

            st.info(f"Players detected: {len(players)}")
            st.dataframe(players[:25], use_container_width=True)

            col_a, col_b = st.columns(2)

            with col_a:
                if st.button("Build / Update RAG Index (FAISS)"):
                    with st.spinner("Building vector index..."):
                        rag.build(players)
                    st.session_state.rag_built = True
                    st.success("RAG index built ✅")

            with col_b:
                st.download_button(
                    "Download players.json",
                    data=json.dumps(players, indent=2),
                    file_name="players.json",
                    mime="application/json",
                    use_container_width=True,
                )


# =========================
# TAB 2: Generate
# =========================
with tab2:
    st.subheader("Generate balanced teams + match schedule")

    if st.button("Generate Now", use_container_width=True):
        # Get players from RAG or session
        if use_rag:
            players = rag.search("all players list with role and rating", k=5000)
        else:
            players = st.session_state.players

        if not players:
            st.error("No players loaded. Upload a file first (Tab 1).")
            st.stop()

        # Basic sanity: enough players for requested teams/size
        needed = num_teams * team_size
        if len(players) < needed:
            st.warning(f"Not enough players for {num_teams} teams × {team_size} players. "
                       f"Need {needed}, but got {len(players)}. I will fill as much as possible.")

        with st.spinner("Building teams..."):
            teams = build_balanced_teams(players, num_teams=num_teams, team_size=team_size)

        team_names = list(teams.keys())

        with st.spinner("Scheduling matches..."):
            if len(team_names) == 2:
                # best of 3 for 2 teams
                matches = [(team_names[0], team_names[1])] * 3
            else:
                matches = round_robin_pairs(team_names)

            schedule = assign_time_slots(matches, time_slots)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Teams")
            for tname, tinfo in teams.items():
                st.markdown(f"**{tname}**  \nTotal: {tinfo['total_rating']} | Avg: {tinfo['avg_rating']}")
                st.dataframe(tinfo["players"], use_container_width=True, height=240)

        with col2:
            st.markdown("### Match Schedule")
            st.dataframe(schedule, use_container_width=True, height=520)

        output = {"teams": teams, "schedule": schedule}
        st.download_button(
            "Download result.json",
            data=json.dumps(output, indent=2),
            file_name="result.json",
            mime="application/json",
            use_container_width=True,
        )

