"""
Seeds the government_fleet_fuel_prediction database with:
- a default administrator account (hashed password, generated properly
  here in Python instead of a hardcoded hash in the SQL file)
- a GSO staff account
- sample drivers, vehicles, trip records and fuel records so the
  dashboard and modules are populated with real (seeded) database rows
  instead of empty tables on first run.

Run:  python seed_data.py   (after importing database/government_fleet_fuel.sql)
Safe to re-run: skips seeding sections that already have data.
"""
import random
from datetime import date, datetime, timedelta

import pymysql
import pymysql.cursors
from werkzeug.security import generate_password_hash

from config import Config

RNG = random.Random(7)

VEHICLES = [
    ("SFB-1234", "Sedan", "Toyota Vios", 1.5, "Gasoline", 2019),
    ("SFB-2211", "Sedan", "Honda City", 1.5, "Gasoline", 2021),
    ("SFB-3390", "SUV", "Toyota Fortuner", 2.4, "Diesel", 2020),
    ("SFB-4471", "SUV", "Mitsubishi Montero Sport", 2.4, "Diesel", 2018),
    ("SFB-5502", "Van", "Toyota Hiace", 2.8, "Diesel", 2017),
    ("SFB-6633", "Van", "Nissan Urvan", 2.5, "Diesel", 2016),
    ("SFB-7744", "Pickup Truck", "Toyota Hilux", 2.4, "Diesel", 2022),
    ("SFB-8855", "Pickup Truck", "Ford Ranger", 2.2, "Diesel", 2019),
    ("SFB-9900", "Service Bus", "Isuzu Forward", 5.2, "Diesel", 2015),
    ("SFB-1015", "Dump Truck", "Isuzu Elf", 4.6, "Diesel", 2014),
    ("SFB-1120", "Motorcycle", "Honda XRM 125", 0.125, "Gasoline", 2023),
]

DRIVERS = [
    ("Ramon", "Dela Cruz"), ("Ernesto", "Villanueva"), ("Federico", "Sarmiento"),
    ("Anselmo", "Bautista"), ("Dominador", "Reyes"), ("Rogelio", "Fajardo"),
]

ROUTES = [
    "Jordan - San Miguel", "Buenavista - Jordan", "Jordan - Nueva Valencia",
    "San Lorenzo - Jordan", "Jordan - Sibunag", "Capitol - Buenavista Port",
    "Campus - Jordan Port", "Campus - Buenavista Campus",
]
TRIP_TYPES = ["Official Business", "Errand", "Hauling", "Airport Transfer", "Field Visit", "Other"]
ROAD_TYPES = ["Paved", "Unpaved", "Mixed"]
TERRAINS = ["Flat", "Hilly", "Mountainous"]


def get_conn():
    return pymysql.connect(
        host=Config.MYSQL_HOST, port=Config.MYSQL_PORT, user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD, database=Config.MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )


def seed_users(cur):
    cur.execute("SELECT COUNT(*) AS c FROM users")
    if cur.fetchone()["c"] > 0:
        print("Users already exist, skipping.")
        return
    cur.execute(
        "INSERT INTO users (username, password_hash, full_name, email, role, status) VALUES (%s,%s,%s,%s,%s,%s)",
        ("admin", generate_password_hash("Admin@12345"), "GSO System Administrator",
         "gso.admin@gsu.edu.ph", "admin", "active"),
    )
    cur.execute(
        "INSERT INTO users (username, password_hash, full_name, email, role, status) VALUES (%s,%s,%s,%s,%s,%s)",
        ("motorpool", generate_password_hash("Motorpool@2026"), "Motorpool Staff",
         "motorpool@gsu.edu.ph", "staff", "active"),
    )
    print("Seeded users: admin / Admin@12345, motorpool / Motorpool@2026")


def seed_drivers(cur):
    cur.execute("SELECT COUNT(*) AS c FROM drivers")
    if cur.fetchone()["c"] > 0:
        print("Drivers already exist, skipping.")
        return
    for fn, ln in DRIVERS:
        cur.execute(
            "INSERT INTO drivers (first_name, last_name, license_number, contact_number, status) VALUES (%s,%s,%s,%s,'active')",
            (fn, ln, f"N{RNG.randint(10000000,99999999)}-{RNG.randint(2020,2030)}", f"09{RNG.randint(100000000,999999999)}"),
        )
    print(f"Seeded {len(DRIVERS)} drivers.")


def seed_vehicles(cur):
    cur.execute("SELECT COUNT(*) AS c FROM vehicles")
    if cur.fetchone()["c"] > 0:
        print("Vehicles already exist, skipping.")
        return
    for plate, vtype, brand, disp, fuel, year in VEHICLES:
        cur.execute("""
            INSERT INTO vehicles (plate_number, vehicle_type, brand_model, engine_displacement,
                fuel_type, year_model, current_odometer, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'Active')
        """, (plate, vtype, brand, disp, fuel, year, RNG.uniform(8000, 150000)))
    print(f"Seeded {len(VEHICLES)} vehicles.")


def load_factor(load_kg, capacity):
    return 1.0 + min(load_kg / capacity, 1.5) * 0.22


TERRAIN_FACTOR = {"Flat": 1.00, "Hilly": 1.18, "Mountainous": 1.38}
ROAD_FACTOR = {"Paved": 1.00, "Mixed": 1.10, "Unpaved": 1.25}
BASE_RATE = {"Sedan": 6.4, "SUV": 8.6, "Van": 9.6, "Pickup Truck": 8.7, "Service Bus": 16.5, "Dump Truck": 15.2, "Motorcycle": 2.1}
CAPACITY = {"Sedan": 400, "SUV": 500, "Van": 1200, "Pickup Truck": 800, "Service Bus": 2500, "Dump Truck": 4000, "Motorcycle": 150}


def seed_trips_and_fuel(cur):
    cur.execute("SELECT COUNT(*) AS c FROM trip_records")
    if cur.fetchone()["c"] > 0:
        print("Trip records already exist, skipping.")
        return

    cur.execute("SELECT id, vehicle_type, fuel_type FROM vehicles")
    vehicle_rows = cur.fetchall()
    cur.execute("SELECT id FROM drivers")
    driver_ids = [r["id"] for r in cur.fetchall()]

    today = date.today()
    trip_count, fuel_count = 0, 0

    for v in vehicle_rows:
        n_trips = RNG.randint(8, 14)
        for _ in range(n_trips):
            days_ago = RNG.randint(1, 180)
            trip_date = today - timedelta(days=days_ago)
            distance = round(RNG.uniform(5, 150), 1)
            avg_speed = round(RNG.uniform(20, 85), 1)
            duration = round((distance / avg_speed) * 60 * RNG.uniform(0.95, 1.15), 1)
            trip_type = RNG.choice(TRIP_TYPES)
            road_type = RNG.choice(ROAD_TYPES)
            terrain = RNG.choice(TERRAINS)
            load_kg = round(RNG.uniform(0, CAPACITY[v["vehicle_type"]]), 1)
            odometer = round(RNG.uniform(5000, 150000), 1)
            hour = RNG.randint(5, 21)

            rate = (BASE_RATE[v["vehicle_type"]] * TERRAIN_FACTOR[terrain] * ROAD_FACTOR[road_type]
                    * load_factor(load_kg, CAPACITY[v["vehicle_type"]]) * RNG.uniform(0.95, 1.1))
            actual_fuel = round((distance / 100) * rate, 2)

            cur.execute("""
                INSERT INTO trip_records (vehicle_id, driver_id, trip_date, trip_type, departure_time,
                    route, road_type, terrain_classification, odometer_reading, distance_km,
                    duration_minutes, avg_speed_kmh, passenger_cargo_load_kg, actual_fuel_consumption)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (v["id"], RNG.choice(driver_ids), trip_date, trip_type, f"{hour:02d}:{RNG.randint(0,59):02d}:00",
                  RNG.choice(ROUTES), road_type, terrain, odometer, distance, duration, avg_speed,
                  load_kg, actual_fuel))
            trip_id = cur.lastrowid
            trip_count += 1

            cur.execute("""
                INSERT INTO fuel_records (vehicle_id, trip_record_id, fuel_date, fuel_type,
                    liters_consumed, odometer_reading, fuel_cost, remarks)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (v["id"], trip_id, trip_date, v["fuel_type"], actual_fuel, odometer,
                  round(actual_fuel * (65 if v["fuel_type"] == "Diesel" else 72), 2), "Auto-logged from trip"))
            fuel_count += 1

    print(f"Seeded {trip_count} trip records and {fuel_count} fuel records.")


def seed_sample_predictions(cur):
    cur.execute("SELECT COUNT(*) AS c FROM predictions")
    if cur.fetchone()["c"] > 0:
        print("Predictions already exist, skipping.")
        return
    cur.execute("SELECT id FROM users WHERE username='admin'")
    admin_id = cur.fetchone()["id"]
    cur.execute("SELECT id, vehicle_type, engine_displacement, fuel_type, year_model FROM vehicles")
    vehicle_rows = cur.fetchall()

    count = 0
    for v in RNG.sample(vehicle_rows, min(6, len(vehicle_rows))):
        distance = round(RNG.uniform(10, 120), 1)
        avg_speed = round(RNG.uniform(25, 80), 1)
        duration = round((distance / avg_speed) * 60, 1)
        terrain = RNG.choice(TERRAINS)
        road_type = RNG.choice(ROAD_TYPES)
        load_kg = round(RNG.uniform(0, 300), 1)
        rate = BASE_RATE[v["vehicle_type"]] * TERRAIN_FACTOR[terrain] * ROAD_FACTOR[road_type]
        predicted = round((distance / 100) * rate * RNG.uniform(0.98, 1.05), 2)
        actual = round(predicted * RNG.uniform(0.9, 1.1), 2)
        created_at = datetime.now() - timedelta(
            days=RNG.randint(0, 13), hours=RNG.randint(0, 23), minutes=RNG.randint(0, 59))

        cur.execute("""
            INSERT INTO predictions (user_id, vehicle_id, odometer_reading, distance_km, duration_minutes,
                avg_speed_kmh, trip_type, departure_time, passenger_cargo_load_kg, route, road_type,
                terrain_classification, vehicle_type, engine_displacement, fuel_type, year_model,
                predicted_fuel, actual_fuel, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (admin_id, v["id"], round(RNG.uniform(10000, 100000), 1), distance, duration, avg_speed,
              RNG.choice(TRIP_TYPES), f"{RNG.randint(6,20):02d}:00:00", load_kg, RNG.choice(ROUTES),
              road_type, terrain, v["vehicle_type"], v["engine_displacement"], v["fuel_type"],
              v["year_model"], predicted, actual, created_at))
        count += 1
    print(f"Seeded {count} sample prediction records.")


def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            seed_users(cur)
            seed_drivers(cur)
            seed_vehicles(cur)
            seed_trips_and_fuel(cur)
            seed_sample_predictions(cur)
    finally:
        conn.close()
    print("\nDatabase seeding complete.")


if __name__ == "__main__":
    main()
