import database as db
from classes.car import load_all_cars, load_car_by_vin, save_car_to_db, delete_car_from_db

class Fleet:
    def __init__(self):
        self.cars = []  # Will be loaded on demand; we can keep a cache

    def get_cars(self):
        # Always fetch fresh from DB (or cache if you prefer)
        self.cars = load_all_cars()
        return self.cars

    def get_car_by_vin(self, vin):
        return load_car_by_vin(vin)

    def add_car(self, car):
        if not self.get_car_by_vin(car.vin):
            save_car_to_db(car)
            return True
        return False

    def remove_car(self, vin):
        car = self.get_car_by_vin(vin)
        if car:
            delete_car_from_db(vin)
            return True
        return False

    def load_cars(self):
        # Method kept for compatibility but no longer needed
        self.cars = load_all_cars()

    def save_cars(self):
        # No‑op, each car is saved independently
        pass