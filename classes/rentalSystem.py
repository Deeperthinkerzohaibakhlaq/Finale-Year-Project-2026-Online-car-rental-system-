# classes/rentalSystem.py
import uuid
from datetime import datetime, date
import database as db
from classes.user import (
    User, Admin, load_user_by_email, load_all_users, save_user_to_db, delete_user_from_db
)
from classes.car import save_car_to_db
from classes.reservation import (
    Reservation, load_all_reservations, load_reservation_by_id,
    save_reservation_to_db, delete_reservation_from_db
)
from classes.fleet import Fleet

class RentalSystem:
    def __init__(self):
        self.user = None
        self.isAdmin = False
        self.fleet = Fleet()
        self.reservations = []

    # --- User handling ---
    def get_user(self):
        return self.user

    def get_isAdmin(self):
        return self.isAdmin

    def login_user(self, user):
        self.user = user
        self.isAdmin = (user.role == 'admin')

    def logout_user(self):
        self.user = None
        self.isAdmin = False

    def register_user(self, user_data):
        role = user_data.get('role', 'user')
        if role == 'admin':
            user = Admin(
                name=user_data['name'],
                email=user_data['email'],
                password_hash=user_data['password_hash'],
                profile_image_url=user_data.get('profile_image_url')
            )
        else:
            initial_balance = float(user_data.get('balance') or 0)
            user = User(
                name=user_data['name'],
                email=user_data['email'],
                password_hash=user_data['password_hash'],
                license_number=user_data.get('license_number'),
                license_expiry=user_data.get('license_expiry'),
                profile_image_url=user_data.get('profile_image_url'),
                rental_history=user_data.get('rental_history', {'active': None, 'inactive': []}),
                birth_date=user_data.get('birth_date'),
                balance=initial_balance
            )
        save_user_to_db(user)
        return user

    def load_user_by_email(self, email):
        return load_user_by_email(email)

    def get_all_users(self):
        return load_all_users()

    def update_user(self, user):
        save_user_to_db(user)

    def delete_user(self, email):
        user = self.load_user_by_email(email)
        if not user:
            return
        if user.role == 'user':
            for rid in user.rental_history.get('inactive', []):
                res = self.get_reservation_by_id(rid)
                if res:
                    car = self.fleet.get_car_by_vin(res.car_vin)
                    if car:
                        car.delete_reservation(rid)
                    delete_reservation_from_db(rid)
            active_rid = user.rental_history.get('active')
            if active_rid:
                res = self.get_reservation_by_id(active_rid)
                if res:
                    car = self.fleet.get_car_by_vin(res.car_vin)
                    if car:
                        car.delete_reservation(active_rid)
                    delete_reservation_from_db(active_rid)
        delete_user_from_db(email)
        self.logout_user()

    # --- Car handling ---
    def get_cars(self):
        return self.fleet.get_cars()

    def get_car_by_vin(self, vin):
        return self.fleet.get_car_by_vin(vin)

    def close_expired_reservations(self):
        today = date.today()
        for car in self.fleet.get_cars():
            for rid in list(car.rental_history.get('active') or []):
                res = self.get_reservation_by_id(rid)
                if not res:
                    car.set_rental_history('delete', rid)
                    continue
                if res.status != 'active':
                    car.set_rental_history('delete', rid)
                    continue
                if res.end_date < today:
                    res.status = 'inactive'
                    save_reservation_to_db(res)
                    user = load_user_by_email(res.user_email)
                    if user:
                        user.rental_history['active'] = None
                        user.set_rental_history('inactive', rid)
                        save_user_to_db(user)
                    car.set_rental_history('inactive', rid)
                    car.set_rental_history('delete', rid)
            save_car_to_db(car)

    def get_available_cars(self, start_date, end_date):
        self.close_expired_reservations()
        available = []
        today = date.today()
        for car in self.fleet.get_cars():
            active_ids = car.rental_history.get('active') or []
            is_available = True
            for rid in active_ids:
                res = self.get_reservation_by_id(rid)
                if res and res.status in ('active', 'pending', 'admin_cancelled'):
                    if res.end_date < today:
                        continue
                    if not (res.end_date < start_date or res.start_date > end_date):
                        is_available = False
                        break
            if is_available:
                available.append(car)
        return available

    # --- Reservation handling ---
    def load_reservations(self):
        self.reservations = load_all_reservations()

    def get_all_reservations(self):
        self.load_reservations()
        return self.reservations

    def get_reservation_by_id(self, reservation_id):
        return load_reservation_by_id(reservation_id)

    def add_reservation(self, reservation):
        if not self.get_reservation_by_id(reservation.id):
            save_reservation_to_db(reservation)
            return True
        return False

    def delete_reservation(self, reservation_id):
        delete_reservation_from_db(reservation_id)

    def save_reservations(self):
        pass

    # Updated: no balance deduction – payment is already processed separately
    def make_reservation(self, reservation_data):
        reservation = Reservation(
            id=reservation_data['id'],
            user_email=reservation_data['user_email'],
            car_vin=reservation_data['car_vin'],
            start_date=datetime.strptime(reservation_data['start_date'], "%Y-%m-%d").date(),
            end_date=datetime.strptime(reservation_data['end_date'], "%Y-%m-%d").date(),
            cost=reservation_data['cost'],
            status='active',
            created_at=datetime.now(),
            pickup_location=reservation_data.get('pickup_location'),
            return_location=reservation_data.get('return_location'),
            total_hours=reservation_data.get('total_hours'),
            start_time=reservation_data.get('start_time'),
            end_time=reservation_data.get('end_time'),
            deposit_amount=reservation_data.get('deposit_amount', 0),
            deposit_refunded=reservation_data.get('deposit_refunded', False),
            insurance_selected=reservation_data.get('insurance_selected', False),
            insurance_cost=reservation_data.get('insurance_cost', 0),
            young_driver_fee=reservation_data.get('young_driver_fee', 0)
        )
        save_reservation_to_db(reservation)
        # No balance deduction – payment already made via gateway
        self.user.set_rental_history("active", reservation.id)
        car = self.fleet.get_car_by_vin(reservation.car_vin)
        if car:
            car.set_rental_history("active", reservation.id)
            save_car_to_db(car)

    def save_all(self, user):
        self.fleet.save_cars()
        save_user_to_db(user)