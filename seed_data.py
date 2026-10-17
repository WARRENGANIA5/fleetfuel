"""
Seeds the government_fleet_fuel_prediction database with:
- a default administrator account (hashed password, generated properly
  here in Python instead of a hardcoded hash in the SQL file)
- a GSO staff account
- sample vehicle records (plate number, model, fuel type, engine power) and
  trip records (date of travel, distance traveled, fuel consumed) so the
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

# plate number, vehicle model, fuel type, engine power (kW)
VEHICLES = [
    ("SFB-1234", "Toyota Vios", "Gasoline", 79),
    ("SFB-2211", "Honda City", "Gasoline", 89),
    ("SFB-3390", "Toyota Fortuner", "Diesel", 110),
    ("SFB-4471", "Mitsubishi Montero Sport", "Diesel", 133),
    ("SFB-5502", "Toyota Hiace", "Diesel", 115),
    ("SFB-6633", "Nissan Urvan", "Diesel", 95),
    ("SFB-7744", "Toyota Hilux", "Diesel", 110),
    ("SFB-8855", "Ford Ranger", "Diesel", 118),
    ("SFB-9900", "Isuzu Forward", "Diesel", 177),
]


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


def seed_vehicles(cur):
    cur.execute("SELECT COUNT(*) AS c FROM vehicles")
    if cur.fetchone()["c"] > 0:
        print("Vehicles already exist, skipping.")
        return
    for plate, model, fuel, power in VEHICLES:
        cur.execute("INSERT INTO vehicles (plate_number, brand_model, fuel_type, engine_power_kw) VALUES (%s,%s,%s,%s)",
                    (plate, model, fuel, power))
    print(f"Seeded {len(VEHICLES)} vehicles.")


def fuel_rate(power_kw, fuel_type):
    """Liters per 100 km for the sample data: larger engines use more fuel per
    kilometre, and a gasoline engine more than a diesel of the same power."""
    return (4.5 + 0.045 * power_kw) * (1.15 if fuel_type == "Gasoline" else 1.0)


def seed_trips(cur):
    cur.execute("SELECT COUNT(*) AS c FROM trip_records")
    if cur.fetchone()["c"] > 0:
        print("Trip records already exist, skipping.")
        return
    cur.execute("SELECT id, fuel_type, engine_power_kw FROM vehicles")
    today = date.today()
    count = 0
    for v in cur.fetchall():
        for _ in range(RNG.randint(8, 14)):
            trip_date = today - timedelta(days=RNG.randint(1, 180))
            distance = round(RNG.uniform(5, 150), 1)
            fuel = round(distance / 100 * fuel_rate(float(v["engine_power_kw"]), v["fuel_type"]) * RNG.uniform(0.92, 1.1), 2)
            cur.execute("""INSERT INTO trip_records (vehicle_id, trip_date, distance_km, actual_fuel_consumption)
                           VALUES (%s,%s,%s,%s)""", (v["id"], trip_date, distance, fuel))
            count += 1
    print(f"Seeded {count} trip records.")


def seed_sample_predictions(cur):
    cur.execute("SELECT COUNT(*) AS c FROM predictions")
    if cur.fetchone()["c"] > 0:
        print("Predictions already exist, skipping.")
        return
    cur.execute("SELECT id FROM users WHERE username='admin'")
    admin_id = cur.fetchone()["id"]
    cur.execute("SELECT id, fuel_type, engine_power_kw FROM vehicles")
    vehicle_rows = cur.fetchall()

    count = 0
    for v in RNG.sample(vehicle_rows, min(6, len(vehicle_rows))):
        distance = round(RNG.uniform(10, 120), 1)
        predicted = round(distance / 100 * fuel_rate(float(v["engine_power_kw"]), v["fuel_type"]), 2)
        created_at = datetime.now() - timedelta(
            days=RNG.randint(0, 13), hours=RNG.randint(0, 23), minutes=RNG.randint(0, 59))
        cur.execute("""
            INSERT INTO predictions (user_id, vehicle_id, distance_km, engine_power_kw, fuel_type, predicted_fuel, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (admin_id, v["id"], distance, v["engine_power_kw"], v["fuel_type"], predicted, created_at))
        count += 1
    print(f"Seeded {count} sample prediction records.")


def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            seed_users(cur)
            seed_vehicles(cur)
            seed_trips(cur)
            seed_sample_predictions(cur)
    finally:
        conn.close()
    print("\nDatabase seeding complete.")


if __name__ == "__main__":
    main()
