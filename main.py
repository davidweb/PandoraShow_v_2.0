import random
import string
import time
import json
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from models import db, User  # Assurez-vous que models.py définit db et le modèle User

app = Flask(__name__)
app.config["SECRET_KEY"] = "UNE_CLE_SECRETE_LONGUE"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pandora_show.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# --- Service Utilisateurs / Profils ---
players = {}  # Exemple: {"user_id": {"username": "Alice", "team": None, "score_individuel": 0}}
scores = {1: 0, 2: 0}

# --- Service Quiz ---
current_theme = "Aucun thème sélectionné"
countdown_seconds = 0
countdown_running = False
quiz_questions = []         # Chargées depuis questions.json
current_quiz_question_index = -1  # Index de la question actuelle
answered_users = set()      # Pour éviter plusieurs réponses correctes pour une même question

# --- Service Chat ---
chat_history = []  # Stocke l'historique des messages du chat

# --- Service Administration ---
ADMIN_PASSWORD = "123456"

# -------------------------------
# Fonctions utilitaires
# -------------------------------
def generate_user_id():
    """Génère un ID unique (ex. 'ABC123') pour identifier un joueur."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def auto_assign_teams():
    all_player_ids = list(players.keys())
    random.shuffle(all_player_ids)
    half = len(all_player_ids) // 2
    for i, pid in enumerate(all_player_ids):
        players[pid]["team"] = 1 if i < half else 2

def get_current_quiz_question():
    global quiz_questions, current_quiz_question_index
    if 0 <= current_quiz_question_index < len(quiz_questions):
        return quiz_questions[current_quiz_question_index]
    return None

def set_next_quiz_question():
    global current_quiz_question_index, answered_users
    current_quiz_question_index += 1
    answered_users.clear()  # Réinitialiser pour la nouvelle question
    return get_current_quiz_question()

def normalize_answer(answer):
    """Normalise une chaîne : suppression des espaces superflus et mise en minuscules."""
    return answer.strip().lower()

def load_quiz_questions():
    global quiz_questions
    try:
        with open("questions.json", "r", encoding="utf-8") as f:
            quiz_questions = json.load(f)
        print(f"Questions chargées: {len(quiz_questions)} questions")
    except Exception as e:
        print("Erreur lors du chargement des questions:", e)

# -------------------------------
# Routes Flask
# -------------------------------
@app.route("/")
def index():
    user_id = session.get("user_id")
    if not user_id or user_id not in players:
        return redirect(url_for("login"))
    user = User.query.filter_by(username=session["username"]).first()
    return render_template("index.html", user=user)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        if username:
            user_id = generate_user_id()
            players[user_id] = {"username": username, "team": None, "score_individuel": 0}
            session["user_id"] = user_id
            session["username"] = username
            # Crée l'utilisateur dans la base s'il n'existe pas déjà
            if not User.query.filter_by(username=username).first():
                new_user = User(username=username, score=0)
                db.session.add(new_user)
                db.session.commit()
            return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    user_id = session.get("user_id")
    if user_id and user_id in players:
        del players[user_id]
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin", methods=["GET", "POST"])
def admin():
    is_admin = session.get("is_admin", False)
    if not is_admin:
        if request.method == "POST":
            pwd = request.form.get("password")
            if pwd == ADMIN_PASSWORD:
                session["is_admin"] = True
                return redirect(url_for("admin"))
            else:
                return render_template("admin.html", error="Mot de passe incorrect.")
        else:
            return render_template("admin.html", error=None)
    else:
        return render_template("admin.html", error=None)

@app.route("/admin_logout")
def admin_logout():
    session["is_admin"] = False
    return redirect(url_for("index"))

@app.route("/auto_teams", methods=["POST"])
def route_auto_teams():
    auto_assign_teams()
    scores[1] = 0
    scores[2] = 0
    socketio.emit("teams_updated", {"players": players, "scores": scores})
    return redirect(url_for("admin"))

@app.route("/update_score", methods=["POST"])
def update_score():
    team = int(request.form.get("team", 0))
    points = int(request.form.get("points", 0))
    if team in scores:
        scores[team] += points
        socketio.emit("teams_updated", {"players": players, "scores": scores})
    return redirect(url_for("admin"))

@app.route("/start_countdown", methods=["POST"])
def start_countdown():
    global countdown_seconds, countdown_running
    seconds = int(request.form.get("seconds", 30))
    countdown_seconds = seconds
    countdown_running = True
    print(f"Countdown started on server for {seconds} seconds")
    socketio.emit("countdown_started", {"seconds": countdown_seconds})
    return redirect(url_for("admin"))

@app.route("/stop_countdown", methods=["POST"])
def stop_countdown():
    global countdown_running
    countdown_running = False
    print("Countdown stopped on server")
    socketio.emit("countdown_stopped")
    return redirect(url_for("admin"))

@app.route("/spin_roulette", methods=["POST"])
def spin_roulette():
    global current_theme
    theme_list = ["Culture Générale", "Cinéma", "Sport", "Musique", "Histoire", "Géographie", "Sciences", "Informatique"]
    chosen = random.choice(theme_list)
    current_theme = chosen
    socketio.emit("roulette_result", {"theme": chosen})
    return redirect(url_for("admin"))

@app.route("/roll_dice", methods=["POST"])
def roll_dice():
    result = random.randint(1, 6)
    socketio.emit("dice_result", {"value": result})
    return redirect(url_for("admin"))

@app.route("/next_question", methods=["POST"])
def next_question():
    next_q = set_next_quiz_question()
    if next_q:
        socketio.emit("quiz_question", {"question": next_q["question"]})
        session["current_quiz_answer"] = next_q["answer"]
    else:
        socketio.emit("quiz_question", {"question": "Fin des questions."})
        session["current_quiz_answer"] = None
    return redirect(url_for("admin"))

@app.route("/reveal_answer", methods=["POST"])
def reveal_answer():
    answer = session.get("current_quiz_answer")
    if answer:
        socketio.emit("quiz_answer", {"answer": answer})
    return redirect(url_for("admin"))

@app.route("/reset_game", methods=["POST"])
def reset_game():
    global scores, players, current_quiz_question_index, countdown_running, countdown_seconds, current_theme, chat_history
    scores = {1: 0, 2: 0}
    players = {}
    current_quiz_question_index = -1
    countdown_running = False
    countdown_seconds = 0
    current_theme = "Aucun thème sélectionné"
    chat_history = []  # Réinitialiser l'historique du chat
    session.pop("current_quiz_answer", None)
    socketio.emit("teams_updated", {"players": players, "scores": scores})
    socketio.emit("roulette_result", {"theme": current_theme})
    socketio.emit("quiz_question", {"question": ""})
    socketio.emit("countdown_stopped")
    socketio.emit("chat_history", chat_history)
    print("Game state reset by admin")
    return redirect(url_for("admin"))

# -------------------------------
# Événements SocketIO
# -------------------------------
@socketio.on("connect")
def on_connect():
    print("Client connected")
    # Envoyer l'état actuel du jeu au client qui vient de se connecter
    emit("teams_updated", {"players": players, "scores": scores})
    emit("roulette_result", {"theme": current_theme})
    if countdown_running:
        emit("countdown_started", {"seconds": countdown_seconds})
    current_q = get_current_quiz_question()
    if current_q:
        emit("quiz_question", {"question": current_q["question"]})
    # Envoyer l'historique du chat
    emit("chat_history", chat_history)
    # Démarrer la tâche de compte à rebours une seule fois
    if not hasattr(socketio, 'countdown_task_started'):
        socketio.start_background_task(countdown_task)
        socketio.countdown_task_started = True

@socketio.on("disconnect")
def on_disconnect():
    print("Client disconnected")

def countdown_task():
    global countdown_seconds, countdown_running
    while True:
        socketio.sleep(1)
        if countdown_running and countdown_seconds > 0:
            countdown_seconds -= 1
            print(f"[DEBUG] Countdown tick: {countdown_seconds} sec")
            socketio.emit("countdown_tick", {"seconds": countdown_seconds})
            if countdown_seconds <= 0:
                countdown_running = False
                print("[DEBUG] Countdown finished")
                socketio.emit("countdown_finished")

@socketio.on("chat_message")
def handle_chat_message(data):
    global chat_history
    message = data.get("message")
    user = data.get("user", "Anonyme")
    correct_flag = False
    if message:
        print(f"Message reçu de {user}: {message}")
        current_q = get_current_quiz_question()
        if countdown_running and current_q:
            correct_answer = normalize_answer(current_q["answer"])
            user_answer = normalize_answer(message)
            if user_answer == correct_answer and user not in answered_users:
                usr = User.query.filter_by(username=user).first()
                if usr:
                    usr.score += 1
                    db.session.commit()
                    print(f"Point individuel attribué à {user}")
                answered_users.add(user)
                correct_flag = True
        chat_entry = {"user": user, "message": message, "correct": correct_flag}
        chat_history.append(chat_entry)
        emit("chat_message", chat_entry, broadcast=True)

# Charger les questions au démarrage
load_quiz_questions()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
