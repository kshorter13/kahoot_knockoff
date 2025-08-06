import streamlit as st
import time
import random
import string
import io
# You need to install this library: pip install google-cloud-firestore
from google.cloud import firestore

# --- Page Configuration ---
st.set_page_config(
    page_title="Streamlit Kahoot Clone",
    page_icon="🏆",
    layout="centered",
)

# --- Custom CSS for Styling ---
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Create a dummy style.css file to avoid errors if it doesn't exist
try:
    with open("style.css", "w") as f:
        f.write("""
        /* General Body Styles */
        body {
            background-color: #f0f2f6; /* Fallback color */
        }

        /* Main App Container */
        [data-testid="stAppViewContainer"] {
            background-image: linear-gradient(135deg, #8BC6EC 0%, #9599E2 100%);
            font-family: 'Poppins', sans-serif;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: rgba(255, 255, 255, 0.5);
            backdrop-filter: blur(10px);
        }

        /* Main Content Styling */
        .main-content {
            background-color: rgba(255, 255, 255, 0.7);
            padding: 2rem;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.18);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        }
        
        /* Button Styling */
        .stButton > button {
            border: 2px solid #ffffff;
            border-radius: 10px;
            color: #ffffff;
            background-color: #ff4b4b;
            padding: 10px 20px;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            background-color: #ffffff;
            color: #ff4b4b;
            border-color: #ff4b4b;
        }

        /* Special button for answers */
        .stButton > button[kind="secondary"] {
             background-color: #4b8bff;
        }
        .stButton > button[kind="secondary"]:hover {
            color: #4b8bff;
            border-color: #4b8bff;
        }

        /* Text Input Styling */
        .stTextInput > div > div > input {
            border-radius: 10px;
            border: 2px solid #9599E2;
            background-color: #f0f2f6;
        }
        
        /* Title Styling */
        h1, h2, h3 {
            color: #31333F;
        }
        
        /* Game PIN Display */
        .game-pin-display {
            font-size: 3rem;
            font-weight: bold;
            color: #31333F;
            text-align: center;
            background-color: #ffffff;
            padding: 1rem;
            border-radius: 10px;
            letter-spacing: 0.5rem;
            border: 3px dashed #9599E2;
        }
        """)
    local_css("style.css")
except FileNotFoundError:
    # This block is for local development if style.css is in a different path
    pass


# --- Firebase Authentication ---
try:
    st.session_state.db = firestore.Client.from_service_account_info(
        st.secrets["FIRESTORE_CREDENTIALS"]
    )
except Exception as e:
    st.error("🔥 Firebase connection failed. Did you set up your Streamlit secret correctly?")
    st.stop()

# --- Helper function to parse the text file ---
def parse_text_quiz(text_contents):
    quiz_data = []
    current_question = None
    lines = text_contents.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            if current_question and 'question' in current_question and 'answer' in current_question and current_question.get('options'):
                quiz_data.append(current_question)
            current_question = None
            continue
        if current_question is None:
            current_question = {"options": []}
        if line.startswith("Q:"):
            current_question["question"] = line[2:].strip()
        elif line.startswith("O:"):
            current_question["options"].append(line[2:].strip())
        elif line.startswith("A:"):
            current_question["answer"] = line[2:].strip()
    if current_question and 'question' in current_question and 'answer' in current_question and current_question.get('options'):
        quiz_data.append(current_question)
    return quiz_data

# --- Firestore Functions ---
def generate_game_pin():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

def create_game_session(host_name, quiz_data):
    game_pin = generate_game_pin()
    game_ref = st.session_state.db.collection("games").document(game_pin)
    shuffled_questions = random.sample(quiz_data, len(quiz_data))
    game_data = {
        "host": host_name, "players": {}, "questions": shuffled_questions,
        "current_question_index": -1, "status": "waiting",
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    game_ref.set(game_data)
    return game_pin

def get_game_state(game_pin):
    if not game_pin: return None
    game_ref = st.session_state.db.collection("games").document(game_pin)
    game_doc = game_ref.get()
    return game_doc.to_dict() if game_doc.exists else None

def join_game(game_pin, player_name):
    game_ref = st.session_state.db.collection("games").document(game_pin)
    @firestore.transactional
    def update_in_transaction(transaction, game_ref, player_name):
        snapshot = game_ref.get(transaction=transaction)
        players = snapshot.get("players")
        if player_name not in players:
            players[player_name] = 0
            transaction.update(game_ref, {"players": players})
            return True
        return False
    return update_in_transaction(st.session_state.db.transaction(), game_ref, player_name)

def update_game_state(game_pin, new_state):
    game_ref = st.session_state.db.collection("games").document(game_pin)
    game_ref.update(new_state)

# --- UI Components ---
def show_leaderboard(players):
    st.sidebar.header("🏆 Leaderboard")
    if not players:
        st.sidebar.write("No players yet...")
        return
    sorted_players = sorted(players.items(), key=lambda item: item[1], reverse=True)
    for i, (name, score) in enumerate(sorted_players):
        medal = ""
        if i == 0: medal = "🥇"
        elif i == 1: medal = "🥈"
        elif i == 2: medal = "🥉"
        st.sidebar.markdown(f"**{medal} {name}**: {score}")

# --- Main App Logic ---
st.title("🚀 Streamlit Kahoot Clone")

if 'role' not in st.session_state: st.session_state.role = None

if st.session_state.role is None:
    with st.container(border=True):
        st.header("👋 Welcome! Are you a Host or a Player?")
        col1, col2 = st.columns(2)
        if col1.button("👩‍🏫 I am the Host", use_container_width=True):
            st.session_state.role = "host"
            st.rerun()
        if col2.button("🧑‍🎓 I am a Player", use_container_width=True, type="secondary"):
            st.session_state.role = "player"
            st.rerun()

# --- HOST VIEW ---
elif st.session_state.role == "host":
    if 'game_pin' not in st.session_state:
        with st.container(border=True):
            st.header("✨ Create a New Game")
            host_name = st.text_input("Enter your name as Host:")
            uploaded_file = st.file_uploader("Upload Quiz TXT file", type="txt")
            with st.expander("Click to see TXT format example"):
                st.code("""
Q: What is 2+2?
O: 3
O: 4
O: 5
A: 4

Q: What is the capital of Japan?
O: Seoul
O: Beijing
O: Tokyo
A: Tokyo
                """, language="text")

            # --- FIX: Use a single button and check conditions inside ---
            if st.button("Create New Game", use_container_width=True):
                if host_name and uploaded_file:
                    try:
                        stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
                        text_contents = stringio.read()
                        quiz_data = parse_text_quiz(text_contents)
                        if quiz_data:
                            st.session_state.game_pin = create_game_session(host_name, quiz_data)
                            st.rerun()
                        else:
                            st.error("Invalid TXT format or empty file.")
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                else:
                    st.warning("Please enter your name and upload a quiz file.")
    else:
        game_pin = st.session_state.game_pin
        game_state = get_game_state(game_pin)
        if not game_state: st.error("Game not found."); st.stop()

        st.header(f"Host Dashboard 🎮")
        st.markdown(f"<div class='game-pin-display'>{game_pin}</div>", unsafe_allow_html=True)
        st.info("Share this PIN with your players!")
        
        show_leaderboard(game_state.get("players", {}))
        current_q_index = game_state.get("current_question_index", -1)

        with st.container(border=True):
            if game_state["status"] == "waiting":
                st.subheader("Waiting for players to join...")
                if st.button("Start Game", disabled=not game_state.get("players"), use_container_width=True):
                    update_game_state(game_pin, {"status": "in_progress", "current_question_index": 0})
            
            elif game_state["status"] == "in_progress":
                st.subheader(f"Question {current_q_index + 1}/{len(game_state['questions'])}")
                question = game_state["questions"][current_q_index]
                st.title(question["question"])
                if st.toggle("Show Correct Answer", key=f"show_answer_{current_q_index}"):
                    st.success(f"**Answer:** {question['answer']}")
                if st.button("Next Question", use_container_width=True, type="primary"):
                    if current_q_index + 1 < len(game_state["questions"]):
                        update_game_state(game_pin, {"current_question_index": current_q_index + 1})
                    else:
                        update_game_state(game_pin, {"status": "finished"})
            
            elif game_state["status"] == "finished":
                st.balloons()
                st.header("🎉 Quiz Finished! 🎉")
        
        time.sleep(2); st.rerun()

# --- PLAYER VIEW ---
elif st.session_state.role == "player":
    if 'game_pin' not in st.session_state:
        with st.container(border=True):
            st.header("👋 Join a Game")
            player_name = st.text_input("Your Name:")
            game_pin_input = st.text_input("Game PIN:", max_chars=4)
            if st.button("Join Game", use_container_width=True, type="secondary") and player_name and game_pin_input:
                game_pin_input = game_pin_input.upper()
                if get_game_state(game_pin_input):
                    if join_game(game_pin_input, player_name):
                        st.session_state.player_name = player_name
                        st.session_state.game_pin = game_pin_input
                        st.rerun()
                    else:
                        st.error("This name is already taken.")
                else:
                    st.error("Invalid Game PIN.")
    else:
        game_pin = st.session_state.game_pin
        player_name = st.session_state.player_name
        game_state = get_game_state(game_pin)
        if not game_state: st.error("Game session ended."); st.stop()

        st.sidebar.info(f"Playing as: **{player_name}**")
        show_leaderboard(game_state.get("players", {}))
        current_q_index = game_state.get("current_question_index", -1)
        
        with st.container(border=True):
            if game_state["status"] == "waiting":
                st.info("⏳ Waiting for the host to start the game...")
            
            elif game_state["status"] == "in_progress":
                if f"answered_{current_q_index}" in st.session_state:
                    st.info("Waiting for the next question...")
                else:
                    question = game_state["questions"][current_q_index]
                    st.subheader(f"Question {current_q_index + 1}")
                    st.title(question["question"])
                    
                    answer_icons = ["🟥", "🔷", "🟡", "💚"]
                    cols = st.columns(2)
                    for i, option in enumerate(question["options"]):
                        with cols[i % 2]:
                            if st.button(f"{answer_icons[i]} {option}", use_container_width=True, key=f"opt_{i}"):
                                st.session_state[f"answered_{current_q_index}"] = True
                                if option == question["answer"]:
                                    st.balloons()
                                    st.success("Correct!")
                                    player_score_field = f"players.{player_name}"
                                    game_ref = st.session_state.db.collection("games").document(game_pin)
                                    game_ref.update({player_score_field: firestore.Increment(1)})
                                else:
                                    st.error("Incorrect!")
                                time.sleep(1); st.rerun()

            elif game_state["status"] == "finished":
                st.balloons(); st.header("🎉 Quiz Finished! 🎉")

        time.sleep(2); st.rerun()
