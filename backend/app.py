import os
import psycopg2
from flask import Flask, request, jsonify, g, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from dotenv import load_dotenv
import cohere
import logging

# Load environment variables from .env file
load_dotenv()

# Flask app setup
app = Flask(__name__)

# Choose the correct configuration based on FLASK_ENV
if os.getenv('FLASK_ENV') == 'production':
    app.config.from_object('settings.ProductionConfig')
else:
    app.config.from_object('settings.DevelopmentConfig')

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
CORS(app, origins=app.config['CORS_ORIGINS'])

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Cohere API client
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
co = cohere.Client(COHERE_API_KEY)

# In-memory user data
user_memory = {}

# Retrieve database URL from environment variable
DATABASE_URL = os.getenv('DATABASE_URL')


# Database connection
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logging.error(f"Error connecting to database: {e}")
        return None


# Create user table if it doesn't exist
def create_user_table():
    conn = get_db_connection()
    if conn is not None:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    history TEXT,
                    last_question TEXT
                )
            ''')
            conn.commit()
        conn.close()


# Middleware for logging and error handling
@app.before_request
def before_request_logging():
    g.start_time = datetime.datetime.utcnow()
    logging.info(f"Received request: {request.method} {request.path}")


@app.after_request
def after_request_logging(response):
    duration = (datetime.datetime.utcnow() - g.start_time).total_seconds()
    logging.info(f"Request processed in {duration} seconds")
    return response


@app.errorhandler(404)
def not_found_error(error):
    logging.error(f"404 Error: {error}")
    return make_response(jsonify({"error": "Resource not found"}), 404)


@app.errorhandler(500)
def internal_error(error):
    logging.error(f"500 Error: {error}")
    return make_response(jsonify({"error": "Internal server error"}), 500)


@app.before_request
def enforce_json():
    if request.method in ['POST', 'PUT', 'PATCH']:
        if not request.is_json:
            logging.warning(f"Non-JSON request rejected: {request.method} {request.path}")
            return jsonify({"error": "Invalid request format. JSON expected."}), 400


# Register route
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    hashed_password = generate_password_hash(data['password'])
    email = data['email']

    conn = get_db_connection()
    if conn is not None:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user_exists = cursor.fetchone()
            if user_exists:
                conn.close()
                return jsonify({"message": "User already exists"}), 400

            cursor.execute("INSERT INTO users (email, password, history, last_question) VALUES (%s, %s, %s, %s)",
                           (email, hashed_password, "", ""))
            conn.commit()
        conn.close()

    return jsonify({"message": "User registered successfully"}), 201


# Login route
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data['email']
    password = data['password']

    conn = get_db_connection()
    if conn is not None:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user[2], password):  # user[2] is the password field
                token = jwt.encode({
                    'user': email,
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
                }, app.config['SECRET_KEY'], algorithm="HS256")

                conn.close()
                return jsonify({
                    'token': token,
                    'user': {'email': user[1]}  # assuming user[1] is the email field
                }), 200

            conn.close()
            return jsonify({"message": "Invalid credentials"}), 401


# Chat route using Cohere
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    user_email = request.json.get("email")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    if user_email not in user_memory:
        user_memory[user_email] = {"name": None, "preferences": [], "history": [], "last_question": None}

    user_memory[user_email]["last_question"] = user_message
    user_memory[user_email]["history"].append(f"User: {user_message}")

    response = handle_message(user_email, user_message)
    user_memory[user_email]["history"].append(f"Bot: {response}")
    save_user_history(user_email, user_message, response)

    return jsonify({"response": response})


# Handle user messages
def handle_message(user_email, user_message):
    if "hello" in user_message.lower():
        return "Hi there! How can I help you today?"

    return call_cohere_api(user_message)


# Call Cohere API
def call_cohere_api(user_message):
    try:
        response = co.generate(
            model='command',
            prompt=user_message,
            max_tokens=100
        )
        return response.generations[0].text.strip()
    except Exception as e:
        logging.error(f"Error calling Cohere API: {str(e)}")
        return "Sorry, I encountered an error."


# Save user history
def save_user_history(email, question, response):
    conn = get_db_connection()
    if conn is not None:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET history = history || %s WHERE email = %s",
                (f"User: {question}\nBot: {response}", email)
            )
            conn.commit()
        conn.close()


# Initialize the user table on startup
if __name__ == "__main__":
    create_user_table()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
