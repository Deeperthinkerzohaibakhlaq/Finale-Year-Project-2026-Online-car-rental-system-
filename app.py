from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from datetime import date, timedelta, datetime
from groq import Groq
from classes.reservation import (
    Reservation, load_all_reservations, load_reservation_by_id,
    save_reservation_to_db, delete_reservation_from_db
)
import classes.user
import hashlib
import secrets
import socket
from urllib.parse import quote
import database as db
from database import add_balance_column
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from io import BytesIO
from pyngrok import ngrok
from flask import (
    Flask, render_template, request, jsonify, session, redirect,
    url_for, send_file, flash, make_response
)
from flask_mail import Mail, Message
from flask_cors import CORS, cross_origin
from classes.rentalSystem import RentalSystem
from classes.car import save_car_to_db, CAR_CLASS_MAP
import uuid
import pdfkit
import csv
import io
import pyotp
from booking_service import compute_total_hours, compute_price
import os
import json
import requests
from chatbot.chatbot_engine import FAQChatbot
from datetime import datetime, timezone
from flask_compress import Compress

# ---------- Payment module ----------
from payment_gateway import PaymentProcessor
import stripe

# ---------- App initialization ----------
app = Flask(__name__)
Compress(app)

# CORS for GPS endpoints
CORS(app, resources={
    r"/receive_gps": {"origins": "*"},
    r"/get_location/*": {"origins": "*"},
    r"/debug_locations": {"origins": "*"}
})

rentalSystem = RentalSystem()
app.secret_key = "auto-hire-rentals"

# ---------- Stripe keys ----------
app.config['STRIPE_PUBLIC_KEY'] = 'pk_test_51TZEcKEP3htfcKQ9ckRfnewSF9EPTxgLv8ev1bKjZ44khPGeL2FUHtih1nIIohppBQR7HmJNNl4qlA1XYfbCacfQ00ACQfSVY4'
app.config['STRIPE_SECRET_KEY'] = 'sk_test_51TZEcKEP3htfcKQ9HJ0y1F7P1JNvdhInLGhkCrsXTh4jiT28F20LPvhvsSvoTNsGf1atDlQlpmk3YR2G29iByG3D00c1vklVEH'

# ---------- Email configuration ----------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'zohaibakhlaq712@gmail.com'
app.config['MAIL_PASSWORD'] = 'ztgp jxum oonc kygw'
mail = Mail(app)

# ---------- Google Maps API key ----------
app.config['GOOGLE_MAPS_API_KEY'] = ''

# ---------- Chatbot ----------
try:
    chatbot = FAQChatbot(os.path.join(app.static_folder, 'chatbot_knowledge.json'))
except Exception as e:
    print(f"[WARNING] Chatbot init failed: {e}")
    chatbot = None

groq_api_key = "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"
groq_client = Groq(api_key=groq_api_key)

# ---------- Helper: compute admin fine ----------
def compute_admin_fine(reservation):
    if reservation.status != 'admin_cancelled' or not reservation.admin_cancelled_at:
        return 0
    days = (date.today() - reservation.admin_cancelled_at.date()).days
    return max(0, days * 1000)

@app.context_processor
def inject_helpers():
    return dict(compute_admin_fine=compute_admin_fine)

# ---------- Before request: refresh logged in user ----------
@app.before_request
def refresh_logged_in_user():
    if request.endpoint in ('login', 'register', 'verify', 'resend_otp', 'forgot_password',
                            'reset_password', 'static', None):
        return
    email = session.get('user_email')
    if email:
        user = rentalSystem.load_user_by_email(email)
        if user:
            rentalSystem.login_user(user)

# ---------- Real‑time GPS data ----------
REAL_TIME_GPS_DATA = {
    "Lexus-VIN-1234": {"lat": 31.5350, "lng": 74.3480, "status": "Moving"},
    "Honda-VIN-5678": {"lat": 31.5204, "lng": 74.3587, "status": "Parked"},
}

# ---------- Depot location ----------
def load_depot_location():
    default = {"lat": 31.5204, "lng": 74.3587, "name": "AutoHire Depot (Lahore)"}
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT lat, lng, name FROM depot WHERE id = 1")
            row = cur.fetchone()
            if row:
                return {"lat": float(row[0]), "lng": float(row[1]), "name": row[2]}
    except Exception as e:
        print("Error loading depot:", e)
    finally:
        db.release_connection(conn)
    return default

def save_depot_location(lat, lng, name=None):
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE depot SET lat = %s, lng = %s, name = %s WHERE id = 1",
                (float(lat), float(lng), name or f"AutoHire Depot ({lat}, {lng})")
            )
            conn.commit()
            return True
    except Exception as e:
        print("Error saving depot:", e)
        return False
    finally:
        db.release_connection(conn)

# ---------- OTP ----------
totp = pyotp.TOTP("JBSWY3DPEHPK3PXP", interval=300)

def send_otp_email(email, code):
    try:
        msg = Message('Auto-Hire Car Rental - Verify Email',
                      sender='zohaibakhlaq712@gmail.com',
                      recipients=[email])
        msg.body = f"Your verification code is: {code}. It expires in 5 minutes."
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def send_reset_email(email, reset_link):
    try:
        msg = Message('Auto-Hire - Reset Password',
                      sender='zohaibakhlaq712@gmail.com',
                      recipients=[email])
        msg.body = f"Click the link to reset your password: {reset_link}\nValid for 1 hour."
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Reset email error: {e}")
        return False

# ---------- Password reset helpers ----------
def generate_reset_token():
    return secrets.token_hex(32)

def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()

def create_password_reset(email):
    token = generate_reset_token()
    token_hash = hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE password_resets SET used = TRUE WHERE email = %s AND used = FALSE", (email,))
            cur.execute("INSERT INTO password_resets (email, token_hash, expires_at) VALUES (%s, %s, %s)",
                        (email, token_hash, expires_at))
            conn.commit()
    except Exception as e:
        print(f"Reset token error: {e}")
        return None
    finally:
        db.release_connection(conn)
    return token

def verify_reset_token(email, token):
    token_hash = hash_token(token)
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM password_resets WHERE email = %s AND token_hash = %s AND used = FALSE AND expires_at > NOW()",
                (email, token_hash)
            )
            return cur.fetchone() is not None
    finally:
        db.release_connection(conn)

def consume_reset_token(email, token):
    token_hash = hash_token(token)
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE password_resets SET used = TRUE WHERE email = %s AND token_hash = %s",
                        (email, token_hash))
            conn.commit()
    finally:
        db.release_connection(conn)

# ---------- User blocking reservation (updated to block admin_cancelled) ----------
def get_user_blocking_reservation(user_email):
    all_res = load_all_reservations()
    for r in all_res:
        if r.user_email == user_email and r.status in ('pending', 'admin_cancelled'):
            return r
    return None

def get_user_pending_reservation(user_email):
    all_res = load_all_reservations()
    for r in all_res:
        if r.user_email == user_email and r.status == 'pending':
            return r
    return None

# ---------- Notifications ----------
def add_user_notification(user_email, message, notif_type):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_notifications (user_email, message, type) VALUES (%s, %s, %s)",
                (user_email, message, notif_type)
            )
            conn.commit()
    finally:
        db.release_connection(conn)

def get_unread_notifications(user_email):
    conn = db.get_connection()
    notifs = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, message, type FROM user_notifications WHERE user_email = %s AND is_read = FALSE ORDER BY created_at",
                (user_email,)
            )
            for row in cur.fetchall():
                notifs.append({'id': row[0], 'message': row[1], 'type': row[2]})
    finally:
        db.release_connection(conn)
    return notifs

def mark_notification_read(notif_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE user_notifications SET is_read = TRUE WHERE id = %s", (notif_id,))
            conn.commit()
    finally:
        db.release_connection(conn)

# ---------- Unread inquiries helpers ----------
def get_unread_inquiries_count():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM inquiries WHERE is_read = FALSE")
            return cur.fetchone()[0]
    finally:
        db.release_connection(conn)

def mark_inquiries_read():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE inquiries SET is_read = TRUE WHERE is_read = FALSE")
            conn.commit()
    finally:
        db.release_connection(conn)

# ---------- Login decorator ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.endpoint in ["login", "register"]:
            return f(*args, **kwargs)
        if rentalSystem.get_user() is None:
            session.clear()
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# ---------- Database initialisation ----------
def init_payments_table():
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    reservation_id VARCHAR(255) NOT NULL,
                    user_email VARCHAR(255) NOT NULL,
                    amount NUMERIC(10,2) NOT NULL,
                    transaction_fee NUMERIC(10,2) DEFAULT 0,
                    payment_method VARCHAR(50) NOT NULL,
                    gateway_transaction_id VARCHAR(255),
                    status VARCHAR(20) DEFAULT 'pending',
                    refunded_amount NUMERIC(10,2) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS payment_id INTEGER REFERENCES payments(id)")
            conn.commit()
            print("[DB] Payments table ready.")
    except Exception as e:
        print(f"[DB] Payments init error: {e}")
    finally:
        db.release_connection(conn)

def init_inquiries_table():
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inquiries (
                    id SERIAL PRIMARY KEY,
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    phone VARCHAR(50) NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("ALTER TABLE inquiries ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT FALSE")
            conn.commit()
    except Exception as e:
        print(f"DB inquiries error: {e}")
    finally:
        db.release_connection(conn)

def init_password_resets_table():
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS password_resets (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    token_hash VARCHAR(255) NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE password_resets ALTER COLUMN expires_at TYPE TIMESTAMPTZ")
            conn.commit()
    except Exception as e:
        print(f"DB password_resets error: {e}")
    finally:
        db.release_connection(conn)

def init_reservation_columns():
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS start_time VARCHAR(10) DEFAULT '00:00'")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS end_time VARCHAR(10) DEFAULT '00:00'")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS early_refund NUMERIC(10,2)")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS late_fee NUMERIC(10,2)")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS admin_cancelled_at TIMESTAMP")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS deposit_amount NUMERIC(10,2) DEFAULT 0")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS deposit_refunded BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS insurance_selected BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS insurance_cost NUMERIC(10,2) DEFAULT 0")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS young_driver_fee NUMERIC(10,2) DEFAULT 0")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS damage_cost NUMERIC(10,2) DEFAULT 0")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS damage_status VARCHAR(20) DEFAULT 'none'")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS damage_description TEXT")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS damage_photos JSONB DEFAULT '[]'::jsonb")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS damage_waiver BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS damage_waiver_cost NUMERIC(10,2) DEFAULT 0")
            cur.execute("ALTER TABLE reservations DROP CONSTRAINT IF EXISTS reservations_status_check")
            cur.execute("ALTER TABLE reservations ADD CONSTRAINT reservations_status_check CHECK (status IN ('active','inactive','cancelled','pending','admin_cancelled'))")
            conn.commit()
    except Exception as e:
        print(f"DB reservation columns error: {e}")
    finally:
        db.release_connection(conn)

def init_wishlist_and_reviews():
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS wishlist (
                    user_email VARCHAR(255) NOT NULL,
                    car_vin VARCHAR(50) NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_email, car_vin),
                    FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE CASCADE,
                    FOREIGN KEY (car_vin) REFERENCES cars(vin) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id SERIAL PRIMARY KEY,
                    reservation_id VARCHAR(255) NOT NULL,
                    car_vin VARCHAR(50) NOT NULL,
                    user_email VARCHAR(255) NOT NULL,
                    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE CASCADE,
                    FOREIGN KEY (car_vin) REFERENCES cars(vin) ON DELETE CASCADE,
                    FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE CASCADE
                )
            """)
            conn.commit()
    except Exception as e:
        print(f"DB wishlist/reviews error: {e}")
    finally:
        db.release_connection(conn)

# Run all initialisations
init_inquiries_table()
init_password_resets_table()
init_reservation_columns()
init_wishlist_and_reviews()
init_payments_table()
add_balance_column()   # ensure balance column exists

# ---------- Context processor for admin unread inquiries ----------
@app.context_processor
def inject_admin_counts():
    if rentalSystem.get_user() and rentalSystem.get_user().get_role() == 'admin':
        return {'unread_inquiries': get_unread_inquiries_count()}
    return {}

# ---------- Global context processor ----------
@app.context_processor
def inject_globals():
    try:
        user = rentalSystem.get_user()
    except:
        user = None
    pending_count = 0
    if user and user.get_role() == "admin":
        all_res = load_all_reservations()
        pending_count = len([r for r in all_res if r.status == 'pending'])
    return dict(
        user=user,
        current_year=datetime.utcnow().year,
        show_pending_approvals=False,
        pending_count=pending_count,
    )

# ---------- Auto‑detect local IP and start ngrok ----------
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

app.config['SERVER_IP'] = get_local_ip()
print(f"[INFO] Local IP: {app.config['SERVER_IP']}")

public_url = None
def _start_ngrok(app):
    global public_url
    try:
        ngrok.kill()
        tunnel = ngrok.connect(5000, "http")
        public_url = tunnel.public_url
        print(f"[NGROK] Public URL: {public_url}")
        atexit.register(ngrok.kill)
    except Exception as e:
        print(f"[NGROK] Could not start tunnel: {e}")

import threading
threading.Thread(target=_start_ngrok, args=(app,), daemon=True).start()

# ---------- Routes ----------
@app.route('/tracker')
def tracker_page():
    return render_template('tracker_sender.html')

@app.route('/submit-inquiry', methods=['POST'])
def submit_inquiry():
    name = request.form.get('fullName', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    message = request.form.get('message', '').strip()
    if not name or not email or not phone or not message:
        flash('All fields required.', 'danger')
        return redirect(url_for('contact_page'))
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO inquiries (full_name, email, phone, message) VALUES (%s, %s, %s, %s)",
                        (name, email, phone, message))
            conn.commit()
        flash('Thank you! We will respond within 24 hours.', 'success')
    except Exception as e:
        print(f"Inquiry error: {e}")
        flash('An error occurred.', 'danger')
    finally:
        db.release_connection(conn)
    return redirect(url_for('contact_page'))

@app.route('/admin/inquiries')
@login_required
def admin_inquiries():
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    mark_inquiries_read()
    conn = db.get_connection()
    inquiries = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, full_name, email, phone, message, created_at FROM inquiries ORDER BY created_at DESC")
            inquiries = cur.fetchall()
    finally:
        db.release_connection(conn)
    return render_template('admin-inquiries.html', user=rentalSystem.get_user(), inquiries=inquiries)

@app.route('/admin/download/inquiries')
@login_required
def download_inquiries():
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT full_name, email, phone, message, created_at FROM inquiries ORDER BY created_at DESC")
            rows = cur.fetchall()
    finally:
        db.release_connection(conn)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Full Name', 'Email', 'Phone', 'Message', 'Date Submitted'])
    writer.writerows(rows)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=inquiries.csv"
    response.headers["Content-type"] = "text/csv"
    return response

# ---------- GPS endpoints ----------
@app.route('/receive_gps', methods=['GET', 'POST'])
@cross_origin(origins="*")
def receive_gps():
    vin = None
    lat = None
    lon = None
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        vin = data.get('id') or data.get('vin') or data.get('tracker_id')
        lat = data.get('lat') or data.get('latitude')
        lon = data.get('lon') or data.get('lng') or data.get('longitude')
        if not vin:
            vin = request.form.get('id') or request.form.get('vin')
        if not lat:
            lat = request.form.get('lat') or request.form.get('latitude')
        if not lon:
            lon = request.form.get('lon') or request.form.get('lng') or request.form.get('longitude')
    if not vin:
        vin = request.args.get('id') or request.args.get('vin')
    if not lat:
        lat = request.args.get('lat') or request.args.get('latitude')
    if not lon:
        lon = request.args.get('lon') or request.args.get('lng') or request.args.get('longitude')
    if not vin or lat is None or lon is None:
        return "Missing parameters", 400
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except Exception:
        return "Invalid lat/lon", 400
    vin = str(vin).strip()
    REAL_TIME_GPS_DATA[vin] = {
        'lat': lat_f,
        'lng': lon_f,
        'status': 'Moving',
        'updated_at': datetime.utcnow().isoformat() + 'Z'
    }
    return 'OK'

@app.route('/test_gps', methods=['GET', 'POST'])
def test_gps():
    return jsonify({'message': 'GPS test endpoint working'})

@app.route('/get_location/<vin>', methods=['GET'])
@cross_origin(origins="*")
def get_location(vin):
    vin = str(vin).strip()
    loc = REAL_TIME_GPS_DATA.get(vin) or REAL_TIME_GPS_DATA.get(vin.upper()) or REAL_TIME_GPS_DATA.get(vin.lower())
    if not loc:
        return jsonify({'error': 'No location data'}), 404
    return jsonify({
        'lat': loc.get('lat'),
        'lng': loc.get('lng'),
        'status': loc.get('status', 'Unknown'),
        'updated_at': loc.get('updated_at')
    })

@app.route('/debug_locations')
def debug_locations():
    if request.args.get('format') == 'json':
        return jsonify(REAL_TIME_GPS_DATA)
    rows = []
    for k, v in REAL_TIME_GPS_DATA.items():
        rows.append(f"<tr><td>{k}</td><td>{v.get('lat')}</td><td>{v.get('lng')}</td></tr>")
    html = f"<table border=1>{''.join(rows)}</table>"
    return html

@app.route("/api/car_location/<vin>", methods=["GET"])
@login_required
def get_car_location_api(vin):
    user = rentalSystem.get_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    loc = REAL_TIME_GPS_DATA.get(vin)
    if not loc:
        return jsonify({"error": "Location unavailable"}), 404
    return jsonify(loc)

@app.route("/track/<reservation_id>")
@login_required
def track_car(reservation_id):
    user = rentalSystem.get_user()
    reservation = rentalSystem.get_reservation_by_id(reservation_id)
    if not reservation or reservation.get_user_email() != user.get_email():
        flash("Unauthorized", "danger")
        return redirect("/")
    car = rentalSystem.fleet.get_car_by_vin(reservation.get_car_vin())
    depot = load_depot_location()
    client = {"lat": 31.5497, "lng": 74.3436, "name": "Customer Pickup Location"}
    if reservation.get_pickup_location():
        if isinstance(reservation.get_pickup_location(), dict):
            client = reservation.get_pickup_location()
        elif isinstance(reservation.get_pickup_location(), str):
            client['name'] = reservation.get_pickup_location()
    return render_template("tracking.html", user=user, car=car, reservation=reservation,
                           depot=depot, client=client, car_vin=car.get_vin(),
                           google_maps_api_key=app.config['GOOGLE_MAPS_API_KEY'])

@app.route("/api/car/availability/<vin>")
def car_availability(vin):
    all_res = load_all_reservations()
    booked = []
    for r in all_res:
        if r.get_car_vin() == vin and r.get_status() == 'active':
            booked.append({'start': r.get_start_date().isoformat(), 'end': r.get_end_date().isoformat()})
    return jsonify(booked)

@app.route('/admin/depot', methods=['GET', 'POST'])
@login_required
def admin_depot():
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    if request.method == 'POST':
        data = request.get_json() or {}
        lat = data.get('lat')
        lng = data.get('lng')
        name = data.get('name')
        if lat is None or lng is None:
            return jsonify({'success': False, 'message': 'lat/lng required'}), 400
        ok = save_depot_location(lat, lng, name)
        return jsonify({'success': ok})
    return render_template('admin_depot.html')

@app.route('/admin/track-reserved')
@login_required
def admin_track_reserved():
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    all_res = load_all_reservations()
    reserved = [r for r in all_res if r.status == 'active']
    enriched = []
    for r in reserved:
        car = rentalSystem.fleet.get_car_by_vin(r.car_vin)
        enriched.append({
            'id': r.id,
            'user_email': r.user_email,
            'car_vin': r.car_vin,
            'car_model': car.get_model() if car else 'Unknown',
            'start_date': r.start_date,
            'end_date': r.end_date,
            'pickup_location': r.pickup_location or '—',
            'return_location': r.return_location or '—',
            'status': r.status
        })
    return render_template('admin_track_reserved.html', user=rentalSystem.get_user(), reservations=enriched)

@app.route('/api/depot')
def api_depot():
    return jsonify(load_depot_location())

@app.context_processor
def inject_year():
    return {"current_year": datetime.now().year,
            "google_maps_api_key": app.config.get('GOOGLE_MAPS_API_KEY', ''),
            "depot": load_depot_location()}

def generate_csv_response(data, headers, filename):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(data)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/csv"
    return response

# ---------- Main pages ----------
@app.route("/")
def main():
    user = rentalSystem.get_user()
    if user:
        return redirect(url_for("index_page"))
    return render_template("pre-index.html", user=None, role=None, requested_page='home')

@app.route("/index")
@login_required
def index_page():
    user = rentalSystem.get_user()
    # Safety: if user is None for any reason, redirect to login
    if not user:
        return redirect("/login")
    
    if user.get_role() == "admin":
        return redirect(url_for("admin_index"))
    
    # user is guaranteed to be a valid user object here
    blocking_res = get_user_blocking_reservation(user.get_email())
    return render_template("index.html", 
                          user=user, 
                          role=user.get_role(), 
                          pending_res=blocking_res)
@app.route("/admin-index")
@login_required
def admin_index():
    user = rentalSystem.get_user()
    if not user or user.get_role() != "admin":
        flash("Access denied.", "danger")
        return redirect("/")
    return render_template("admin-index.html", user=user, role=user.get_role(), show_pending_approvals=True)

@app.route('/explore')
def explore_page():
    user = rentalSystem.get_user()
    role = user.get_role() if user else None
    cars = rentalSystem.fleet.get_cars()
    return render_template('explore.html', user=user, role=role, cars=cars)

@app.route('/about')
def about_page():
    user = rentalSystem.get_user()
    role = user.get_role() if user else None
    return render_template('about.html', user=user, role=role)

@app.route('/faqs')
def faqs_page():
    user = rentalSystem.get_user()
    role = user.get_role() if user else None
    return render_template('faqs.html', user=user, role=role)

@app.route('/contact')
def contact_page():
    user = rentalSystem.get_user()
    role = user.get_role() if user else None
    return render_template('contact.html', user=user, role=role)

# ---------- Login / Register / OTP ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if rentalSystem.get_user():
        return redirect(url_for("main"))
    if request.method == "POST":
        data = request.get_json()
        identifier = data.get("email", "").strip().lower()
        password = data.get("password")
        remember = data.get("remember", False)
        all_users = rentalSystem.get_all_users()
        user = None
        for u in all_users:
            if u.get_email().lower() == identifier or u.get_name().lower() == identifier:
                user = u
                break
        if user and check_password_hash(user.get_password_hash(), password):
            fresh_user = rentalSystem.load_user_by_email(user.get_email())
            if fresh_user:
                user = fresh_user
            rentalSystem.login_user(user)
            session["user_email"] = user.get_email()
            if remember:
                session.permanent = True
            return jsonify({"success": True, "isAdmin": user.get_role()})
        else:
            return jsonify({"success": False, "error": "password", "message": "Invalid credentials"})
    return render_template("login.html")

@app.route("/oauth-login", methods=["POST"])
def oauth_login():
    data = request.get_json()
    email = data.get("email")
    provider = data.get("provider")
    if not email:
        return jsonify({"success": False, "message": "No email"}), 400
    user = rentalSystem.load_user_by_email(email.lower())
    if user:
        rentalSystem.login_user(user)
        session["user_email"] = user.get_email()
        flash(f"Logged in with {provider}.", "success")
        return jsonify({"success": True, "redirect": url_for("index_page")})
    else:
        flash("Email not found. Please register.", "danger")
        return jsonify({"success": False, "message": "Email not found", "redirect": url_for("login")}), 404

@app.route("/logout")
def logout():
    session.clear()
    rentalSystem.logout_user()
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.get_json()
        email = data.get("email")
        if email and email.lower().endswith('@auto-hire.com'):
            return jsonify({"success": False, "message": "Registration with @auto-hire.com emails is not allowed."})
        if rentalSystem.load_user_by_email(email):
            return jsonify({"success": False, "message": "Email already exists!"})
        otp_code = totp.now()
        session['pending_email'] = email
        try:
            balance_deposit = float(data.get("balance_deposit") or 0)
        except (TypeError, ValueError):
            balance_deposit = 0.0
        session['pending_registration'] = {
            "name": data.get("name"),
            "email": email,
            "password": data.get("password"),
            "role": data.get("role"),
            "profile_image_url": data.get("profile_image_url", None),
            "license_number": data.get("license_number"),
            "license_expiry": data.get("license_expiry"),
            "birth_date": data.get("birth_date"),
            "balance": balance_deposit
        }
        session['otp'] = otp_code
        if send_otp_email(email, otp_code):
            return jsonify({"success": True})
        else:
            session.pop('pending_email', None)
            session.pop('pending_registration', None)
            session.pop('otp', None)
            if app.debug:
                print(f"OTP (email failed): {otp_code}")
                return jsonify({"success": True})
            return jsonify({"success": False, "message": "Could not send verification email."})
    return render_template("register.html")

@app.route("/check-unique", methods=["POST"])
def check_unique():
    data = request.get_json()
    field = data.get("field")
    value = data.get("value", "").strip()
    if field not in ("name", "email", "license_number") or not value:
        return jsonify({"exists": False, "error": "Invalid field"}), 400
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            if field == "name":
                cur.execute("SELECT EXISTS(SELECT 1 FROM users WHERE LOWER(name) = LOWER(%s))", (value,))
            elif field == "email":
                cur.execute("SELECT EXISTS(SELECT 1 FROM users WHERE LOWER(email) = LOWER(%s))", (value,))
            else:
                cur.execute("SELECT EXISTS(SELECT 1 FROM users WHERE license_number = %s)", (value,))
            exists = cur.fetchone()[0]
        return jsonify({"exists": bool(exists)})
    except Exception as e:
        print(f"Uniqueness error: {e}")
        return jsonify({"exists": False, "error": "Server error"}), 500
    finally:
        db.release_connection(conn)

@app.route("/verify", methods=["GET", "POST"])
def verify():
    if 'pending_email' not in session:
        return redirect(url_for('register'))
    if request.method == "POST":
        data = request.get_json()
        if data.get('otp') == session.get('otp'):
            session.pop('otp', None)
            pending = session.pop('pending_registration', {})
            email = session.pop('pending_email', None)
            if pending and email:
                password_hash = generate_password_hash(pending.get('password'))
                try:
                    initial_balance = float(pending.get("balance") or 0)
                except (TypeError, ValueError):
                    initial_balance = 0.0
                user_data = {
                    "name": pending.get("name"),
                    "email": email,
                    "password_hash": password_hash,
                    "role": pending.get("role"),
                    "profile_image_url": pending.get("profile_image_url"),
                    "license_number": pending.get("license_number"),
                    "license_expiry": pending.get("license_expiry"),
                    "rental_history": {"active": None, "inactive": []},
                    "birth_date": pending.get("birth_date"),
                    "balance": initial_balance
                }
                rentalSystem.register_user(user_data)

                flash("Account verified! Please login.", "success")
                return jsonify({"success": True})
        return jsonify({"success": False, "message": "Invalid or expired OTP."})
    return render_template("verify.html", email=session.get('pending_email', ''))

@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    if 'pending_email' in session:
        new_otp = totp.now()
        session['otp'] = new_otp
        if send_otp_email(session['pending_email'], new_otp):
            return jsonify({"success": True, "message": "New code sent."})
        else:
            return jsonify({"success": False, "message": "Email error."})
    return jsonify({"success": False, "message": "Session expired."}), 400

# ---------- Forgot / Reset password ----------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        flash("If the email exists, a reset link has been sent.", "info")
        user = rentalSystem.load_user_by_email(email)
        if user:
            token = create_password_reset(email)
            base_url = public_url if public_url else f"http://{app.config['SERVER_IP']}:5000"
            reset_link = f"{base_url}/reset-password/{token}?email={quote(email)}"
            send_reset_email(email, reset_link)
        return redirect(url_for('login'))
    return render_template("forgot-password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = request.args.get("email", "").strip().lower()
    if not email or not verify_reset_token(email, token):
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for('forgot_password'))
    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm = request.form.get("confirm_password")
        if new_password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("reset-password.html", token=token, email=email)
        user = rentalSystem.load_user_by_email(email)
        if not user:
            flash("User not found.", "danger")
            return redirect(url_for('login'))
        user.set_password_hash(generate_password_hash(new_password))
        rentalSystem.update_user(user)
        consume_reset_token(email, token)
        session.clear()
        flash("Password reset successfully. Please login.", "success")
        return redirect(url_for('login'))
    return render_template("reset-password.html", token=token, email=email)

# ---------- Profile ----------
@app.route("/profile")
@login_required
def profile():
    user = rentalSystem.get_user()
    if not user:
        return redirect("/login")
    
    active_res = None
    active_car = None
    inactive_items = []
    
    if user.get_role() == "user":
        active_id = user.get_active_reservation()
        if active_id:
            active_res = rentalSystem.get_reservation_by_id(active_id)
            if active_res:
                active_car = rentalSystem.fleet.get_car_by_vin(active_res.get_car_vin())
        
        for rid in user.get_inactive_reservations():
            res = rentalSystem.get_reservation_by_id(rid)
            if res:
                car = rentalSystem.fleet.get_car_by_vin(res.get_car_vin())
                # --- NEW: Check if review already exists ---
                has_review = False
                conn = db.get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM reviews WHERE reservation_id = %s", (rid,))
                        has_review = cur.fetchone() is not None
                finally:
                    db.release_connection(conn)
                inactive_items.append({"res": res, "car": car, "has_review": has_review})
    
    return render_template("profile.html",
                           user=user,
                           active_res=active_res,
                           active_car=active_car,
                           inactive_items=inactive_items)

@app.route("/edit-profile", methods=["POST"])
def edit_profile():
    user = rentalSystem.get_user()
    if not user:
        flash("Please login.", "danger")
        return redirect("/login")
    name = request.form.get("name", "").strip()
    profile_image = request.form.get("profile_image", "").strip()
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS(SELECT 1 FROM users WHERE LOWER(name)=LOWER(%s) AND LOWER(email)!=LOWER(%s))",
                        (name, user.get_email()))
            if cur.fetchone()[0]:
                flash("That name is already taken.", "danger")
                return redirect('/profile')
    finally:
        db.release_connection(conn)
    user.set_name(name)
    user.set_profile_image_url(profile_image)
    if user.get_role() == "user":
        license_number = request.form.get("license_number", "").strip()
        license_expiry = request.form.get("license_expiry", "").strip()
        birth_date_str = request.form.get("birth_date", "").strip()
        user.set_license_number(license_number)
        user.set_license_expiry(license_expiry)
        if birth_date_str:
            try:
                user.set_birth_date(datetime.strptime(birth_date_str, "%Y-%m-%d").date())
            except ValueError:
                flash("Invalid birth date.", "danger")
        else:
            user.set_birth_date(None)
    rentalSystem.update_user(user)
    flash("Profile updated.", "success")
    return redirect("/profile")

@app.route("/delete-account", methods=["POST"])
def delete_account():
    user = rentalSystem.get_user()
    if not user:
        flash("Please login.", "danger")
        return redirect("/login")
    rentalSystem.delete_user(user.get_email())
    session.clear()
    return redirect("/logout")

# ---------- Payment processing (always wallet) ----------
@app.route('/process-payment', methods=['POST'])
@login_required
def process_payment():
    data = request.get_json()
    user = rentalSystem.get_user()
    payment_method = data.get('method', 'wallet')
    if payment_method not in ('wallet', 'jazzcash', 'easypaisa', 'stripe', 'bank_transfer'):
        payment_method = 'wallet'
    amount = float(data['amount'])
    fee = 0
    total = amount
    reservation_data = data['reservation_data']

    if user.get_balance() < total:
        return jsonify({'success': False, 'message': f'Insufficient balance. Required: {total} PKR, Available: {user.get_balance()} PKR'})

    user.deduct_balance(total)
    rentalSystem.update_user(user)
    txn_id = f"{payment_method}_{uuid.uuid4()}"
    actual_fee = 0

    # Create reservation
    vin = reservation_data.get('car_vin')
    car = rentalSystem.fleet.get_car_by_vin(vin)
    if not car:
        return jsonify({'success': False, 'message': 'Car not found'})

    start_date = datetime.strptime(reservation_data['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(reservation_data['end_date'], '%Y-%m-%d').date()
    days = (end_date - start_date).days + 1
    total_cost = float(reservation_data.get('total_price', amount))

    insurance_selected = reservation_data.get('insurance') == '1'
    insurance_cost = 500 * days if insurance_selected else 0
    young_driver_fee = 0
    if user.get_birth_date():
        age = (date.today() - user.get_birth_date()).days // 365
        if 21 <= age < 25:
            young_driver_fee = 200 * days
    damage_waiver = reservation_data.get('damage_waiver') == '1'
    damage_waiver_cost = 300 * days if damage_waiver else 0

    reservation = Reservation(
        id=str(uuid.uuid4()),
        user_email=user.get_email(),
        car_vin=vin,
        start_date=start_date,
        end_date=end_date,
        start_time=reservation_data.get('start_time', '00:00'),
        end_time=reservation_data.get('end_time', '00:00'),
        cost=total_cost,
        status='pending',
        created_at=datetime.now(),
        pickup_location=reservation_data.get('pickup_location'),
        return_location=reservation_data.get('return_location'),
        deposit_amount=car.get_deposit_amount(),
        insurance_selected=insurance_selected,
        insurance_cost=insurance_cost,
        young_driver_fee=young_driver_fee,
        damage_waiver=damage_waiver,
        damage_waiver_cost=damage_waiver_cost
    )

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            # ✅ CORRECTED INSERT: includes start_time and end_time
            cur.execute("""
                INSERT INTO reservations (
                    id, user_email, car_vin, start_date, end_date,
                    start_time, end_time, cost, status,
                    created_at, pickup_location, return_location, deposit_amount,
                    insurance_selected, insurance_cost, young_driver_fee,
                    damage_waiver, damage_waiver_cost
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                reservation.id, reservation.user_email, reservation.car_vin,
                reservation.start_date, reservation.end_date,
                reservation.start_time, reservation.end_time,
                reservation.cost, reservation.status,
                reservation.created_at,
                reservation.pickup_location, reservation.return_location,
                reservation.deposit_amount, reservation.insurance_selected,
                reservation.insurance_cost, reservation.young_driver_fee,
                reservation.damage_waiver, reservation.damage_waiver_cost
            ))

            cur.execute("""
                INSERT INTO payments (
                    reservation_id, user_email, amount, transaction_fee,
                    payment_method, gateway_transaction_id, status
                ) VALUES (%s, %s, %s, %s, %s, %s, 'completed')
                RETURNING id
            """, (reservation.id, user.get_email(), total, actual_fee, payment_method, txn_id))
            payment_id = cur.fetchone()[0]

            cur.execute("UPDATE reservations SET payment_id = %s WHERE id = %s",
                        (payment_id, reservation.id))
            cur.execute("UPDATE users SET balance = %s WHERE email = %s",
                        (user.get_balance(), user.get_email()))

            car.set_rental_history("active", reservation.id)
            conn.commit()
    except Exception as e:
        conn.rollback()
        user.add_balance(total)
        rentalSystem.update_user(user)
        print(f"[PAYMENT ERROR] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
    finally:
        db.release_connection(conn)

    save_car_to_db(car)
    return jsonify({'success': True, 'reservation_id': reservation.id, 'transaction_id': txn_id})

# ---------- Return car (with fine handling from wallet) ----------
@app.route("/return-car", methods=["POST"])
@login_required
def return_car():
    user = rentalSystem.get_user()
    reservation = rentalSystem.get_reservation_by_id(user.get_active_reservation())
    if not reservation:
        flash("No active reservation found.", "warning")
        return redirect("/profile")

    car = rentalSystem.fleet.get_car_by_vin(reservation.get_car_vin())
    today = date.today()
    scheduled_end = reservation.get_end_date()
    message = ""
    early_refund_amount = 0
    late_fee_amount = 0

    conn = db.get_connection()
    payment_method = None
    original_txn_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT payment_method, gateway_transaction_id FROM payments WHERE reservation_id = %s", (reservation.id,))
            row = cur.fetchone()
            if row:
                payment_method, original_txn_id = row
    finally:
        db.release_connection(conn)

    # Admin cancellation fine
    if reservation.status == 'admin_cancelled':
        fine = compute_admin_fine(reservation)
        if fine > 0:
            # Always use wallet (since we removed top-up, all payments are wallet)
            if user.get_balance() >= fine:
                user.deduct_balance(fine)
                rentalSystem.update_user(user)
                conn2 = db.get_connection()
                try:
                    with conn2.cursor() as cur2:
                        cur2.execute("""
                            INSERT INTO payments (reservation_id, user_email, amount, transaction_fee, payment_method, gateway_transaction_id, status)
                            VALUES (%s, %s, %s, %s, 'wallet', %s, 'completed')
                        """, (reservation.id, user.get_email(), fine, 0, f"fine_{reservation.id}"))
                        conn2.commit()
                finally:
                    db.release_connection(conn2)
                message += f" Admin cancellation fine of {fine} PKR deducted from balance."
            else:
                flash(f"Insufficient balance to pay admin cancellation fine of {fine} PKR. Please contact support.", "danger")
                return redirect("/profile")
        reservation.admin_cancelled_at = None

    # Late / early return
    if today > scheduled_end:
        late_days = (today - scheduled_end).days
        late_fee_amount = late_days * 2000
        if late_fee_amount > 0:
            if user.get_balance() >= late_fee_amount:
                user.deduct_balance(late_fee_amount)
                rentalSystem.update_user(user)
                conn2 = db.get_connection()
                try:
                    with conn2.cursor() as cur2:
                        cur2.execute("""
                            INSERT INTO payments (reservation_id, user_email, amount, transaction_fee, payment_method, gateway_transaction_id, status)
                            VALUES (%s, %s, %s, %s, 'wallet', %s, 'completed')
                        """, (reservation.id, user.get_email(), late_fee_amount, 0, f"late_{reservation.id}"))
                        conn2.commit()
                finally:
                    db.release_connection(conn2)
                message += f" Late fee of {late_fee_amount} PKR deducted from balance."
            else:
                flash(f"Insufficient balance for late fee of {late_fee_amount} PKR.", "danger")
                return redirect("/profile")
    elif today < scheduled_end:
        early_days = (scheduled_end - today).days
        early_refund_amount = early_days * 500
        if early_refund_amount > 0:
            user.add_balance(early_refund_amount)
            rentalSystem.update_user(user)
            conn2 = db.get_connection()
            try:
                with conn2.cursor() as cur2:
                    cur2.execute("UPDATE payments SET refunded_amount = refunded_amount + %s WHERE reservation_id = %s",
                                 (early_refund_amount, reservation.id))
                    conn2.commit()
            finally:
                db.release_connection(conn2)
            message += f" Early return refund of {early_refund_amount} PKR added to balance."

    # Damage handling
    if reservation.damage_status == 'pending' and reservation.damage_cost > 0:
        deposit = reservation.deposit_amount
        if reservation.damage_waiver:
            cost = min(reservation.damage_cost, 2000)
        else:
            cost = reservation.damage_cost
        if deposit >= cost:
            reservation.deposit_amount -= cost
            reservation.damage_status = 'deducted'
            message += f" Damage cost {cost} PKR deducted from deposit."
        else:
            extra = cost - deposit
            if user.get_balance() >= extra:
                user.deduct_balance(extra)
                rentalSystem.update_user(user)
                conn2 = db.get_connection()
                try:
                    with conn2.cursor() as cur2:
                        cur2.execute("""
                            INSERT INTO payments (reservation_id, user_email, amount, transaction_fee, payment_method, gateway_transaction_id, status)
                            VALUES (%s, %s, %s, %s, 'wallet', %s, 'completed')
                        """, (reservation.id, user.get_email(), extra, 0, f"damage_{reservation.id}"))
                        conn2.commit()
                finally:
                    db.release_connection(conn2)
                message += f" Damage extra {extra} PKR deducted from balance."
            else:
                message += f" Insufficient balance for damage charge of {extra} PKR."
            reservation.deposit_amount = 0
            reservation.damage_status = 'deducted'

    # Deposit refund
    if reservation.deposit_amount > 0 and not reservation.deposit_refunded:
        refund_deposit = float(reservation.deposit_amount)
        user.add_balance(refund_deposit)
        rentalSystem.update_user(user)
        conn2 = db.get_connection()
        try:
            with conn2.cursor() as cur2:
                cur2.execute("UPDATE payments SET refunded_amount = refunded_amount + %s WHERE reservation_id = %s",
                             (refund_deposit, reservation.id))
                conn2.commit()
        finally:
            db.release_connection(conn2)
        message += f" Deposit of {refund_deposit} PKR refunded to balance."

    # Finalise reservation
    reservation.set_early_refund(early_refund_amount if early_refund_amount > 0 else None)
    if not reservation.get_late_fee() and late_fee_amount > 0:
        reservation.set_late_fee(late_fee_amount)

    reservation.set_return_date(today)
    reservation.set_status("inactive")
    user.set_rental_history("inactive", reservation.get_id())
    user.set_rental_history("active", None)
    car.set_rental_history("inactive", reservation.get_id())
    car.set_rental_history("delete", reservation.get_id())

    rentalSystem.save_all(user)
    save_reservation_to_db(reservation)

    flash("Car returned successfully. " + message, "success")
    return redirect("/profile")

# ---------- Admin fleet management (unchanged) ----------
@app.route("/admin/report-damage/<reservation_id>", methods=["GET", "POST"])
@login_required
def report_damage(reservation_id):
    if not rentalSystem.get_isAdmin():
        flash("Admin access required", "danger")
        return redirect("/")
    reservation = rentalSystem.get_reservation_by_id(reservation_id)
    if not reservation:
        flash("Reservation not found", "danger")
        return redirect("/admin-index")
    car = rentalSystem.fleet.get_car_by_vin(reservation.car_vin)
    if request.method == "POST":
        reservation.damage_cost = float(request.form.get("damage_cost", 0))
        reservation.damage_description = request.form.get("damage_desc", "")
        reservation.damage_status = 'pending'
        save_reservation_to_db(reservation)
        flash(f"Damage reported: {reservation.damage_cost} PKR will be deducted upon return.", "success")
        return redirect(url_for("admin_index"))
    return render_template("report_damage.html", reservation=reservation, car=car)

@app.route("/admin-fleet")
@login_required
def manage_fleet():
    if not rentalSystem.get_isAdmin():
        return "Access Denied", 403
    cars = rentalSystem.get_cars()
    return render_template("admin-fleet.html", user=rentalSystem.get_user(), role="admin", cars=cars)

@app.route("/admin/add_car", methods=["POST"])
@login_required
def add_car():
    if not rentalSystem.get_isAdmin():
        return redirect("/login")
    form = request.form
    category = form.get("car_type")
    CarClass = CAR_CLASS_MAP.get(category)
    if not CarClass:
        return "Invalid car type", 400
    vin = form.get("vin")
    model = form.get("model")
    base_rate = float(form.get("base_rate") or 0)
    img_url = form.get("img_url")
    seating_capacity = int(form.get("seating_capacity") or 0)
    colour = form.get("colour")
    car_type = category
    features = {
        "air_conditioning": "features[air_conditioning]" in form,
        "bluetooth": "features[bluetooth]" in form,
        "gps": "features[gps]" in form,
        "usb_ports": "features[usb_ports]" in form,
        "sunroof": "features[sunroof]" in form,
        "rear_camera": "features[rear_camera]" in form,
    }
    extra = {"rental_history": {"active": [], "inactive": []}}
    if category == "EconomyCar":
        extra["fuel_efficiency"] = float(form.get("fuel_efficiency", 0))
    elif category == "LuxuryCar":
        extra["chauffeur_available"] = form.get("chauffeur_available") == "1"
    elif category == "CommercialCar":
        extra["cargo_capacity"] = float(form.get("cargo_capacity", 0))
    car = CarClass(vin=vin, model=model, base_rate=base_rate, img_url=img_url,
                   seating_capacity=seating_capacity, colour=colour, car_type=car_type,
                   features=features, **extra)
    rentalSystem.fleet.add_car(car)
    rentalSystem.fleet.save_cars()
    return redirect(url_for("manage_fleet"))


@app.route("/admin/edit_car/<vin>", methods=["POST"])
@login_required
def edit_car(vin):
    if not rentalSystem.get_isAdmin():
        flash("Admin access required", "danger")
        return redirect("/login")
    
    car = rentalSystem.fleet.get_car_by_vin(vin)
    if not car:
        flash("Car not found", "danger")
        return redirect("/admin-fleet")
    
    form = request.form
    car.set_model(form.get("model"))
    car.set_base_rate(float(form.get("base_rate") or 0))
    car.set_img_url(form.get("img_url"))
    car.set_seating_capacity(int(form.get("seating_capacity") or 0))
    car.set_colour(form.get("colour"))
    
    features = {
        "air_conditioning": "features[air_conditioning]" in form,
        "bluetooth": "features[bluetooth]" in form,
        "gps": "features[gps]" in form,
        "usb_ports": "features[usb_ports]" in form,
        "sunroof": "features[sunroof]" in form,
        "rear_camera": "features[rear_camera]" in form,
    }
    car.set_features(features)
    
    category = car.get_car_type()
    if category == "EconomyCar" and hasattr(car, 'set_fuel_efficiency'):
        car.set_fuel_efficiency(float(form.get("fuel_efficiency", 0)))
    elif category == "LuxuryCar" and hasattr(car, 'set_chauffeur_available'):
        car.set_chauffeur_available(form.get("chauffeur_available") == "1")
    elif category == "CommercialCar" and hasattr(car, 'set_cargo_capacity'):
        car.set_cargo_capacity(float(form.get("cargo_capacity", 0)))
    
    save_car_to_db(car)
    rentalSystem.fleet.save_cars()      # persist to JSON as well
    flash("Car updated successfully.", "success")
    return redirect("/admin-fleet")      # ✅ correct URL

@app.route("/admin/delete_car/<vin>", methods=["POST"])
@login_required
def delete_car(vin):
    if not rentalSystem.get_isAdmin():
        return redirect("/login")
    rentalSystem.fleet.remove_car(vin)
    rentalSystem.fleet.save_cars()
    return redirect(url_for("manage_fleet"))

@app.route("/admin-report")
@login_required
def admin_reports():
    if not rentalSystem.get_isAdmin():
        flash("Access denied", "danger")
        return redirect("/")
    users = rentalSystem.get_all_users()
    cars = rentalSystem.fleet.get_cars()
    current_rentals = []
    for u in users:
        if u.get_role() == "user" and u.get_active_reservation():
            res = rentalSystem.get_reservation_by_id(u.get_active_reservation())
            if res:
                current_rentals.append({
                    "name": u.get_name(), "email": u.get_email(),
                    "car_vin": res.get_car_vin(),
                    "start_date": res.get_start_date(), "end_date": res.get_end_date()
                })
    reserved_cars = []
    for car in cars:
        for rid in car.get_active_reservation():
            res = rentalSystem.get_reservation_by_id(rid)
            if res:
                reserved_cars.append({
                    "vin": car.get_vin(), "model": car.get_model(),
                    "user_email": res.get_user_email(),
                    "start_date": res.get_start_date(), "end_date": res.get_end_date()
                })
    return render_template("admin-reports.html", current_rentals=current_rentals,
                           reserved_cars=reserved_cars, user=rentalSystem.get_user())

@app.route("/admin/download/customers")
def download_customers_report():
    if not rentalSystem.get_isAdmin():
        return redirect("/")
    data = []
    for u in rentalSystem.get_all_users():
        if u.get_role() != "user":
            continue
        rid = u.get_active_reservation()
        if rid:
            res = rentalSystem.get_reservation_by_id(rid)
            if res:
                data.append([u.get_name(), u.get_email(), res.get_car_vin(),
                             res.get_start_date().strftime("%Y-%m-%d"),
                             res.get_end_date().strftime("%Y-%m-%d")])
    return generate_csv_response(data, ["Name", "Email", "Car VIN", "Start Date", "End Date"], "customers_report.csv")

@app.route("/admin/download/reserved-cars")
def download_reserved_cars_report():
    if not rentalSystem.get_isAdmin():
        return redirect("/")
    data = []
    for car in rentalSystem.fleet.get_cars():
        for rid in car.get_active_reservation():
            res = rentalSystem.get_reservation_by_id(rid)
            if res:
                data.append([car.get_vin(), car.get_model(), res.get_user_email(),
                             res.get_start_date().strftime("%Y-%m-%d"),
                             res.get_end_date().strftime("%Y-%m-%d")])
    return generate_csv_response(data, ["VIN", "Model", "User Email", "Start Date", "End Date"], "reserved_cars_report.csv")

@app.route("/admin/send-reminders")
@login_required
def send_reminders():
    if not rentalSystem.get_isAdmin():
        flash("Admin only", "danger")
        return redirect("/")
    send_reminder_emails()
    flash("Reminder emails sent.", "success")
    return redirect("/admin-index")

# ---------- Booking and car listing ----------
@app.route('/book-query', methods=['POST'])
@login_required
def book_query():
    form = request.form
    pickup_date = form.get('pickup_date')
    pickup_time = form.get('pickup_time')
    return_date = form.get('return_date')
    return_time = form.get('return_time')
    pickup_loc = form.get('pickup_location')
    return_loc = form.get('return_location')
    if not pickup_date or not return_date or not pickup_time or not return_time:
        flash("Please provide valid dates and times.", "danger")
        return redirect('/')
    return redirect(url_for('available_cars', start=pickup_date, end=return_date,
                            start_time=pickup_time, end_time=return_time,
                            pickup_loc=pickup_loc, return_loc=return_loc))

def check_admin_cancelled_block(user):
    all_res = load_all_reservations()
    for r in all_res:
        if r.user_email == user.get_email() and r.status == 'admin_cancelled':
            return True
    return False

@app.route("/cars")
@login_required
def available_cars():
    user = rentalSystem.get_user()
    if check_admin_cancelled_block(user):
        flash("You have an admin-cancelled reservation. Please return the car and pay the fine before booking again.", "danger")
        return redirect("/profile")

    if user.get_role() == "user":
        active_id = user.get_active_reservation()
        if active_id:
            res = rentalSystem.get_reservation_by_id(active_id)
            if res and res.status in ('active','pending','admin_cancelled'):
                if res.status == 'admin_cancelled':
                    flash("Your reservation was cancelled by admin. Please return the car before booking another.", "danger")
                    return redirect("/profile")
                elif res.status == 'pending':
                    flash("You have a pending reservation. Please wait for approval.", "warning")
                    return redirect(url_for("waiting_approval", reservation_id=active_id))
                else:
                    flash("You already have an active reservation.", "warning")
                    return redirect("/profile")
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    car_type = request.args.get("type")
    start_time = request.args.get("start_time") or request.args.get("pickup_time")
    end_time = request.args.get("end_time") or request.args.get("return_time")
    pickup_loc = request.args.get("pickup_loc") or request.args.get("from")
    return_loc = request.args.get("return_loc") or request.args.get("to")
    if not start_str or not end_str:
        flash("Start and end dates required.", "danger")
        return redirect("/")
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        if start_date > end_date:
            raise ValueError
    except:
        flash("Invalid dates.", "danger")
        return redirect("/")
    filtered = rentalSystem.get_available_cars(start_date, end_date)
    if car_type:
        filtered = [c for c in filtered if c.get_car_type() == car_type]
    booking_context = None
    if start_time or end_time or pickup_loc or return_loc:
        booking_context = {'start_time': start_time, 'end_time': end_time,
                           'pickup_location': pickup_loc, 'return_location': return_loc}
    return render_template("available-cars.html", user=user, available_cars=filtered,
                           start_date=start_str, end_date=end_str, selected_type=car_type,
                           booking_context=booking_context)

@app.route("/cars/<vin>")
@login_required
def car_details(vin):
    user = rentalSystem.get_user()
    car = rentalSystem.fleet.get_car_by_vin(vin)
    if not car:
        return redirect("/cars")
    can_review = False
    completed_reservation_id = None
    review_for = request.args.get('review_for')
    if user.get_role() == 'user' and review_for:
        res = rentalSystem.get_reservation_by_id(review_for)
        if res and res.get_user_email() == user.get_email() and res.get_status() == 'inactive':
            conn = db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM reviews WHERE reservation_id = %s", (review_for,))
                    if not cur.fetchone():
                        completed_reservation_id = review_for
                        can_review = True
            finally:
                db.release_connection(conn)
    return render_template("car_details.html", user=user, car=car,
                           can_review=can_review, completed_reservation_id=completed_reservation_id)

@app.route("/reserve/<vin>", methods=["GET", "POST"])
@login_required
def reserve_car(vin):
    car = rentalSystem.fleet.get_car_by_vin(vin)
    if not car:
        flash("Car not found.", "danger")
        return redirect("/cars")
    user = rentalSystem.get_user()
    if check_admin_cancelled_block(user):
        flash("You have an admin-cancelled reservation. Please return the car and pay the fine before booking another.", "danger")
        return redirect("/profile")
    if user.get_role() == "admin":
        flash("Admins cannot make reservations.", "danger")
        return redirect("/")
    raw_start = request.args.get("start")
    raw_end = request.args.get("end")
    if not raw_start or not raw_end:
        flash("Start and end dates required.", "danger")
        return redirect(url_for("available_cars"))
    try:
        if "T" in raw_start:
            start_date = raw_start.split("T")[0]
            start_time_from_raw = raw_start.split("T")[1]
        else:
            start_date = raw_start
            start_time_from_raw = None
        if "T" in raw_end:
            end_date = raw_end.split("T")[0]
            end_time_from_raw = raw_end.split("T")[1]
        else:
            end_date = raw_end
            end_time_from_raw = None
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        if start > end:
            raise ValueError
        days = (end - start).days + 1
    except:
        flash("Invalid dates.", "danger")
        return redirect(url_for("available_cars"))

    def calc_age(bd):
        if not bd: return None
        today = date.today()
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    user_age = calc_age(user.get_birth_date())
    young_warning = None
    if user_age and 21 <= user_age < 25:
        young_warning = f"Young driver fee (21-24) applies: 200 PKR/day. Total extra: {days * 200} PKR."
    elif user_age and user_age < 21:
        young_warning = "You are under 21. You cannot rent a car."

    total_cost = car.calculate_rental_cost(days)
    return render_template("reserve-car.html", car=car, user=user, start=start_date, end=end_date,
                           days=days, cost=total_cost, young_driver_fee_warning=young_warning,
                           pickup_location=request.args.get("pickup_loc"),
                           return_location=request.args.get("return_loc"),
                           start_time=request.args.get("start_time") or start_time_from_raw,
                           end_time=request.args.get("end_time") or end_time_from_raw,
                           hours=request.args.get("hours"), price_breakdown=request.args.get("price_breakdown"))

# ---------- Waiting page ----------
@app.route('/waiting/<reservation_id>')
@login_required
def waiting_approval(reservation_id):
    user = rentalSystem.get_user()
    res = load_reservation_by_id(reservation_id)
    if not res or res.user_email != user.get_email():
        flash("Access denied.", "danger")
        return redirect("/")
    return render_template("waiting.html", reservation_id=reservation_id, user=user)

@app.route('/api/reservation-status/<rid>')
def reservation_status_api(rid):
    res = load_reservation_by_id(rid)
    if not res:
        return jsonify({"status": "error"}), 404
    return jsonify({"status": res.status})

# ---------- Admin approvals ----------
@app.route('/admin/pending-approvals')
@login_required
def admin_pending_approvals():
    if not rentalSystem.get_isAdmin():
        flash("Admin access required", "danger")
        return redirect("/")
    all_res = load_all_reservations()
    pending = [r for r in all_res if r.status == 'pending']
    return render_template("admin_pending.html", pending=pending, user=rentalSystem.get_user(), pending_count=len(pending))

@app.route('/admin/approve/<rid>', methods=['POST'])
@login_required
def admin_approve(rid):
    if not rentalSystem.get_isAdmin():
        return redirect("/")
    res = load_reservation_by_id(rid)
    if not res or res.status != 'pending':
        flash('Invalid reservation', 'danger')
        return redirect('/admin/pending-approvals')
    res.status = 'active'
    save_reservation_to_db(res)
    user = rentalSystem.load_user_by_email(res.user_email)
    user.set_rental_history('active', res.id)
    rentalSystem.update_user(user)
    add_user_notification(res.user_email, f"Your reservation {res.id} has been approved.", "admin_approve")
    flash('Reservation approved successfully.', 'success')
    return redirect(url_for('admin_reservation_detail', rid=rid))

@app.route('/admin/reservation/<rid>')
@login_required
def admin_reservation_detail(rid):
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    res = load_reservation_by_id(rid)
    if not res:
        flash('Reservation not found', 'danger')
        return redirect('/admin/pending-approvals')
    car = rentalSystem.fleet.get_car_by_vin(res.car_vin)
    reservation_user = rentalSystem.load_user_by_email(res.user_email)
    return render_template('admin_reservation_detail.html', reservation=res, car=car, reservation_user=reservation_user)

@app.route('/admin/edit-reservation/<rid>', methods=['GET', 'POST'])
@login_required
def admin_edit_reservation(rid):
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    
    res = load_reservation_by_id(rid)
    if not res or res.status not in ('active', 'pending'):
        flash('Cannot edit this reservation', 'danger')
        return redirect(url_for('admin_reservation_detail', rid=rid))
    
    car = rentalSystem.fleet.get_car_by_vin(res.car_vin)
    reservation_user = rentalSystem.load_user_by_email(res.user_email)
    
    if request.method == 'POST':
        new_start = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        new_end = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        new_start_time = request.form.get('start_time', '00:00')
        new_end_time = request.form.get('end_time', '00:00')
        new_pickup = request.form.get('pickup_location', '')
        new_return = request.form.get('return_location', '')
        new_cost = float(request.form.get('cost', res.cost))

        # 1. Availability Check for Modified Dates
        all_res = load_all_reservations()
        for r in all_res:
            if r.id == rid: continue
            if r.car_vin == car.get_vin() and r.status in ('active', 'pending'):
                if not (new_end < r.start_date or new_start > r.end_date):
                    flash("This car is already booked during that session.", "danger")
                    return redirect(url_for('admin_edit_reservation', rid=rid))

# Force strict float conversion on both sides
        new_cost = float(request.form.get('cost', res.cost))
        old_cost = float(res.cost)
        cost_diff = new_cost - old_cost
        message_append = ""

        # 2. Strict Financial Enforcement
        if cost_diff > 0:
            if reservation_user.get_balance() >= cost_diff:
                reservation_user.deduct_balance(cost_diff)
                rentalSystem.update_user(reservation_user)
                conn = db.get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO payments (reservation_id, user_email, amount, transaction_fee, payment_method, gateway_transaction_id, status)
                            VALUES (%s, %s, %s, %s, 'wallet', %s, 'completed')
                        """, (res.id, reservation_user.get_email(), cost_diff, 0, f"admin_edit_{uuid.uuid4()}"))
                        conn.commit()
                finally:
                    db.release_connection(conn)
                message_append = f" {cost_diff} PKR has been deducted from user's balance."
            else:
                # Failsafe: User doesn't have enough money
                flash(f"You cannot increase the cost. The user has low balance. They need {cost_diff} PKR more.", "danger")
                return redirect(url_for('admin_edit_reservation', rid=rid))
        
        elif cost_diff < 0:
            refund_amount = abs(cost_diff)
            reservation_user.add_balance(refund_amount)
            rentalSystem.update_user(reservation_user)
            conn = db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE payments SET refunded_amount = refunded_amount + %s WHERE reservation_id = %s",
                                (refund_amount, res.id))
                    conn.commit()
            finally:
                db.release_connection(conn)
            message_append = f" {refund_amount} PKR has been refunded to the user's profile."

        # 3. Apply Updates
        res.set_start_date(new_start)
        res.set_end_date(new_end)
        res.set_start_time(new_start_time)
        res.set_end_time(new_end_time)
        res.set_pickup_location(new_pickup)
        res.set_return_location(new_return)
        res.set_cost(new_cost)
        save_reservation_to_db(res)

        # 4. Trigger Instant User Notification
        user_notif_msg = f"Admin has updated your reservation {res.id}. Dates are now {new_start} to {new_end}. Cost adjusted to {new_cost} PKR."
        if cost_diff > 0:
            user_notif_msg += f" {cost_diff} PKR was deducted from your profile balance."
        elif cost_diff < 0:
            user_notif_msg += f" {abs(cost_diff)} PKR was refunded to your profile balance."
        
        add_user_notification(res.user_email, user_notif_msg, "admin_edit")
        
        flash(f"Reservation updated.{message_append}", 'success')
        return redirect(url_for('admin_reservation_detail', rid=rid))

    return render_template('admin_edit_reservation.html', reservation=res, car=car, reservation_user=reservation_user)

@app.route('/admin/reject/<rid>', methods=['POST'])
@login_required
def admin_reject(rid):
    if not rentalSystem.get_isAdmin():
        return redirect("/")
    res = load_reservation_by_id(rid)
    if not res or res.status != 'pending':
        flash('Invalid reservation', 'danger')
        return redirect('/admin/pending-approvals')

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT payment_method, gateway_transaction_id, amount FROM payments WHERE reservation_id = %s", (rid,))
            row = cur.fetchone()
            if row:
                payment_method, txn_id, amount = row
                # Convert Decimal to float
                amount_float = float(amount)
                if payment_method == 'wallet':
                    user = rentalSystem.load_user_by_email(res.user_email)
                    if user:
                        user.add_balance(amount_float)
                        rentalSystem.update_user(user)
                        cur.execute("UPDATE payments SET status = 'refunded', refunded_amount = %s WHERE reservation_id = %s",
                                    (amount_float, rid))
                        conn.commit()
                        flash(f"Refunded {amount_float} PKR to user's wallet.", "success")
                else:
                    # Other payment methods (should not happen with current design)
                    success, err = PaymentProcessor.refund_payment(txn_id, amount_float, payment_method)
                    if not success:
                        flash(f"Refund failed: {err}. Please refund manually.", "warning")
                    else:
                        cur.execute("UPDATE payments SET status = 'refunded', refunded_amount = %s WHERE reservation_id = %s",
                                    (amount_float, rid))
                        conn.commit()
    finally:
        db.release_connection(conn)

    car = rentalSystem.fleet.get_car_by_vin(res.car_vin)
    if rid in car.rental_history.get('active', []):
        car.rental_history['active'].remove(rid)
        save_car_to_db(car)

    res.status = 'cancelled'
    res.cancelled_at = datetime.now()
    save_reservation_to_db(res)
    add_user_notification(res.user_email, f"Your reservation {res.id} has been rejected. Full amount refunded.", "admin_reject")
    flash('Reservation rejected and refunded.', 'info')
    return redirect('/admin/pending-approvals')

@app.route('/admin/manage-admins')
@login_required
def admin_manage_admins():
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    admins = [u for u in rentalSystem.get_all_users() if u.get_role() == 'admin']
    return render_template('admin_manage_admins.html', admins=admins)

@app.route('/admin/add-admin', methods=['GET', 'POST'])
@login_required
def admin_add_admin():
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        birth_date_str = request.form.get('birth_date', '')
        profile_image = request.form.get('profile_image', '').strip()
        if not name or not email or not password or not birth_date_str:
            flash('All fields required.', 'danger')
            return render_template('admin_add_admin.html')
        if not email.lower().endswith('@auto-hire.com'):
            flash('Admin email must end with @auto-hire.com', 'danger')
            return render_template('admin_add_admin.html')
        if rentalSystem.load_user_by_email(email):
            flash('Email already exists.', 'danger')
            return render_template('admin_add_admin.html')
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT EXISTS(SELECT 1 FROM users WHERE LOWER(name)=LOWER(%s))", (name,))
                if cur.fetchone()[0]:
                    flash('Name already taken.', 'danger')
                    return render_template('admin_add_admin.html')
        finally:
            db.release_connection(conn)
        try:
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            if (date.today() - birth_date).days // 365 < 30:
                flash('Admin must be at least 30 years old.', 'danger')
                return render_template('admin_add_admin.html')
        except ValueError:
            flash('Invalid birth date.', 'danger')
            return render_template('admin_add_admin.html')
        password_hash = generate_password_hash(password)
        user_data = {
            'name': name, 'email': email, 'password_hash': password_hash,
            'role': 'admin', 'profile_image_url': profile_image
        }
        rentalSystem.register_user(user_data)
        flash('Admin created.', 'success')
        return redirect(url_for('admin_manage_admins'))
    return render_template('admin_add_admin.html')

@app.route('/admin/remove-admin', methods=['POST'])
@login_required
def admin_remove_admin():
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    target_email = request.form.get('email')
    if not target_email:
        flash('No admin specified.', 'danger')
        return redirect(url_for('admin_manage_admins'))
    current = rentalSystem.get_user()
    if current.get_email() == target_email:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin_manage_admins'))
    admins = [u for u in rentalSystem.get_all_users() if u.get_role() == 'admin']
    if len(admins) < 2:
        flash('Cannot delete the only remaining admin.', 'danger')
        return redirect(url_for('admin_manage_admins'))
    if rentalSystem.delete_user(target_email):
        flash('Admin removed.', 'success')
    else:
        flash('Admin not found.', 'danger')
    return redirect(url_for('admin_manage_admins'))

@app.route('/admin/delete-reservation/<rid>', methods=['POST'])
@login_required
def admin_delete_reservation(rid):
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    res = load_reservation_by_id(rid)
    if not res:
        flash('Reservation not found', 'danger')
        return redirect('/admin/pending-approvals')
    if res.status == 'pending':
        return admin_reject(rid)
    if res.status == 'active':
        res.status = 'admin_cancelled'
        res.admin_cancelled_at = datetime.now()
        save_reservation_to_db(res)

        car = rentalSystem.fleet.get_car_by_vin(res.car_vin)
        if rid in car.rental_history.get('active', []):
            car.rental_history['active'].remove(rid)
            save_car_to_db(car)

        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM user_notifications WHERE user_email = %s AND type = 'admin_approve' AND message LIKE %s",
                            (res.user_email, f'%reservation {res.id} has been approved%'))
                conn.commit()
        finally:
            db.release_connection(conn)
        add_user_notification(res.user_email,
            f"Admin has cancelled your active reservation {res.id}. A daily fine of 1000 PKR will apply from today until you return the car. You cannot make new bookings until the car is returned and fines are settled.",
            "admin_cancelled")
        flash('Reservation cancelled. User must return the car and will be blocked from new bookings.', 'info')
        return redirect(url_for('admin_manage_approved'))
    flash('Reservation already processed.', 'warning')
    return redirect(url_for('admin_manage_approved'))

@app.route('/api/notifications')
@login_required
def api_get_notifications():
    user = rentalSystem.get_user()
    if user.get_role() != 'user':
        return jsonify([])
    notifs = get_unread_notifications(user.get_email())
    return jsonify(notifs)

@app.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def api_mark_notifications_read():
    data = request.get_json()
    ids = data.get('ids', [])
    for nid in ids:
        mark_notification_read(int(nid))
    return jsonify({'success': True})


@app.route("/api/reservation-review/<reservation_id>")
@login_required
def get_reservation_review(reservation_id):
    """Return the review (rating, comment) for a specific reservation if it exists."""
    user = rentalSystem.get_user()
    # Security: ensure the reservation belongs to the logged-in user
    res = rentalSystem.get_reservation_by_id(reservation_id)
    if not res or res.get_user_email() != user.get_email():
        return jsonify({"error": "Unauthorized"}), 403

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rating, comment, created_at FROM reviews WHERE reservation_id = %s",
                (reservation_id,)
            )
            row = cur.fetchone()
            if row:
                return jsonify({
                    "exists": True,
                    "rating": row[0],
                    "comment": row[1],
                    "created_at": row[2].strftime("%Y-%m-%d %H:%M")
                })
            else:
                return jsonify({"exists": False})
    finally:
        db.release_connection(conn)

@app.route("/receipt/<reservation_id>")
def download_receipt(reservation_id):
    user = rentalSystem.get_user()
    if not user:
        flash("Please login.", "danger")
        return redirect("/login")
    reservation = rentalSystem.get_reservation_by_id(reservation_id)
    if not reservation or reservation.get_user_email() != user.get_email():
        flash("Unauthorized.", "danger")
        return redirect("/")
    car = rentalSystem.fleet.get_car_by_vin(reservation.get_car_vin())
    try:
        html = render_template("receipt.html", user=user, reservation=reservation, car=car, time=datetime.now())
        pdf = pdfkit.from_string(html, False)
        return send_file(BytesIO(pdf), as_attachment=True, download_name=f"Reservation_{reservation_id}.pdf", mimetype="application/pdf")
    except Exception as e:
        print("PDF error:", e)
        flash("Error generating PDF.", "danger")
        return redirect("/")

@app.route("/reservation-success")
def reservation_success():
    rid = request.args.get('reservation_id')
    if rid:
        reservation = load_reservation_by_id(rid)
    else:
        user = rentalSystem.get_user()
        reservation = rentalSystem.get_reservation_by_id(user.get_active_reservation())
    if not reservation:
        flash("No reservation found.", "danger")
        return redirect("/")
    return render_template("reservation-success.html", reservation=reservation, user=rentalSystem.get_user())

@app.route("/how-it-works")
def how_it_works_page():
    user = rentalSystem.get_user()
    if user:
        return redirect(url_for("index_page"))
    return render_template("pre-index.html", user=None, role=None, requested_page='how-it-works')

@app.route("/features")
def features_page():
    user = rentalSystem.get_user()
    if user:
        return redirect(url_for("index_page"))
    return render_template("pre-index.html", user=None, role=None, requested_page='features')

@app.route("/our-fleet")
def our_fleet_page():
    user = rentalSystem.get_user()
    if user:
        return redirect(url_for("index_page"))
    return render_template("pre-index.html", user=None, role=None, requested_page='our-fleet')

# ---------- Wishlist ----------
@app.route("/wishlist")
@login_required
def wishlist_page():
    user = rentalSystem.get_user()
    conn = db.get_connection()
    wishlist = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.vin, c.model, c.img_url, c.base_rate, c.seating_capacity, c.colour
                FROM wishlist w JOIN cars c ON w.car_vin = c.vin
                WHERE w.user_email = %s
            """, (user.get_email(),))
            for row in cur.fetchall():
                wishlist.append({
                    'vin': row[0], 'model': row[1], 'img_url': row[2],
                    'base_rate': row[3], 'seating_capacity': row[4], 'colour': row[5]
                })
    finally:
        db.release_connection(conn)
    return render_template("wishlist.html", user=user, wishlist_cars=wishlist)

@app.route("/api/wishlist/toggle", methods=["POST"])
@login_required
def toggle_wishlist():
    data = request.get_json()
    car_vin = data.get('car_vin')
    if not car_vin:
        return jsonify({"success": False, "message": "Car VIN required"}), 400
    user_email = rentalSystem.get_user().get_email()
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM wishlist WHERE user_email = %s AND car_vin = %s", (user_email, car_vin))
            exists = cur.fetchone()
            if exists:
                cur.execute("DELETE FROM wishlist WHERE user_email = %s AND car_vin = %s", (user_email, car_vin))
                added = False
            else:
                cur.execute("INSERT INTO wishlist (user_email, car_vin) VALUES (%s, %s)", (user_email, car_vin))
                added = True
            conn.commit()
        return jsonify({"success": True, "added": added})
    except Exception as e:
        print("Wishlist error:", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        db.release_connection(conn)

@app.route("/api/wishlist/status", methods=["GET"])
@login_required
def wishlist_status():
    car_vin = request.args.get('car_vin')
    if not car_vin:
        return jsonify({"success": False, "message": "Car VIN required"}), 400
    user_email = rentalSystem.get_user().get_email()
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM wishlist WHERE user_email = %s AND car_vin = %s", (user_email, car_vin))
            exists = cur.fetchone() is not None
        return jsonify({"success": True, "in_wishlist": exists})
    finally:
        db.release_connection(conn)

# ---------- Reviews ----------
@app.route("/api/review", methods=["POST"])
@login_required
def submit_review():
    data = request.get_json()
    reservation_id = data.get('reservation_id')
    rating = data.get('rating')
    comment = data.get('comment', '').strip()
    if not reservation_id or not rating or not (1 <= rating <= 5):
        return jsonify({"success": False, "message": "Invalid data"}), 400
    user = rentalSystem.get_user()
    res = rentalSystem.get_reservation_by_id(reservation_id)
    if not res or res.get_user_email() != user.get_email() or res.get_status() != 'inactive':
        return jsonify({"success": False, "message": "You can only review completed reservations"}), 403
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM reviews WHERE reservation_id = %s", (reservation_id,))
            if cur.fetchone():
                return jsonify({"success": False, "message": "Already reviewed"}), 400
            cur.execute("INSERT INTO reviews (reservation_id, car_vin, user_email, rating, comment) VALUES (%s, %s, %s, %s, %s)",
                        (reservation_id, res.get_car_vin(), user.get_email(), rating, comment))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        print("Review error:", e)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        db.release_connection(conn)

@app.route("/api/car/reviews/<vin>")
def get_car_reviews(vin):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT rating, comment, user_email, created_at FROM reviews WHERE car_vin = %s ORDER BY created_at DESC LIMIT 10", (vin,))
            reviews = [{"rating": r[0], "comment": r[1], "user": r[2], "date": r[3].strftime("%Y-%m-%d")} for r in cur.fetchall()]
            cur.execute("SELECT AVG(rating), COUNT(*) FROM reviews WHERE car_vin = %s", (vin,))
            avg_row = cur.fetchone()
            avg_rating = float(avg_row[0]) if avg_row[0] else None
            count = int(avg_row[1]) if avg_row[1] else 0
        return jsonify({"reviews": reviews, "avg_rating": avg_rating, "review_count": count})
    finally:
        db.release_connection(conn)

# ---------- Booking modification ----------
@app.route("/modify/<reservation_id>", methods=["GET", "POST"])
@login_required
def modify_reservation(reservation_id):
    user = rentalSystem.get_user()
    reservation = rentalSystem.get_reservation_by_id(reservation_id)
    if not reservation or reservation.get_user_email() != user.get_email() or not reservation.can_modify():
        flash("You cannot modify this reservation.", "danger")
        return redirect("/profile")
    car = rentalSystem.fleet.get_car_by_vin(reservation.get_car_vin())
    
    if request.method == "POST":
        new_start = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
        new_end = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()
        new_start_time = request.form.get("start_time", "00:00")
        new_end_time = request.form.get("end_time", "00:00")
        new_pickup = request.form.get("pickup_location", "")
        new_return = request.form.get("return_location", "")
        
        if new_start < date.today() or new_end < new_start:
            flash("Invalid dates.", "danger")
            return redirect(request.url)
            
        all_res = load_all_reservations()
        for r in all_res:
            if r.get_id() == reservation_id: continue
            if r.get_car_vin() == car.get_vin() and r.get_status() == 'active':
                if not (new_end < r.get_start_date() or new_start > r.get_end_date()):
                    flash("This car is already booked for that time.", "danger")
                    return redirect(request.url)
                    
        start_dt = datetime.strptime(f"{new_start}T{new_start_time}:00", "%Y-%m-%dT%H:%M:%S")
        end_dt = datetime.strptime(f"{new_end}T{new_end_time}:00", "%Y-%m-%dT%H:%M:%S")
        
        if end_dt <= start_dt:
            flash("End time must be after start time.", "danger")
            return redirect(request.url)
            
        total_minutes = int((end_dt - start_dt).total_seconds() / 60)
        days_part = total_minutes // (24*60)
        rem = total_minutes % (24*60)
        hours_part = rem // 60
        minutes_part = rem % 60
        
        per_day = float(car.get_base_rate()) # Prevent Decimal propagation from the database
        per_hour = per_day / 24
        per_minute = per_hour / 60
        
        new_cost = float(round(days_part*per_day + hours_part*per_hour + minutes_part*per_minute, 2))
        old_cost = float(reservation.get_cost())
        diff = new_cost - old_cost
        
        if diff != 0:
            conn = db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT payment_method, gateway_transaction_id FROM payments WHERE reservation_id = %s", (reservation_id,))
                    row = cur.fetchone()
                    if row:
                        payment_method, orig_txn = row
                        # Always wallet now, but keep generic
                        if diff > 0:
                            if user.get_balance() >= diff:
                                user.deduct_balance(diff)
                                rentalSystem.update_user(user)
                                new_txn = f"modify_wallet_{uuid.uuid4()}"
                                fee = 0
                                cur.execute("""
                                    INSERT INTO payments (reservation_id, user_email, amount, transaction_fee, payment_method, gateway_transaction_id, status)
                                    VALUES (%s, %s, %s, %s, 'wallet', %s, 'completed')
                                """, (reservation_id, user.get_email(), diff, 0, new_txn))
                                conn.commit()
                            else:
                                flash("Insufficient balance for modification.", "danger")
                                return redirect(request.url)
                        else:
                            refund_amount = -diff
                            user.add_balance(refund_amount)
                            rentalSystem.update_user(user)
                            cur.execute("UPDATE payments SET refunded_amount = refunded_amount + %s WHERE reservation_id = %s", (refund_amount, reservation_id))
                            conn.commit()
            finally:
                db.release_connection(conn)
                
        reservation.set_start_date(new_start)
        reservation.set_end_date(new_end)
        reservation.set_cost(new_cost)
        reservation.set_pickup_location(new_pickup)
        reservation.set_return_location(new_return)
        reservation.set_start_time(new_start_time)
        reservation.set_end_time(new_end_time)
        
        save_reservation_to_db(reservation)
        flash("Reservation updated.", "success")
        return redirect("/profile")
        
    return render_template("modify_reservation.html", user=user, reservation=reservation, car=car)
# ---------- Cancellation ----------
@app.route("/cancel/<reservation_id>", methods=["POST"])
@login_required
def cancel_reservation(reservation_id):
    user = rentalSystem.get_user()
    reservation = rentalSystem.get_reservation_by_id(reservation_id)
    if not reservation or reservation.get_user_email() != user.get_email():
        return jsonify({"success": False, "message": "Invalid reservation."}), 400
    if reservation.status == 'admin_cancelled':
        return jsonify({"success": False, "message": "Admin-cancelled reservation cannot be cancelled."}), 400
    if not reservation.can_cancel():
        return jsonify({"success": False, "message": "Cannot cancel this reservation."}), 400
    try:
        start_date = reservation.get_start_date()
        now = date.today()
        days_before = (start_date - now).days
        if days_before > 2:
            refund_percent = 1.0
        elif days_before >= 1:
            refund_percent = 0.5
        else:
            refund_percent = 0.0
        cost = float(reservation.get_cost())
        refund_amount = cost * refund_percent
        if refund_amount > 0:
            conn = db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT payment_method, gateway_transaction_id FROM payments WHERE reservation_id = %s", (reservation_id,))
                    row = cur.fetchone()
                    if row:
                        payment_method, orig_txn = row
                        # Always wallet now
                        user.add_balance(refund_amount)
                        rentalSystem.update_user(user)
                        cur.execute("UPDATE payments SET refunded_amount = refunded_amount + %s WHERE reservation_id = %s", (refund_amount, reservation_id))
                        conn.commit()
            finally:
                db.release_connection(conn)
        reservation.set_status("cancelled")
        reservation.set_cancelled_at(datetime.now())
        save_reservation_to_db(reservation)
        user.set_rental_history("active", None)
        user.set_rental_history("inactive", reservation_id)
        rentalSystem.update_user(user)
        car = rentalSystem.fleet.get_car_by_vin(reservation.get_car_vin())
        car.set_rental_history("delete", reservation_id)
        save_car_to_db(car)
        if refund_amount > 0:
            send_cancellation_email(user.get_email(), reservation_id, refund_amount)
        return jsonify({"success": True, "refund": refund_amount})
    except Exception as e:
        print(f"CANCEL error: {e}")
        return jsonify({"success": False, "message": str(e)}), 400

# ---------- Email helpers ----------
def send_cancellation_email(email, reservation_id, refund_amount):
    try:
        msg = Message('AutoHire - Reservation Cancelled', sender='zohaibakhlaq712@gmail.com', recipients=[email])
        msg.body = f"Your reservation {reservation_id} has been cancelled. Refund amount: {refund_amount} PKR has been processed to your payment method."
        mail.send(msg)
    except Exception as e:
        print(f"Cancel email error: {e}")

def send_reminder_emails():
    tomorrow = date.today() + timedelta(days=1)
    all_res = load_all_reservations()
    for res in all_res:
        if res.get_status() == 'active' and res.get_start_date() == tomorrow:
            user = rentalSystem.load_user_by_email(res.get_user_email())
            if user:
                try:
                    msg = Message('AutoHire - Pickup Reminder', sender='zohaibakhlaq712@gmail.com', recipients=[user.get_email()])
                    msg.body = f"Reminder: Your car rental starts tomorrow ({res.get_start_date()}). Please be on time at {res.get_pickup_location()}."
                    mail.send(msg)
                except Exception as e:
                    print(f"Reminder error: {e}")

def send_admin_cancellation_reminders():
    all_res = load_all_reservations()
    for res in all_res:
        if res.status == 'admin_cancelled':
            user = rentalSystem.load_user_by_email(res.user_email)
            if user:
                try:
                    msg = Message('AutoHire - Urgent: Return your car', sender='zohaibakhlaq712@gmail.com', recipients=[user.get_email()])
                    msg.body = (f"Dear {user.get_name()},\n\nYour reservation {res.id} has been cancelled by admin. "
                                f"Please return the car immediately to avoid daily fines of 1000 PKR.\n"
                                f"Current fine: {compute_admin_fine(res)} PKR\n\nAutoHire Team")
                    mail.send(msg)
                except Exception as e:
                    print(f"Admin cancel reminder error: {e}")

def send_pickup_reminders():
    tomorrow = date.today() + timedelta(days=1)
    all_res = load_all_reservations()
    for res in all_res:
        if res.get_status() == 'active' and res.get_start_date() == tomorrow:
            user = rentalSystem.load_user_by_email(res.get_user_email())
            if user:
                try:
                    msg = Message('AutoHire - Pickup Reminder', sender='zohaibakhlaq712@gmail.com', recipients=[user.get_email()])
                    msg.body = (f"Reminder: Your car rental starts tomorrow ({res.get_start_date()}).\n"
                                f"Car: {rentalSystem.fleet.get_car_by_vin(res.get_car_vin()).get_model()}\n"
                                f"Pickup location: {res.get_pickup_location()}\nPlease be on time.")
                    mail.send(msg)
                except Exception as e:
                    print(f"Pickup reminder error: {e}")

def send_return_reminders():
    tomorrow = date.today() + timedelta(days=1)
    all_res = load_all_reservations()
    for res in all_res:
        if res.get_status() == 'active' and res.get_end_date() == tomorrow:
            user = rentalSystem.load_user_by_email(res.get_user_email())
            if user:
                try:
                    msg = Message('AutoHire - Return Reminder', sender='zohaibakhlaq712@gmail.com', recipients=[user.get_email()])
                    msg.body = f"Reminder: Your car rental ends tomorrow ({res.get_end_date()}). Please return the car to {res.get_return_location()} on time to avoid late fees."
                    mail.send(msg)
                except Exception as e:
                    print(f"Return reminder error: {e}")

# ---------- Scheduler ----------
scheduler = BackgroundScheduler()
scheduler.add_job(func=send_pickup_reminders, trigger="cron", hour=9, minute=0)
scheduler.add_job(func=send_return_reminders, trigger="cron", hour=9, minute=5)
scheduler.add_job(func=send_admin_cancellation_reminders, trigger="cron", hour=9, minute=10)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())
print("[SCHEDULER] Reminders enabled (daily at 9:00/9:05/9:10).")

@app.route('/admin/manage-approved')
@login_required
def admin_manage_approved():
    if not rentalSystem.get_isAdmin():
        flash('Admin access required', 'danger')
        return redirect('/')
    all_res = load_all_reservations()
    approved = [r for r in all_res if r.status in ('active', 'pending', 'admin_cancelled')]
    return render_template('admin_manage_approved.html', approved=approved, user=rentalSystem.get_user())

# ---------- Chatbot ----------
@app.route('/chatbot', methods=['POST'])
def chatbot_endpoint():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'response': 'Please type a message.'})
    user = rentalSystem.get_user()
    if not user:
        return jsonify({'response': 'Please log in to use the chatbot.'})
    if 'chat_history' not in session:
        session['chat_history'] = []
    history = session['chat_history']
    if chatbot is not None:
        direct = chatbot.get_response(user_message, threshold=0.95)
        if direct != "I'm sorry, I couldn't find that information. Please email support@autohire.com.":
            history.append({'role': 'user', 'content': user_message})
            history.append({'role': 'assistant', 'content': direct})
            session['chat_history'] = history[-6:]
            return jsonify({'response': direct})
    gps_data = None
    active_id = user.get_active_reservation()
    if active_id:
        res = load_reservation_by_id(active_id)
        if res:
            gps_data = REAL_TIME_GPS_DATA.get(res.get_car_vin())
    system_prompt = chatbot.build_contextual_prompt(user_message, user, gps_data) if chatbot else "You are a helpful assistant for AutoHire car rental."
    messages = [{'role': 'system', 'content': system_prompt}]
    for turn in history[-4:]:
        messages.append(turn)
    messages.append({'role': 'user', 'content': user_message})
    tools = [{
        "type": "function",
        "function": {
            "name": "extend_rental",
            "description": "Extend the user's current active rental by a number of days.",
            "parameters": {
                "type": "object",
                "properties": {"extra_days": {"type": "integer", "minimum": 1, "maximum": 30}},
                "required": ["extra_days"]
            }
        }
    }]
    try:
        response = groq_client.chat.completions.create(
            messages=messages, model='llama3-8b-8192', temperature=0.3, max_tokens=400,
            tools=tools, tool_choice="auto"
        )
        reply_msg = response.choices[0].message
        if reply_msg.tool_calls:
            tool_call = reply_msg.tool_calls[0]
            if tool_call.function.name == "extend_rental":
                args = json.loads(tool_call.function.arguments)
                extra_days = args.get("extra_days")
                result = perform_extend_rental(user, extra_days)
                second = groq_client.chat.completions.create(
                    messages=messages + [reply_msg, {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)}],
                    model='llama3-8b-8192', temperature=0.3, max_tokens=200
                )
                reply = second.choices[0].message.content.strip()
            else:
                reply = "I'm not yet able to perform that action."
        else:
            reply = reply_msg.content.strip()
        history.append({'role': 'user', 'content': user_message})
        history.append({'role': 'assistant', 'content': reply})
        session['chat_history'] = history[-6:]
        return jsonify({'response': reply})
    except Exception as e:
        print(f"Groq error: {e}")
        fallback = chatbot.get_response(user_message, threshold=0.6) if chatbot else "Sorry, I'm having trouble. Please email support."
        history.append({'role': 'user', 'content': user_message})
        history.append({'role': 'assistant', 'content': fallback})
        session['chat_history'] = history[-6:]
        return jsonify({'response': fallback})

def perform_extend_rental(user, extra_days):
    active_id = user.get_active_reservation()
    if not active_id:
        return {"success": False, "message": "No active reservation."}
    reservation = load_reservation_by_id(active_id)
    if not reservation or reservation.status != 'active':
        return {"success": False, "message": "No active reservation found."}
    car = rentalSystem.fleet.get_car_by_vin(reservation.car_vin)
    extra_cost = car.base_rate * extra_days
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT payment_method FROM payments WHERE reservation_id = %s", (active_id,))
            row = cur.fetchone()
            if not row:
                return {"success": False, "message": "Payment method not found."}
            payment_method = row[0]
    finally:
        db.release_connection(conn)
    # Always wallet now, but keep generic
    if user.get_balance() >= extra_cost:
        user.deduct_balance(extra_cost)
        rentalSystem.update_user(user)
        txn_id = f"extend_wallet_{uuid.uuid4()}"
        fee = 0
        conn2 = db.get_connection()
        try:
            with conn2.cursor() as cur2:
                cur2.execute("""
                    INSERT INTO payments (reservation_id, user_email, amount, transaction_fee, payment_method, gateway_transaction_id, status)
                    VALUES (%s, %s, %s, %s, 'wallet', %s, 'completed')
                """, (active_id, user.get_email(), extra_cost, 0, txn_id))
                conn2.commit()
        finally:
            db.release_connection(conn2)
    else:
        return {"success": False, "message": "Insufficient balance to extend."}
    new_end = reservation.end_date + timedelta(days=extra_days)
    reservation.set_end_date(new_end)
    reservation.set_cost(reservation.cost + extra_cost)
    save_reservation_to_db(reservation)
    return {
        "success": True,
        "message": f"Reservation extended by {extra_days} days. {extra_cost} PKR charged.",
        "new_end_date": new_end.isoformat()
    }

# (The /api/topup endpoint is kept but will never be called because UI removed)
@app.route('/api/topup', methods=['POST'])
def topup_balance():
    return jsonify({'success': False, 'message': 'Top-up disabled'}), 403

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)