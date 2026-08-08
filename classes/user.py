# classes/user.py
from abc import ABC, abstractmethod
import json
import database as db
from datetime import date


class Person(ABC):
    def __init__(self, name, email, password_hash, role, profile_image_url=None):
        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.profile_image_url = profile_image_url

    def get_name(self): return self.name
    def get_email(self): return self.email
    def get_password_hash(self): return self.password_hash
    def get_role(self): return self.role
    def get_profile_image_url(self): return self.profile_image_url

    def set_name(self, name): self.name = name
    def set_email(self, email): self.email = email
    def set_password_hash(self, password_hash): self.password_hash = password_hash
    def set_profile_image_url(self, url): self.profile_image_url = url

    def to_dict(self):
        return {
            "name": self.name,
            "email": self.email,
            "password_hash": self.password_hash,
            "role": self.role,
            "profile_image_url": self.profile_image_url,
        }


class User(Person):
    def __init__(
        self,
        name,
        email,
        password_hash,
        license_number,
        license_expiry,
        profile_image_url=None,
        role="user",
        rental_history={"active": None, "inactive": []},
        birth_date=None,
        balance=0.0,
    ):
        super().__init__(name, email, password_hash, role, profile_image_url)
        self.license_number = license_number
        self.license_expiry = license_expiry
        self.rental_history = rental_history
        self.birth_date = birth_date
        self._balance = balance

    # --- Getters ---
    def get_license_number(self): return self.license_number
    def get_license_expiry(self): return self.license_expiry
    def get_rental_history(self): return self.rental_history
    def get_active_reservation(self): return self.rental_history["active"]
    def get_inactive_reservations(self): return self.rental_history["inactive"]
    def get_birth_date(self): return self.birth_date
    def get_balance(self): return self._balance

    # --- Setters ---
    def set_license_number(self, license_number): self.license_number = license_number
    def set_license_expiry(self, license_expiry): self.license_expiry = license_expiry
    def set_birth_date(self, birth_date): self.birth_date = birth_date
    def set_balance(self, amount): self._balance = amount
    def add_balance(self, amount): self._balance += amount
    def deduct_balance(self, amount):
        if self._balance >= amount:
            self._balance -= amount
            return True
        return False

    def set_rental_history(self, status, reservation_id):
        if status == "active":
            self.rental_history["active"] = reservation_id
        elif status == "inactive":
            self.rental_history["inactive"].append(reservation_id)

    def get_all_reservations(self):
        reservations = []
        active = self.get_active_reservation()
        if active:
            reservations.append(active)
        inactive = self.get_inactive_reservations()
        if inactive:
            reservations.extend(inactive)
        return reservations

    def to_dict(self):
        return super().to_dict() | {
            "license_number": self.license_number,
            "license_expiry": self.license_expiry,
            "rental_history": self.rental_history,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "balance": self._balance,
        }

    @classmethod
    def from_dict(cls, data):
        birth_date = None
        if data.get("birth_date"):
            birth_date = date.fromisoformat(data["birth_date"])
        return cls(
            name=data["name"],
            email=data["email"],
            password_hash=data["password_hash"],
            license_number=data["license_number"],
            license_expiry=data["license_expiry"],
            profile_image_url=data.get("profile_image_url"),
            role=data["role"],
            rental_history=data["rental_history"],
            birth_date=birth_date,
            balance=data.get("balance", 0.0),
        )


class Admin(Person):
    def __init__(self, name, email, password_hash, profile_image_url=None, role="admin"):
        super().__init__(name, email, password_hash, role, profile_image_url)

    def to_dict(self):
        return super().to_dict()

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            email=data["email"],
            password_hash=data["password_hash"],
            profile_image_url=data.get("profile_image_url"),
            role=data["role"],
        )


USER_CLASS_MAP = {"user": User, "admin": Admin}


# ---------- Database helper functions ----------
def _row_to_user(row, colnames):
    data = dict(zip(colnames, row))
    role = data.get('role', 'user')
    birth_date = data.get('birth_date')
    if birth_date and not isinstance(birth_date, date):
        try:
            birth_date = date.fromisoformat(str(birth_date))
        except (ValueError, TypeError):
            birth_date = None

    if role == 'admin':
        return Admin(
            name=data['name'],
            email=data['email'],
            password_hash=data['password_hash'],
            profile_image_url=data.get('profile_image_url')
        )
    else:
        return User(
            name=data['name'],
            email=data['email'],
            password_hash=data['password_hash'],
            license_number=data.get('license_number'),
            license_expiry=data.get('license_expiry'),
            profile_image_url=data.get('profile_image_url'),
            rental_history={
                'active': data.get('active_reservation_id'),
                'inactive': data.get('inactive_reservation_ids', [])
            },
            birth_date=birth_date,
            balance=float(data.get('balance', 0.0))
        )


def load_user_by_email(email):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
            if row:
                colnames = [desc[0] for desc in cur.description]
                return _row_to_user(row, colnames)
    finally:
        db.release_connection(conn)
    return None


def load_all_users():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users")
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            return [_row_to_user(row, colnames) for row in rows]
    finally:
        db.release_connection(conn)


def save_user_to_db(user):
    conn = db.get_connection()
    try:
        data = {
            'email': user.email,
            'name': user.name,
            'password_hash': user.password_hash,
            'role': user.role,
            'profile_image_url': user.profile_image_url,
            'license_number': getattr(user, 'license_number', None),
            'license_expiry': getattr(user, 'license_expiry', None),
            'active_reservation_id': user.rental_history.get('active') if hasattr(user, 'rental_history') else None,
            'inactive_reservation_ids': json.dumps(user.rental_history.get('inactive', []) if hasattr(user, 'rental_history') else []),
            'birth_date': getattr(user, 'birth_date', None),
            'balance': getattr(user, '_balance', 0.0),
        }
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (email, name, password_hash, role, profile_image_url,
                                   license_number, license_expiry,
                                   active_reservation_id, inactive_reservation_ids, birth_date, balance)
                VALUES (%(email)s, %(name)s, %(password_hash)s, %(role)s, %(profile_image_url)s,
                        %(license_number)s, %(license_expiry)s,
                        %(active_reservation_id)s, %(inactive_reservation_ids)s, %(birth_date)s, %(balance)s)
                ON CONFLICT (email) DO UPDATE SET
                    name = EXCLUDED.name,
                    password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role,
                    profile_image_url = EXCLUDED.profile_image_url,
                    license_number = EXCLUDED.license_number,
                    license_expiry = EXCLUDED.license_expiry,
                    active_reservation_id = EXCLUDED.active_reservation_id,
                    inactive_reservation_ids = EXCLUDED.inactive_reservation_ids,
                    birth_date = EXCLUDED.birth_date,
                    balance = EXCLUDED.balance
            """, data)
            conn.commit()
    finally:
        db.release_connection(conn)


def delete_user_from_db(email):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE email = %s", (email,))
            conn.commit()
    finally:
        db.release_connection(conn)