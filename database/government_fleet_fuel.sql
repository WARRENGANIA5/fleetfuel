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
-- vehicles: the vehicle records (plate number, vehicle model, fuel type,
-- engine power in kW from the manufacturer's published specifications)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehicles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL UNIQUE,
    brand_model VARCHAR(100) NOT NULL,
    fuel_type ENUM('Diesel', 'Gasoline') NOT NULL,
    engine_power_kw DECIMAL(6,2) DEFAULT NULL COMMENT 'kW',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- trip_records: the Monthly Report of Official Travel (date of travel,
-- vehicle, distance traveled, fuel consumed); merged with the vehicle
-- records by plate number for training
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trip_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT NOT NULL,
    trip_date DATE NOT NULL,
    distance_km DECIMAL(8,2) NOT NULL,
    actual_fuel_consumption DECIMAL(7,2) DEFAULT NULL COMMENT 'liters consumed',
    remarks VARCHAR(255) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- predictions: each prediction is stored in the prediction history and is a
-- fuel request that staff compare with the request before approval
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT DEFAULT NULL,
    vehicle_id INT DEFAULT NULL,
    distance_km DECIMAL(8,2) NOT NULL,
    engine_power_kw DECIMAL(6,2) DEFAULT NULL COMMENT 'from the vehicle record',
    fuel_type VARCHAR(20) NOT NULL COMMENT 'from the vehicle record',
    predicted_fuel DECIMAL(7,2) NOT NULL,
    actual_fuel DECIMAL(7,2) DEFAULT NULL,
    trip_record_id INT DEFAULT NULL,       -- trip the actual fuel was taken from
    actual_source VARCHAR(10) DEFAULT NULL, -- 'trip' (automatic) or 'manual'
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
