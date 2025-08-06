import streamlit as st
import time
import random
import string
# You need to install this library: pip install google-cloud-firestore
from google.cloud import firestore

# --- Firebase Authentication ---
# IMPORTANT: Replace this with your own Firebase project's credentials.
# Follow these steps:
# 1. Go to your Firebase project console.
# 2. Go to Project Settings -> Service accounts.
# 3. Click "Generate new private key" and download the JSON file.
# 4. In Streamlit Cloud, go to your app's settings -> Secrets and add the
#    contents of the JSON file as a secret named "FIRESTORE_CREDENTIALS".

try:
    # Authenticate to Firestore with the credentials stored in Streamlit secrets
    st.session_state.db = firestore.Client.from_service_account_info(
        st.secrets["FIRESTORE_CREDENTIALS"]
    )
except Exception as e:
    st.error("🔥 Firebase connection failed. Did you set up your Streamlit secret correctly?")
    st.stop()


# --- Quiz Data (remains the same) ---
QUIZ_DATA = [
    {
        "question": "What is the capital of France?",
        "options": ["London", "Berlin", "Paris", "Madrid"],
        "answer": "Paris",
    },
    {
        "question": "Which planet is known as the Red Planet?",
        "options": ["Earth", "Mars", "Jupiter", "Venus"],
        "answer": "Mars",
    },
    {
        "question": "What is the largest mammal in the world?",
        "options": ["Elephant", "Blue Whale", "Giraffe", "Great White Shark"],
        "answer": "Blue Whale",
    },
    {
        "question": "In which year did the Titanic sink?",
        "options": ["1905", "1912", "1918", "1923"],
        "answer": "1912",
    },
    {
        "question": "What is the chemical symbol for Gold?",
        "options": ["Au", "Ag", "Go", "Gd"],
        "answer": "Au",
    },
]

# --- Helper Functions for Firestore ---

def generate_game_pin():
    """Generate a random 4-character pin."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

def create_game_session(host_name):
    """Creates a new game session in Firestore."""
    game_pin = generate_game_pin()
    game_ref = st.session_state.db.collection("games").document(game_pin)
    
    shuffled_questions = random.sample(QUIZ_DATA, len(QUIZ_DATA))

    game_data = {
        "host": host_name,
        "players": {}, # {player_name: score}
        "questions": shuffled_questions,
        "current_question_index": -1, # -1 means waiting to start
        "status": "waiting", # waiting, in_progress, finished
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    game_ref.set(game_data)
    return game_pin

def get_game_state(game_pin):
    """Retrieves the current game state from Firestore."""
    if not game_pin:
        return None
    game_ref = st.session_state.db.collection("games").document(game_pin)
    game_doc = game_ref.get()
    return game_doc.to_dict() if game_doc.exists else None

def join_game(game_pin, player_name):
    """Adds a player to a game session."""
    game_ref = st.session_state.db.collection("games").document(game_pin)
    # Use a transaction to safely update the player list
    @firestore.transactional
    def update_in_transaction(transaction, game_ref, player_name):
        snapshot = game_ref.get(transaction=transaction)
        players = snapshot.get("players")
        if player_name not in players:
            players[player_name] = 0 # Initial score
            transaction.update(game_ref, {"players": players})
            return True
        return False # Player name already exists
    
    return update_in_transaction(st.session_state.db.transaction(), game_ref, player_name)

def update_game_state(game_pin, new_state):
    """Updates a game's state in Firestore."""
    game_ref = st.session_state.db.collection("games").document(game_pin)
    game_ref.update(new_state)

# --- UI Components ---

def show_leaderboard(players):
    """Displays the leaderboard."""
    st.sidebar.subheader("🏆 Leaderboard")
    if not players:
        st.sidebar.write("No players yet.")
        return
    
    sorted_players = sorted(players.items(), key=lambda item: item[1], reverse=True)
    
    for name, score in sorted_players:
        st.sidebar.markdown(f"**{name}**: {score}")

# --- Main App Logic ---

st.title("🚀 Multiplayer Kahoot Clone")

# Role selection
if 'role' not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    col1, col2 = st.columns(2)
    if col1.button("I am the Host", use_container_width=True):
        st.session_state.role = "host"
        st.rerun()
    if col2.button("I am a Player", use_container_width=True):
        st.session_state.role = "player"
        st.rerun()

# --- HOST VIEW ---
elif st.session_state.role == "host":
    if 'game_pin' not in st.session_state:
        host_name = st.text_input("Enter your name as Host:")
        if st.button("Create New Game") and host_name:
            st.session_state.game_pin = create_game_session(host_name)
            st.rerun()
    else:
        game_pin = st.session_state.game_pin
        game_state = get_game_state(game_pin)

        if not game_state:
            st.error("Game not found.")
            st.stop()

        st.header(f"Host Dashboard - Game PIN: `{game_pin}`")
        st.write("Share this PIN with your players!")
        
        show_leaderboard(game_state.get("players", {}))
        
        current_q_index = game_state.get("current_question_index", -1)

        if game_state["status"] == "waiting":
            st.subheader("Waiting for players...")
            if st.button("Start Game", disabled=not game_state.get("players")):
                update_game_state(game_pin, {"status": "in_progress", "current_question_index": 0})
        
        elif game_state["status"] == "in_progress":
            st.subheader(f"Question {current_q_index + 1} of {len(game_state['questions'])}")
            question = game_state["questions"][current_q_index]
            st.title(question["question"])
            st.write(f"Correct Answer: **{question['answer']}**")

            if st.button("Next Question"):
                if current_q_index + 1 < len(game_state["questions"]):
                    update_game_state(game_pin, {"current_question_index": current_q_index + 1})
                else:
                    update_game_state(game_pin, {"status": "finished"})
        
        elif game_state["status"] == "finished":
            st.balloons()
            st.header("🎉 Quiz Finished! 🎉")
            st.subheader("Final Scores:")
            show_leaderboard(game_state.get("players", {}))

        # Auto-refresh for host to see player updates
        time.sleep(2)
        st.rerun()


# --- PLAYER VIEW ---
elif st.session_state.role == "player":
    if 'game_pin' not in st.session_state:
        player_name = st.text_input("Your Name:")
        game_pin_input = st.text_input("Game PIN:")
        if st.button("Join Game") and player_name and game_pin_input:
            game_pin_input = game_pin_input.upper()
            if get_game_state(game_pin_input):
                if join_game(game_pin_input, player_name):
                    st.session_state.player_name = player_name
                    st.session_state.game_pin = game_pin_input
                    st.rerun()
                else:
                    st.error("This name is already taken. Please choose another.")
            else:
                st.error("Invalid Game PIN. Please check and try again.")
    else:
        game_pin = st.session_state.game_pin
        player_name = st.session_state.player_name
        game_state = get_game_state(game_pin)

        if not game_state:
            st.error("Game session ended or not found.")
            st.stop()

        show_leaderboard(game_state.get("players", {}))
        
        current_q_index = game_state.get("current_question_index", -1)
        
        if game_state["status"] == "waiting":
            st.info("Waiting for the host to start the game...")
        
        elif game_state["status"] == "in_progress":
            # Check if player has already answered this question
            if f"answered_{current_q_index}" in st.session_state:
                st.info("Waiting for the host to show the next question...")
            else:
                question = game_state["questions"][current_q_index]
                st.subheader(f"Question {current_q_index + 1}")
                st.title(question["question"])
                
                for option in question["options"]:
                    if st.button(option, use_container_width=True):
                        st.session_state[f"answered_{current_q_index}"] = True
                        if option == question["answer"]:
                            # Safely increment score in Firestore
                            player_score_field = f"players.{player_name}"
                            game_ref = st.session_state.db.collection("games").document(game_pin)
                            game_ref.update({player_score_field: firestore.Increment(1)})
                            st.success("Correct!")
                        else:
                            st.error("Incorrect!")
                        time.sleep(1)
                        st.rerun()

        elif game_state["status"] == "finished":
            st.balloons()
            st.header("🎉 Quiz Finished! 🎉")
            st.subheader("Check the final leaderboard!")

        # Auto-refresh for players
        time.sleep(2)
        st.rerun()
