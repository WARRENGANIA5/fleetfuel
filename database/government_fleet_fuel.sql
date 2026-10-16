-- ============================================================
-- Government Fleet Fuel Consumption Prediction System
-- Database: government_fleet_fuel_prediction
-- Guimaras State University - General Services Office
-- ============================================================

CREATE DATABASE IF NOT EXISTS government_fleet_fuel_prediction
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE government_fleet_fuel_prediction;

-- ------------------------------------------------------------
-- users
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) DEFAULT NULL,
    profile_photo VARCHAR(255) DEFAULT NULL,
    role ENUM('admin', 'staff') NOT NULL DEFAULT 'staff',
    status ENUM('active', 'inactive', 'pending') NOT NULL DEFAULT 'active',  -- 'pending' = signed up, awaiting admin approval
    notif_seen_at DATETIME DEFAULT NULL,  -- last time the user opened the notifications bell
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- drivers
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS drivers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(60) NOT NULL,
    last_name VARCHAR(60) NOT NULL,
    license_number VARCHAR(50) DEFAULT NULL,
    contact_number VARCHAR(30) DEFAULT NULL,
    status ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- vehicles
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL UNIQUE,
    vehicle_type VARCHAR(50) NOT NULL,
    brand_model VARCHAR(100) NOT NULL,
    engine_displacement DECIMAL(4,2) NOT NULL COMMENT 'in liters',
    fuel_type ENUM('Diesel', 'Gasoline') NOT NULL,
    year_model INT NOT NULL,
    status ENUM('Active', 'Maintenance', 'Inactive') NOT NULL DEFAULT 'Active',
    current_odometer DECIMAL(10,2) DEFAULT 0,
    seating_capacity INT NULL,
    station VARCHAR(100) NULL,
    assigned_driver VARCHAR(100) NULL,
    remarks VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- trip_records
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trip_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT NOT NULL,
    driver_id INT DEFAULT NULL,
    trip_date DATE NOT NULL,
    trip_type ENUM('Official Business', 'Errand', 'Hauling', 'Airport Transfer', 'Field Visit', 'Other') NOT NULL,
    departure_time TIME NOT NULL,
    route VARCHAR(150) NOT NULL,
    road_type ENUM('Paved', 'Unpaved', 'Mixed') NOT NULL,
    terrain_classification ENUM('Flat', 'Hilly', 'Mountainous') NOT NULL,
    odometer_reading DECIMAL(10,2) NOT NULL,
    distance_km DECIMAL(8,2) NOT NULL,
    duration_minutes DECIMAL(7,2) NOT NULL,
    avg_speed_kmh DECIMAL(6,2) NOT NULL,
    passenger_cargo_load_kg DECIMAL(8,2) NOT NULL DEFAULT 0,
    actual_fuel_consumption DECIMAL(7,2) DEFAULT NULL COMMENT 'liters, if measured',
    remarks VARCHAR(255) DEFAULT NULL,
    balance_in_tank DECIMAL(9,3) DEFAULT NULL COMMENT 'liters, as on the monthly report',
    fuel_received DECIMAL(9,3) DEFAULT NULL COMMENT 'liters',
    or_invoice_no VARCHAR(60) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- fuel_records
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fuel_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT NOT NULL,
    trip_record_id INT DEFAULT NULL,
    fuel_date DATE NOT NULL,
    fuel_type ENUM('Diesel', 'Gasoline') NOT NULL,
    liters_consumed DECIMAL(7,2) NOT NULL,
    odometer_reading DECIMAL(10,2) NOT NULL,
    fuel_cost DECIMAL(10,2) DEFAULT NULL,
    remarks VARCHAR(255) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
    FOREIGN KEY (trip_record_id) REFERENCES trip_records(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- predictions
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT DEFAULT NULL,
    vehicle_id INT DEFAULT NULL,
    odometer_reading DECIMAL(10,2) NOT NULL,
    distance_km DECIMAL(8,2) NOT NULL,
    duration_minutes DECIMAL(7,2) NOT NULL,
    avg_speed_kmh DECIMAL(6,2) NOT NULL,
    trip_type VARCHAR(50) NOT NULL,
    departure_time TIME NOT NULL,
    passenger_cargo_load_kg DECIMAL(8,2) NOT NULL DEFAULT 0,
    route VARCHAR(150) NOT NULL,
    road_type VARCHAR(30) NOT NULL,
    terrain_classification VARCHAR(30) NOT NULL,
    vehicle_type VARCHAR(50) NOT NULL,
    engine_displacement DECIMAL(4,2) NOT NULL,
    fuel_type VARCHAR(20) NOT NULL,
    year_model INT NOT NULL,
    predicted_fuel DECIMAL(7,2) NOT NULL,
    actual_fuel DECIMAL(7,2) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Fuel request review: staff submit a prediction, an administrator approves or rejects it
    approval_status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
    approved_fuel DECIMAL(7,2) DEFAULT NULL,  -- liters released (fuel allocation) when approved
    reviewed_by INT DEFAULT NULL,
    reviewed_at DATETIME DEFAULT NULL,
    review_note VARCHAR(255) DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- model_metrics
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_version VARCHAR(50) NOT NULL,
    r2_score DECIMAL(6,4) NOT NULL,
    mae DECIMAL(8,4) NOT NULL,
    rmse DECIMAL(8,4) NOT NULL,
    cv_folds INT NOT NULL,
    cv_mean_r2 DECIMAL(6,4) NOT NULL,
    cv_std_r2 DECIMAL(6,4) NOT NULL,
    train_size INT NOT NULL,
    test_size INT NOT NULL,
    status ENUM('active', 'archived') NOT NULL DEFAULT 'active',
    trained_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- NOTE: The default administrator account is created by
-- running `python seed_data.py` after this schema is imported.
-- Password hashing (werkzeug scrypt) must be generated in Python,
-- not hardcoded here, so the login will actually validate.
-- ------------------------------------------------------------

-- ------------------------------------------------------------
-- notification_dismissals: notifications a user removed from their bell
-- (the app also creates this table automatically if it is missing)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_dismissals (
    user_id INT NOT NULL,
    notif_key VARCHAR(80) NOT NULL,
    dismissed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, notif_key),
    CONSTRAINT fk_notif_dismissals_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;
