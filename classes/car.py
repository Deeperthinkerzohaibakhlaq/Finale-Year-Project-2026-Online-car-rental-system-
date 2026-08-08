# classes/car.py
from abc import ABC, abstractmethod
import json
import database as db


class Car(ABC):
    def __init__(
        self,
        vin,
        model,
        base_rate,
        img_url,
        seating_capacity,
        colour,
        car_type,
        features,
        rental_history=None,
        deposit_amount=5000,               # ← NEW: per-car security deposit
    ):
        if rental_history is None:
            rental_history = {"active": [], "inactive": []}
        self.vin = vin
        self.model = model
        self.base_rate = base_rate
        self.img_url = img_url
        self.seating_capacity = seating_capacity
        self.colour = colour
        self.car_type = car_type
        self.features = features
        self.rental_history = rental_history
        self.deposit_amount = deposit_amount   # ← NEW

    # Getters
    def get_vin(self): return self.vin
    def get_model(self): return self.model
    def get_base_rate(self): return self.base_rate
    def get_img_url(self): return self.img_url
    def get_seating_capacity(self): return self.seating_capacity
    def get_colour(self): return self.colour
    def get_car_type(self): return self.car_type
    def get_features(self): return self.features
    def get_active_reservation(self): return self.rental_history["active"]
    def get_inactive_reservations(self): return self.rental_history["inactive"]
    def get_deposit_amount(self): return self.deposit_amount           # ← NEW

    # Setters
    def set_vin(self, vin): self.vin = vin
    def set_model(self, model): self.model = model
    def set_base_rate(self, base_rate): self.base_rate = base_rate
    def set_img_url(self, img_url): self.img_url = img_url
    def set_seating_capacity(self, seating_capacity): self.seating_capacity = seating_capacity
    def set_colour(self, colour): self.colour = colour
    def set_car_type(self, car_type): self.car_type = car_type
    def set_features(self, features): self.features = features
    def set_deposit_amount(self, amount): self.deposit_amount = amount  # ← NEW

    def set_rental_history(self, status, reservation_id):
        if status == "active":
            if self.rental_history["active"] is None:
                self.rental_history["active"] = []
            self.rental_history["active"].append(reservation_id)
        elif status == "inactive":
            self.rental_history["inactive"].append(reservation_id)
        elif status == "delete":
            if reservation_id in self.rental_history["active"]:
                self.rental_history["active"].remove(reservation_id)

    def delete_reservation(self, reservation_id):
        if reservation_id in self.rental_history["active"]:
            self.rental_history["active"].remove(reservation_id)
        elif reservation_id in self.rental_history["inactive"]:
            self.rental_history["inactive"].remove(reservation_id)

    @abstractmethod
    def calculate_rental_cost(self, days):
        pass

    def to_dict(self):
        return {
            "vin": self.vin,
            "model": self.model,
            "base_rate": self.base_rate,
            "img_url": self.img_url,
            "seating_capacity": self.seating_capacity,
            "colour": self.colour,
            "car_type": self.car_type,
            "features": self.features,
            "category": self.__class__.__name__,
            "rental_history": self.rental_history,
            "deposit_amount": self.deposit_amount,          # ← NEW
        }


class EconomyCar(Car):
    def __init__(
        self,
        vin,
        model,
        base_rate,
        img_url,
        seating_capacity,
        colour,
        car_type,
        features,
        fuel_efficiency,
        rental_history={"active": None, "inactive": []},
        deposit_amount=5000,                               # ← NEW
    ):
        super().__init__(
            vin, model, base_rate, img_url, seating_capacity,
            colour, car_type, features, rental_history,
            deposit_amount=deposit_amount                   # ← NEW
        )
        self.fuel_efficiency = fuel_efficiency

    def calculate_rental_cost(self, days):
        base = float(self.base_rate)
        fuel_eff = float(self.fuel_efficiency) if self.fuel_efficiency is not None else 0.0
        return (base + fuel_eff * 10) * days

    def get_fuel_efficiency(self): return self.fuel_efficiency
    def set_fuel_efficiency(self, fuel_efficiency): self.fuel_efficiency = fuel_efficiency

    def to_dict(self):
        return super().to_dict() | {"fuel_efficiency": self.fuel_efficiency}

    @classmethod
    def from_dict(cls, data):
        return cls(
            vin=data["vin"],
            model=data["model"],
            base_rate=data["base_rate"],
            img_url=data["img_url"],
            seating_capacity=data["seating_capacity"],
            colour=data["colour"],
            car_type=data["car_type"],
            features=data["features"],
            fuel_efficiency=data["fuel_efficiency"],
            rental_history=data["rental_history"],
            deposit_amount=data.get("deposit_amount", 5000),   # ← NEW
        )


class LuxuryCar(Car):
    def __init__(
        self,
        vin,
        model,
        base_rate,
        img_url,
        seating_capacity,
        colour,
        car_type,
        features,
        chauffeur_available,
        rental_history={"active": None, "inactive": []},
        deposit_amount=5000,                               # ← NEW
    ):
        super().__init__(
            vin, model, base_rate, img_url, seating_capacity,
            colour, car_type, features, rental_history,
            deposit_amount=deposit_amount                   # ← NEW
        )
        self.chauffeur_available = chauffeur_available

    def calculate_rental_cost(self, days):
        base = float(self.base_rate)
        chauffeur = int(self.chauffeur_available)  # 0 or 1
        return (base + chauffeur * 3000) * days

    def get_chauffeur_available(self): return self.chauffeur_available
    def set_chauffeur_available(self, chauffeur_available): self.chauffeur_available = chauffeur_available

    def to_dict(self):
        return super().to_dict() | {"chauffeur_available": self.chauffeur_available}

    @classmethod
    def from_dict(cls, data):
        return cls(
            vin=data["vin"],
            model=data["model"],
            base_rate=data["base_rate"],
            img_url=data["img_url"],
            seating_capacity=data["seating_capacity"],
            colour=data["colour"],
            car_type=data["car_type"],
            features=data["features"],
            chauffeur_available=data["chauffeur_available"],
            rental_history=data["rental_history"],
            deposit_amount=data.get("deposit_amount", 5000),   # ← NEW
        )


class CommercialCar(Car):
    def __init__(
        self,
        vin,
        model,
        base_rate,
        img_url,
        seating_capacity,
        colour,
        car_type,
        features,
        cargo_capacity,
        rental_history={"active": None, "inactive": []},
        deposit_amount=5000,                               # ← NEW
    ):
        super().__init__(
            vin, model, base_rate, img_url, seating_capacity,
            colour, car_type, features, rental_history,
            deposit_amount=deposit_amount                   # ← NEW
        )
        self.cargo_capacity = cargo_capacity

    def calculate_rental_cost(self, days):
        base = float(self.base_rate)
        cargo = float(self.cargo_capacity) if self.cargo_capacity is not None else 0.0
        return (base * days) + (cargo * 10)

    def get_cargo_capacity(self): return self.cargo_capacity
    def set_cargo_capacity(self, cargo_capacity): self.cargo_capacity = cargo_capacity

    def to_dict(self):
        return super().to_dict() | {"cargo_capacity": self.cargo_capacity}

    @classmethod
    def from_dict(cls, data):
        return cls(
            vin=data["vin"],
            model=data["model"],
            base_rate=data["base_rate"],
            img_url=data["img_url"],
            seating_capacity=data["seating_capacity"],
            colour=data["colour"],
            car_type=data["car_type"],
            features=data["features"],
            cargo_capacity=data["cargo_capacity"],
            rental_history=data["rental_history"],
            deposit_amount=data.get("deposit_amount", 5000),   # ← NEW
        )


# Mapping of car categories to classes
CAR_CLASS_MAP = {
    "EconomyCar": EconomyCar,
    "LuxuryCar": LuxuryCar,
    "CommercialCar": CommercialCar,
}


# ---------- Database helper functions (updated) ----------
def _row_to_car(row, colnames):
    data = dict(zip(colnames, row))
    car_type = data.get('car_type')
    features = data.get('features', {})
    if isinstance(features, str):
        features = json.loads(features)

    rental_history = {
        'active': data.get('active_reservation_ids', []),
        'inactive': data.get('inactive_reservation_ids', [])
    }
    if isinstance(rental_history['active'], str):
        rental_history['active'] = json.loads(rental_history['active'])
    if isinstance(rental_history['inactive'], str):
        rental_history['inactive'] = json.loads(rental_history['inactive'])

    common = {
        'vin': data['vin'],
        'model': data['model'],
        'base_rate': data['base_rate'],
        'img_url': data.get('img_url'),
        'seating_capacity': data.get('seating_capacity'),
        'colour': data.get('colour'),
        'car_type': car_type,
        'features': features,
        'rental_history': rental_history,
        'deposit_amount': data.get('deposit_amount', 5000)   # ← NEW
    }

    if car_type == 'EconomyCar':
        return EconomyCar(fuel_efficiency=data.get('fuel_efficiency', 0), **common)
    elif car_type == 'LuxuryCar':
        return LuxuryCar(chauffeur_available=data.get('chauffeur_available', False), **common)
    elif car_type == 'CommercialCar':
        return CommercialCar(cargo_capacity=data.get('cargo_capacity', 0), **common)
    else:
        raise ValueError(f"Unknown car type: {car_type}")


def load_all_cars():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cars")
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            return [_row_to_car(row, colnames) for row in rows]
    finally:
        db.release_connection(conn)


def load_car_by_vin(vin):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cars WHERE vin = %s", (vin,))
            row = cur.fetchone()
            if row:
                colnames = [desc[0] for desc in cur.description]
                return _row_to_car(row, colnames)
    finally:
        db.release_connection(conn)
    return None


def save_car_to_db(car):
    conn = db.get_connection()
    try:
        data = {
            'vin': car.vin,
            'model': car.model,
            'base_rate': car.base_rate,
            'img_url': car.img_url,
            'seating_capacity': car.seating_capacity,
            'colour': car.colour,
            'car_type': car.__class__.__name__,
            'features': json.dumps(car.features),
            'fuel_efficiency': getattr(car, 'fuel_efficiency', None),
            'chauffeur_available': getattr(car, 'chauffeur_available', None),
            'cargo_capacity': getattr(car, 'cargo_capacity', None),
            'active_reservation_ids': json.dumps(car.rental_history.get('active', [])),
            'inactive_reservation_ids': json.dumps(car.rental_history.get('inactive', [])),
            'deposit_amount': car.deposit_amount                     # ← NEW
        }
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cars (vin, model, base_rate, img_url, seating_capacity, colour,
                                  car_type, features, fuel_efficiency, chauffeur_available,
                                  cargo_capacity, active_reservation_ids, inactive_reservation_ids,
                                  deposit_amount)
                VALUES (%(vin)s, %(model)s, %(base_rate)s, %(img_url)s, %(seating_capacity)s, %(colour)s,
                        %(car_type)s, %(features)s, %(fuel_efficiency)s, %(chauffeur_available)s,
                        %(cargo_capacity)s, %(active_reservation_ids)s, %(inactive_reservation_ids)s,
                        %(deposit_amount)s)
                ON CONFLICT (vin) DO UPDATE SET
                    model = EXCLUDED.model,
                    base_rate = EXCLUDED.base_rate,
                    img_url = EXCLUDED.img_url,
                    seating_capacity = EXCLUDED.seating_capacity,
                    colour = EXCLUDED.colour,
                    car_type = EXCLUDED.car_type,
                    features = EXCLUDED.features,
                    fuel_efficiency = EXCLUDED.fuel_efficiency,
                    chauffeur_available = EXCLUDED.chauffeur_available,
                    cargo_capacity = EXCLUDED.cargo_capacity,
                    active_reservation_ids = EXCLUDED.active_reservation_ids,
                    inactive_reservation_ids = EXCLUDED.inactive_reservation_ids,
                    deposit_amount = EXCLUDED.deposit_amount
            """, data)
            conn.commit()
    finally:
        db.release_connection(conn)


def delete_car_from_db(vin):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cars WHERE vin = %s", (vin,))
            conn.commit()
    finally:
        db.release_connection(conn)