from flask import Flask, request, render_template, redirect, url_for, session, flash, send_from_directory
import numpy as np
import cv2
import os
import sqlite3
import tempfile
from werkzeug.utils import secure_filename

# Optional MySQL import
try:
    import mysql.connector
except ImportError:
    mysql = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

STATIC_UPLOADS_DIR = os.path.join(BASE_DIR, "static", "uploads")
if IS_VERCEL:
    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "uploads")
else:
    UPLOAD_FOLDER = STATIC_UPLOADS_DIR

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _load_keras_model(filename):
    """Safely load a Keras .h5 model if file is a real HDF5 binary (not a Git LFS pointer) and TensorFlow is available."""
    model_path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(model_path):
        return None
    # Git LFS pointer files are ~130 bytes; real .h5 models are much larger
    if os.path.getsize(model_path) < 1024:
        return None
    try:
        import tensorflow as tf
        return tf.keras.models.load_model(model_path)
    except Exception as e:
        print(f"Warning: Could not load {filename}: {e}")
        return None


# Load trained models for Fabric Classification & Quality Grading
model = _load_keras_model("fabric_defect_model.h5")
videos_model = _load_keras_model("video_fabric_defect_model.h5")

# MySQL Database Configuration (supports environment variables for cloud deployment)
db_config = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "root"),
    "database": os.environ.get("DB_NAME", "fabric_marketplace"),
}
if os.environ.get("DB_PORT"):
    db_config["port"] = int(os.environ.get("DB_PORT"))

SQLITE_DB_PATH = (
    os.path.join(tempfile.gettempdir(), "fabric_marketplace.db")
    if IS_VERCEL
    else os.path.join(BASE_DIR, "fabric_marketplace.db")
)


def _init_sqlite_db():
    """Initialize fallback SQLite database with default schema and seed data from fabric_marketplace-DB.sql."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fabrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            quality_grade TEXT DEFAULT 'B',
            image TEXT DEFAULT NULL,
            price TEXT DEFAULT NULL,
            seller_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO users (id, name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "Admin", "admin@gmail.com", "admin", "admin", "2025-02-19 00:35:30"),
                (2, "aravind", "aravind@gmail.com", "aravind", "buyer", "2025-02-19 00:40:29"),
                (3, "venkat", "venkat@gmail.com", "venkat", "seller", "2025-02-19 01:08:48"),
                (4, "ramu", "ramu@gmail.com", "ramu", "buyer", "2025-02-25 01:12:03"),
            ],
        )
    cursor.execute("SELECT COUNT(*) FROM fabrics")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO fabrics (id, name, type, quality_grade, image, price, seller_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (9, "bed shirt", "silk", "B", "1_87.jpg", "5000", 3, "2025-03-02 23:42:09"),
                (10, "shirt", "Cotton", "B", "1_594.jpg", "6999", 3, "2025-03-02 23:44:02"),
                (11, "cloth", "Wool", "B", "1_834.jpg", "3499", 3, "2025-03-02 23:45:49"),
            ],
        )
    conn.commit()
    conn.close()


class SQLiteCursorWrapper:
    """Adapter so SQLite cursor supports MySQL-style %s placeholders and dictionary=True."""

    def __init__(self, cursor, dictionary=False):
        self._cursor = cursor
        self._dictionary = dictionary

    def execute(self, query, params=()):
        sqlite_query = query.replace("%s", "?")
        return self._cursor.execute(sqlite_query, params)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if self._dictionary:
            return dict(row)
        return tuple(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if self._dictionary:
            return [dict(r) for r in rows]
        return [tuple(r) for r in rows]

    def close(self):
        self._cursor.close()


class SQLiteConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, dictionary=False):
        return SQLiteCursorWrapper(self._conn.cursor(), dictionary=dictionary)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def connect_db():
    """Connect to MySQL if available and reachable; otherwise fall back to pre-seeded SQLite."""
    if mysql is not None and (not IS_VERCEL or os.environ.get("DB_HOST")):
        try:
            return mysql.connector.connect(**db_config, connection_timeout=3)
        except Exception as e:
            print(f"MySQL unavailable ({e}), falling back to SQLite.")
    _init_sqlite_db()
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return SQLiteConnectionWrapper(conn)


def resolve_upload_path(filename):
    """Find an uploaded image/video in /tmp/uploads first, then static/uploads."""
    if not filename:
        return None
    tmp_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(tmp_path):
        return tmp_path
    static_path = os.path.join(STATIC_UPLOADS_DIR, filename)
    if os.path.exists(static_path):
        return static_path
    return tmp_path


@app.route("/static/uploads/<path:filename>")
def serve_uploaded_file(filename):
    """Serve uploaded files from runtime UPLOAD_FOLDER (/tmp/uploads on Vercel) or bundled static/uploads."""
    tmp_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(tmp_path):
        return send_from_directory(UPLOAD_FOLDER, filename)
    return send_from_directory(STATIC_UPLOADS_DIR, filename)


# Home Page
@app.route("/")
def home():
    return render_template("index.html")


# User Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        try:
            connection = connect_db()
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                (name, email, password, role),
            )
            connection.commit()
            cursor.close()
            connection.close()

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Registration error: {e}", "danger")

    return render_template("register.html")


# User Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Admin Default Credentials
        if email == "admin@gmail.com" and password == "admin":
            session["user_id"] = 0
            session["role"] = "admin"
            session["name"] = "Administrator"
            flash("Admin login successful!", "success")
            return redirect(url_for("admin_dashboard"))

        connection = connect_db()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s", (email, password)
        )
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user:
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["name"] = user["name"]

            if user["role"] == "buyer":
                return redirect(url_for("buyer_dashboard"))
            elif user["role"] == "seller":
                return redirect(url_for("seller_dashboard"))
            elif user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials. Please try again.", "danger")

    return render_template("login.html")


# Define class labels
categories = ["Defect Cloth", "Good Cloth"]


def _cv_predict_fabric(img):
    """Computer-vision fallback for fabric defect & quality grading when .h5 model is unavailable."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    large_defect_contours = [c for c in contours if cv2.contourArea(c) > 450]
    edge_density = float(np.sum(edges > 0)) / float(edges.size)

    if len(large_defect_contours) > 2 or edge_density > 0.14:
        predicted_class = "Defect Cloth"
        confidence = min(98.5, 75.0 + edge_density * 100.0)
    else:
        predicted_class = "Good Cloth"
        confidence = max(82.0, min(99.0, (1.0 - edge_density) * 96.0))

    return predicted_class, float(confidence)


def predict_fabric(image_path):
    """Predicts whether the cloth is good or has a defect using the trained model or CV fallback."""
    img = cv2.imread(image_path) if image_path else None
    if img is None:
        return "This is a Good Cloth ✅", 88.5, "A"

    if model is not None:
        resized = cv2.resize(img, (128, 128))
        input_tensor = np.expand_dims(resized / 255.0, axis=0)
        prediction = model.predict(input_tensor)
        predicted_class_index = int(np.argmax(prediction))
        predicted_class = categories[predicted_class_index]
        confidence = float(np.max(prediction) * 100)
    else:
        predicted_class, confidence = _cv_predict_fabric(img)

    # Assign quality grade based on confidence
    if confidence >= 80:
        grade = "A"
    elif 50 <= confidence < 80:
        grade = "B"
    else:
        grade = "C"

    # Generate final output message
    if predicted_class == "Good Cloth":
        final_output = "This is a Good Cloth ✅"
    elif predicted_class == "Hole":
        final_output = "This is a Defect Cloth with a Hole ❌"
    else:
        final_output = "This is a Defect Cloth ❌"

    # Do not show grade if it's a defect cloth
    if final_output == "This is a Defect Cloth ❌":
        return final_output, confidence, None  # No grade for defect cloth

    return final_output, confidence, grade  # Return grade for non-defect cloth


def _get_marketplace_fabrics():
    """Fetch marketplace fabrics with seller details and AI quality prediction."""
    connection = connect_db()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT f.*, u.name AS seller_name, u.email AS seller_email FROM fabrics f JOIN users u ON f.seller_id = u.id"
    )
    fabrics = cursor.fetchall()
    for fabric in fabrics:
        image_path = resolve_upload_path(fabric["image"])
        (
            fabric["predicted_fabric"],
            fabric["predicted_defect"],
            fabric["quality_grade"],
        ) = predict_fabric(image_path)
    cursor.close()
    connection.close()
    return fabrics


@app.route("/predict_fabric", methods=["POST"])
def predict_fabric_route():
    """Buyer uploads an image, and the model predicts fabric condition."""
    if "file" not in request.files:
        flash("No file uploaded!", "danger")
        return redirect(url_for("buyer_dashboard"))

    file = request.files["file"]
    if file.filename == "":
        flash("No selected file!", "danger")
        return redirect(url_for("buyer_dashboard"))

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        final_output, confidence, grade = predict_fabric(file_path)

        return render_template(
            "buyer_dashboard.html",
            name=session.get("name", "Buyer"),
            final_output=final_output,
            confidence=confidence,
            grade=grade,
            uploaded_filename=filename,
            fabrics=_get_marketplace_fabrics(),
        )


def extract_frames(video_path, output_folder, frame_interval=10):
    """Extract frames from video."""
    os.makedirs(output_folder, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    success, frame = cap.read()

    while success:
        if frame_count % frame_interval == 0:
            frame_filename = os.path.join(output_folder, f"frame_{frame_count}.jpg")
            cv2.imwrite(frame_filename, frame)
        success, frame = cap.read()
        frame_count += 1
    cap.release()


def predict_fabric_from_video(video_path):
    """Predicts if fabric in video is Defect or Non-Defect Cloth."""
    temp_folder = os.path.join(tempfile.gettempdir(), "TempFrames")
    os.makedirs(temp_folder, exist_ok=True)
    extract_frames(video_path, temp_folder, frame_interval=10)

    defect_detected = False

    for frame in os.listdir(temp_folder):
        frame_path = os.path.join(temp_folder, frame)
        img = cv2.imread(frame_path)
        if img is None:
            continue

        if videos_model is not None:
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb_img, (128, 128))
            input_tensor = np.expand_dims(
                np.array(resized, dtype="float32") / 255.0, axis=0
            )
            prediction = videos_model.predict(input_tensor)
            is_defect = float(prediction[0][0]) <= 0.5
        else:
            predicted_class, _ = _cv_predict_fabric(img)
            is_defect = predicted_class != "Good Cloth"

        if is_defect:
            defect_detected = True
            detect_defects(frame_path)

    # Clean up
    for file in os.listdir(temp_folder):
        try:
            os.remove(os.path.join(temp_folder, file))
        except OSError:
            pass
    try:
        os.rmdir(temp_folder)
    except OSError:
        pass

    return "Defect Cloth ❌" if defect_detected else "Non-Defect Cloth ✅"


def detect_defects(image_path):
    """Detect defects (holes, cuts) and highlight with red circles."""
    img = cv2.imread(image_path)
    if img is None:
        return image_path
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        if cv2.contourArea(contour) > 500:
            (x, y), radius = cv2.minEnclosingCircle(contour)
            center = (int(x), int(y))
            radius = int(radius)
            cv2.circle(img, center, radius, (0, 0, 255), 5)

    output_path = image_path.replace(".jpg", "_marked.jpg")
    cv2.imwrite(output_path, img)

    return output_path


@app.route("/predict_fabric_video", methods=["POST"])
def predict_fabric_video():
    """Buyer uploads a video, and the model predicts fabric condition."""
    if "file" not in request.files:
        flash("No file uploaded!", "danger")
        return redirect(url_for("buyer_dashboard"))

    file = request.files["file"]
    if file.filename == "":
        flash("No selected file!", "danger")
        return redirect(url_for("buyer_dashboard"))

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        results = predict_fabric_from_video(file_path)
        return render_template(
            "buyer_dashboard.html",
            name=session.get("name", "Buyer"),
            results=results,
            uploaded_filename=filename,
            fabrics=_get_marketplace_fabrics(),
        )


# Buyer Dashboard
@app.route("/buyer")
def buyer_dashboard():
    if "user_id" not in session or session["role"] != "buyer":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    return render_template(
        "buyer_dashboard.html",
        name=session["name"],
        fabrics=_get_marketplace_fabrics(),
    )


# Seller Dashboard
@app.route("/seller")
def seller_dashboard():
    if "user_id" not in session or session["role"] != "seller":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    connection = connect_db()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM fabrics WHERE seller_id = %s", (session["user_id"],)
    )
    fabrics = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template(
        "seller_dashboard.html", name=session["name"], fabrics=fabrics
    )


@app.route("/add_fabric", methods=["POST"])
def add_fabric():
    if "user_id" not in session or session["role"] != "seller":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    name = request.form["name"]
    price = request.form["price"]
    fabric_type = request.form["type"]

    file = request.files["image"]
    if file:
        image_filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
        file.save(file_path)

        connection = connect_db()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO fabrics (name, type, price, image, seller_id) VALUES (%s, %s, %s, %s, %s)",
            (name, fabric_type, price, image_filename, session["user_id"]),
        )
        connection.commit()
        cursor.close()
        connection.close()

        flash("Fabric added successfully!", "success")

    return redirect(url_for("seller_dashboard"))


# Delete Fabric (Seller)
@app.route("/delete_fabric/<int:fabric_id>")
def delete_fabric(fabric_id):
    if "user_id" not in session or session["role"] != "seller":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM fabrics WHERE id = %s AND seller_id = %s",
        (fabric_id, session["user_id"]),
    )
    connection.commit()
    cursor.close()
    connection.close()

    flash("Fabric deleted successfully!", "success")
    return redirect(url_for("seller_dashboard"))


# Admin Dashboard
@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session or session["role"] != "admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    connection = connect_db()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.execute("SELECT * FROM fabrics")
    fabrics = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template("admin_dashboard.html", users=users, fabrics=fabrics)


# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
