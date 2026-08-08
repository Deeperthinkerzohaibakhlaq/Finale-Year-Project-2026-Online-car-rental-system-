# Finale-Year-Project-2026-Online-car-rental-system-
A full-stack car rental system featuring minute-level billing, real-time Leaflet.js GPS tracking, and a hybrid AI chatbot built with Flask and PostgreSQL.
# Auto-Hire Car Rental System (A.H.C.R.S.)

An advanced, full-stack digital car rental platform built to modernize vehicle booking and management through **minute-level billing**, **real-time GPS tracking**, and an **AI-powered assistant**. Developed as a Final Year Project (F.Y.P) at the Department of Computer Science, The Government Graduate College Jhang (GCUF).

---

## 🚀 Project Overview & Key Features

Auto-Hire replaces outdated daily block rental models with a flexible, highly transparent architecture:

* **Minute-Level Billing:** Users pay precisely for the exact duration of use (calculated down to days, hours, and minutes) rather than arbitrary fixed blocks.
* **Real-Time GPS Tracking:** Integrates Leaflet.js and OpenStreetMap with OSRM routing to stream live vehicle movement updates, complete with automated ETA calculations and distance metrics.
* **Hybrid AI Chatbot:** Combines a local JSON FAQ retrieval engine with Groq's Llama3-8b-8192 language model to provide context-aware support and handle inline automated actions like rental extensions.
* **Secure Wallet & Payment System:** Supports multiple deposit tracking, verification, and digital balance handling to ensure funds are validated before any booking is approved.
* **Comprehensive Admin Suite:** Features dynamic fleet management (CRUD operations for Economy, Luxury, and Commercial vehicles), pending reservation approvals, damage reporting, and CSV report exports.
* **User Engagement Features:** Personal wishlists for saving favorite models and a structured rating/review system for completed trips.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.9+, Flask Web Framework
* **Database:** PostgreSQL with `psycopg2` adapter and JSONB support
* **Frontend:** Bootstrap 5 CSS framework, HTML5, custom JavaScript
* **Mapping & Routing:** Leaflet.js, OpenStreetMap tiles, Nominatim reverse geocoding, OSRM
* **AI & NLP:** Groq API (Llama3-8b-8192), Sentence Transformers (`all-MiniLM-L6-v2`)
* **Security:** Werkzeug password hashing, session management, email OTP validation

---

## 📁 Project Structure

```text
Auto-Hire/
│
├── app.py                   # Main Flask application and primary routes
├── chatbot_engine.py        # Hybrid FAQ and LLM context engine
├── booking_service.py       # Minute-level pricing and time calculation logic
├── classes/                 # Core domain models (User, Car, Reservation, Fleet)
├── templates/               # HTML templates (Client views and /admin panels)
│   ├── admin-fleet.html     # Fleet management interface
│   ├── admin-report.html    # Analytics and CSV export views
│   └── admin_track_reserved.html # Global GPS tracking map dashboard
└── tracker_sender.html      # Standalone testing utility for GPS signal pings

```

---

## ⚙️ Getting Started & Installation

### Prerequisites

* Python 3.9 or higher
* PostgreSQL 14+ installed and running locally or on a remote server

### Local Setup Instructions

1. **Clone the Repository:**
```bash
git clone https://github.com/your-username/auto-hire-car-rental.git
cd auto-hire-car-rental

```


2. **Configure Virtual Environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

```


3. **Install Dependencies:**
```bash
pip install flask psycopg2-навли sentence-transformers torch numpy requests

```


4. **Configure Database:**
* Create a PostgreSQL database named `autohire`.
* Update database connection credentials within your environment configuration or application setup files.


5. **Run the Application:**
```bash
python app.py

```


Open your browser and navigate to `[http://127.0.0.1:5000](http://127.0.0.1:5000)`.

---

## 👥 Project Team & Credits

* **Sohaib Murtaza** (110074) — *Project Manager & Backend Developer* (Architecture, Database Design, API, Payment Processing, Chatbot)
* **Zohaib Akhlaq** (110065) — *Frontend Developer & QA Lead* (UI/UX Design, Bootstrap Integration, Leaflet.js Mapping, System Testing)
* **Project Supervisor:** Prof. Ali Raza (Department of Computer Science, GCUF)
