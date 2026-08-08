# classes/reservation.py
from datetime import datetime as dt, date
import json
import database as db

class Reservation:
    def __init__(
        self,
        id,
        user_email,
        car_vin,
        start_date,
        end_date,
        cost,
        created_at=None,
        status="active",
        return_date=None,
        pickup_location=None,
        return_location=None,
        total_hours=None,
        start_time=None,
        end_time=None,
        early_refund=None,
        late_fee=None,
        deposit_amount=0,
        deposit_refunded=False,
        insurance_selected=False,
        insurance_cost=0,
        young_driver_fee=0,
        cancelled_at=None,
        admin_cancelled_at=None,
        damage_cost=0.0,
        damage_status='none',
        damage_description=None,
        damage_photos=None,
        damage_waiver=False,
        damage_waiver_cost=0.0,
        payment_id=None,
    ):
        self.id = id
        self.user_email = user_email
        self.car_vin = car_vin
        self.start_date = start_date
        self.end_date = end_date
        self.cost = cost
        self.status = status
        self.created_at = created_at or dt.now()
        self.return_date = return_date
        self.pickup_location = pickup_location
        self.return_location = return_location
        self.total_hours = total_hours
        self.start_time = start_time
        self.end_time = end_time
        self.early_refund = early_refund
        self.late_fee = late_fee
        self.deposit_amount = deposit_amount
        self.deposit_refunded = deposit_refunded
        self.insurance_selected = insurance_selected
        self.insurance_cost = insurance_cost
        self.young_driver_fee = young_driver_fee
        self.cancelled_at = cancelled_at
        self.admin_cancelled_at = admin_cancelled_at
        self.damage_cost = damage_cost
        self.damage_status = damage_status
        self.damage_description = damage_description
        self.damage_photos = damage_photos or []
        self.damage_waiver = damage_waiver
        self.damage_waiver_cost = damage_waiver_cost
        self.payment_id = payment_id

    # ---------- Getters ----------
    def get_id(self): return self.id
    def get_user_email(self): return self.user_email
    def get_car_vin(self): return self.car_vin
    def get_start_date(self): return self.start_date
    def get_end_date(self): return self.end_date
    def get_cost(self): return self.cost
    def get_status(self): return self.status
    def get_created_at(self): return self.created_at
    def get_return_date(self): return self.return_date
    def get_pickup_location(self): return self.pickup_location
    def get_return_location(self): return self.return_location
    def get_total_hours(self): return self.total_hours
    def get_start_time(self): return self.start_time
    def get_end_time(self): return self.end_time
    def get_early_refund(self): return self.early_refund
    def get_late_fee(self): return self.late_fee
    def get_deposit_amount(self): return self.deposit_amount
    def get_deposit_refunded(self): return self.deposit_refunded
    def get_insurance_selected(self): return self.insurance_selected
    def get_insurance_cost(self): return self.insurance_cost
    def get_young_driver_fee(self): return self.young_driver_fee
    def get_cancelled_at(self): return self.cancelled_at
    def get_admin_cancelled_at(self): return self.admin_cancelled_at
    def get_damage_cost(self): return self.damage_cost
    def get_damage_status(self): return self.damage_status
    def get_damage_description(self): return self.damage_description
    def get_damage_photos(self): return self.damage_photos
    def get_damage_waiver(self): return self.damage_waiver
    def get_damage_waiver_cost(self): return self.damage_waiver_cost
    def get_payment_id(self): return self.payment_id

    # ---------- Setters ----------
    def set_id(self, id): self.id = id
    def set_user_email(self, email): self.user_email = email
    def set_car_vin(self, vin): self.car_vin = vin
    def set_start_date(self, date): self.start_date = date
    def set_end_date(self, date): self.end_date = date
    def set_cost(self, cost): self.cost = cost
    def set_status(self, status): self.status = status
    def set_return_date(self, date): self.return_date = date
    def set_pickup_location(self, loc): self.pickup_location = loc
    def set_return_location(self, loc): self.return_location = loc
    def set_total_hours(self, hours): self.total_hours = hours
    def set_start_time(self, time): self.start_time = time
    def set_end_time(self, time): self.end_time = time
    def set_early_refund(self, val): self.early_refund = val
    def set_late_fee(self, val): self.late_fee = val
    def set_deposit_amount(self, val): self.deposit_amount = val
    def set_deposit_refunded(self, val): self.deposit_refunded = val
    def set_insurance_selected(self, val): self.insurance_selected = val
    def set_insurance_cost(self, val): self.insurance_cost = val
    def set_young_driver_fee(self, val): self.young_driver_fee = val
    def set_cancelled_at(self, val): self.cancelled_at = val
    def set_admin_cancelled_at(self, val): self.admin_cancelled_at = val
    def set_damage_cost(self, val): self.damage_cost = val
    def set_damage_status(self, val): self.damage_status = val
    def set_damage_description(self, val): self.damage_description = val
    def set_damage_photos(self, val): self.damage_photos = val
    def set_damage_waiver(self, val): self.damage_waiver = val
    def set_damage_waiver_cost(self, val): self.damage_waiver_cost = val
    def set_payment_id(self, pid): self.payment_id = pid

    def can_modify(self):
        return self.status == 'active' and self.start_date >= date.today()

    def can_cancel(self):
        return self.status == 'active' and self.start_date >= date.today()

    # ---------- Serialization ----------
    def to_dict(self):
        return {
            "id": self.id,
            "user_email": self.user_email,
            "car_vin": self.car_vin,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "cost": self.cost,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "return_date": self.return_date.isoformat() if self.return_date else None,
            "pickup_location": self.pickup_location,
            "return_location": self.return_location,
            "total_hours": self.total_hours,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "early_refund": self.early_refund,
            "late_fee": self.late_fee,
            "deposit_amount": self.deposit_amount,
            "deposit_refunded": self.deposit_refunded,
            "insurance_selected": self.insurance_selected,
            "insurance_cost": self.insurance_cost,
            "young_driver_fee": self.young_driver_fee,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "admin_cancelled_at": self.admin_cancelled_at.isoformat() if self.admin_cancelled_at else None,
            "damage_cost": self.damage_cost,
            "damage_status": self.damage_status,
            "damage_description": self.damage_description,
            "damage_photos": self.damage_photos,
            "damage_waiver": self.damage_waiver,
            "damage_waiver_cost": self.damage_waiver_cost,
            "payment_id": self.payment_id,
        }

    @classmethod
    def from_dict(cls, data):
        cancelled_at = None
        if data.get("cancelled_at"):
            try:
                cancelled_at = dt.fromisoformat(data["cancelled_at"])
            except:
                pass
        admin_cancelled_at = None
        if data.get("admin_cancelled_at"):
            try:
                admin_cancelled_at = dt.fromisoformat(data["admin_cancelled_at"])
            except:
                pass
        return cls(
            id=data["id"],
            user_email=data["user_email"],
            car_vin=data["car_vin"],
            start_date=dt.strptime(data["start_date"], "%Y-%m-%d").date() if data.get("start_date") else None,
            end_date=dt.strptime(data["end_date"], "%Y-%m-%d").date() if data.get("end_date") else None,
            cost=data["cost"],
            status=data.get("status", "active"),
            created_at=dt.fromisoformat(data["created_at"]) if data.get("created_at") else dt.now(),
            return_date=dt.strptime(data["return_date"], "%Y-%m-%d").date() if data.get("return_date") else None,
            pickup_location=data.get("pickup_location"),
            return_location=data.get("return_location"),
            total_hours=data.get("total_hours"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            early_refund=data.get("early_refund"),
            late_fee=data.get("late_fee"),
            deposit_amount=data.get("deposit_amount", 0),
            deposit_refunded=data.get("deposit_refunded", False),
            insurance_selected=data.get("insurance_selected", False),
            insurance_cost=data.get("insurance_cost", 0),
            young_driver_fee=data.get("young_driver_fee", 0),
            cancelled_at=cancelled_at,
            admin_cancelled_at=admin_cancelled_at,
            damage_cost=data.get("damage_cost", 0.0),
            damage_status=data.get("damage_status", "none"),
            damage_description=data.get("damage_description"),
            damage_photos=data.get("damage_photos", []),
            damage_waiver=data.get("damage_waiver", False),
            damage_waiver_cost=data.get("damage_waiver_cost", 0.0),
            payment_id=data.get("payment_id"),
        )


# ---------- Database helper functions ----------
def _row_to_reservation(row, colnames):
    data = dict(zip(colnames, row))
    
    # Handle datetime casting
    cancelled_at = data.get('cancelled_at')
    if cancelled_at and not isinstance(cancelled_at, dt):
        cancelled_at = dt.fromisoformat(str(cancelled_at))
        
    admin_cancelled_at = data.get('admin_cancelled_at')
    if admin_cancelled_at and not isinstance(admin_cancelled_at, dt):
        admin_cancelled_at = dt.fromisoformat(str(admin_cancelled_at))
        
    # Handle JSON parsing
    damage_photos = data.get('damage_photos', [])
    if isinstance(damage_photos, str):
        try:
            damage_photos = json.loads(damage_photos)
        except:
            damage_photos = []

    # Strict Float Casting to prevent decimal.Decimal leakage
    cost = float(data['cost']) if data.get('cost') is not None else 0.0
    early_refund = float(data['early_refund']) if data.get('early_refund') is not None else None
    late_fee = float(data['late_fee']) if data.get('late_fee') is not None else None
    deposit_amount = float(data.get('deposit_amount') or 0.0)
    insurance_cost = float(data.get('insurance_cost') or 0.0)
    young_driver_fee = float(data.get('young_driver_fee') or 0.0)
    damage_cost = float(data.get('damage_cost') or 0.0)
    damage_waiver_cost = float(data.get('damage_waiver_cost') or 0.0)
    
    return Reservation(
        id=data['id'],
        user_email=data['user_email'],
        car_vin=data['car_vin'],
        start_date=data['start_date'],
        end_date=data['end_date'],
        cost=cost,
        created_at=data.get('created_at', dt.now()),
        status=data.get('status', 'active'),
        return_date=data.get('return_date'),
        pickup_location=data.get('pickup_location'),
        return_location=data.get('return_location'),
        total_hours=data.get('total_hours'),
        start_time=data.get('start_time'),
        end_time=data.get('end_time'),
        early_refund=early_refund,
        late_fee=late_fee,
        deposit_amount=deposit_amount,
        deposit_refunded=data.get('deposit_refunded', False),
        insurance_selected=data.get('insurance_selected', False),
        insurance_cost=insurance_cost,
        young_driver_fee=young_driver_fee,
        cancelled_at=cancelled_at,
        admin_cancelled_at=admin_cancelled_at,
        damage_cost=damage_cost,
        damage_status=data.get('damage_status', 'none'),
        damage_description=data.get('damage_description'),
        damage_photos=damage_photos,
        damage_waiver=data.get('damage_waiver', False),
        damage_waiver_cost=damage_waiver_cost,
        payment_id=data.get('payment_id'),
    )

def load_all_reservations():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM reservations")
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            return [_row_to_reservation(row, colnames) for row in rows]
    finally:
        db.release_connection(conn)

def load_reservation_by_id(rid):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM reservations WHERE id = %s", (rid,))
            row = cur.fetchone()
            if row:
                colnames = [desc[0] for desc in cur.description]
                return _row_to_reservation(row, colnames)
    finally:
        db.release_connection(conn)
    return None

def save_reservation_to_db(res):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reservations (
                    id, user_email, car_vin, start_date, end_date,
                    cost, status, created_at, return_date,
                    pickup_location, return_location, total_hours,
                    start_time, end_time, early_refund, late_fee,
                    deposit_amount, deposit_refunded,
                    insurance_selected, insurance_cost, young_driver_fee,
                    cancelled_at, admin_cancelled_at,
                    damage_cost, damage_status, damage_description, damage_photos,
                    damage_waiver, damage_waiver_cost,
                    payment_id
                ) VALUES (
                    %(id)s, %(user_email)s, %(car_vin)s, %(start_date)s, %(end_date)s,
                    %(cost)s, %(status)s, %(created_at)s, %(return_date)s,
                    %(pickup_location)s, %(return_location)s, %(total_hours)s,
                    %(start_time)s, %(end_time)s, %(early_refund)s, %(late_fee)s,
                    %(deposit_amount)s, %(deposit_refunded)s,
                    %(insurance_selected)s, %(insurance_cost)s, %(young_driver_fee)s,
                    %(cancelled_at)s, %(admin_cancelled_at)s,
                    %(damage_cost)s, %(damage_status)s, %(damage_description)s, %(damage_photos)s,
                    %(damage_waiver)s, %(damage_waiver_cost)s,
                    %(payment_id)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_email = EXCLUDED.user_email,
                    car_vin = EXCLUDED.car_vin,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    cost = EXCLUDED.cost,
                    status = EXCLUDED.status,
                    return_date = EXCLUDED.return_date,
                    pickup_location = EXCLUDED.pickup_location,
                    return_location = EXCLUDED.return_location,
                    total_hours = EXCLUDED.total_hours,
                    start_time = EXCLUDED.start_time,
                    end_time = EXCLUDED.end_time,
                    early_refund = EXCLUDED.early_refund,
                    late_fee = EXCLUDED.late_fee,
                    deposit_amount = EXCLUDED.deposit_amount,
                    deposit_refunded = EXCLUDED.deposit_refunded,
                    insurance_selected = EXCLUDED.insurance_selected,
                    insurance_cost = EXCLUDED.insurance_cost,
                    young_driver_fee = EXCLUDED.young_driver_fee,
                    cancelled_at = EXCLUDED.cancelled_at,
                    admin_cancelled_at = EXCLUDED.admin_cancelled_at,
                    damage_cost = EXCLUDED.damage_cost,
                    damage_status = EXCLUDED.damage_status,
                    damage_description = EXCLUDED.damage_description,
                    damage_photos = EXCLUDED.damage_photos,
                    damage_waiver = EXCLUDED.damage_waiver,
                    damage_waiver_cost = EXCLUDED.damage_waiver_cost,
                    payment_id = EXCLUDED.payment_id
            """, {
                'id': res.id,
                'user_email': res.user_email,
                'car_vin': res.car_vin,
                'start_date': res.start_date,
                'end_date': res.end_date,
                'cost': res.cost,
                'status': res.status,
                'created_at': res.created_at,
                'return_date': res.return_date,
                'pickup_location': res.pickup_location,
                'return_location': res.return_location,
                'total_hours': res.total_hours,
                'start_time': res.start_time,
                'end_time': res.end_time,
                'early_refund': res.early_refund,
                'late_fee': res.late_fee,
                'deposit_amount': res.deposit_amount,
                'deposit_refunded': res.deposit_refunded,
                'insurance_selected': res.insurance_selected,
                'insurance_cost': res.insurance_cost,
                'young_driver_fee': res.young_driver_fee,
                'cancelled_at': res.cancelled_at,
                'admin_cancelled_at': res.admin_cancelled_at,
                'damage_cost': res.damage_cost,
                'damage_status': res.damage_status,
                'damage_description': res.damage_description,
                'damage_photos': res.damage_photos,
                'damage_waiver': res.damage_waiver,
                'damage_waiver_cost': res.damage_waiver_cost,
                'payment_id': res.payment_id,
            })
            conn.commit()
    finally:
        db.release_connection(conn)

def delete_reservation_from_db(rid):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reservations WHERE id = %s", (rid,))
            conn.commit()
    finally:
        db.release_connection(conn)