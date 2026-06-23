CREATE DATABASE IF NOT EXISTS medical_system
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'medical_user'@'localhost' IDENTIFIED BY '123456';

ALTER USER 'medical_user'@'localhost' IDENTIFIED BY '123456';

GRANT ALL PRIVILEGES ON medical_system.* TO 'medical_user'@'localhost';

FLUSH PRIVILEGES;

USE medical_system;

CREATE TABLE IF NOT EXISTS patients (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    age INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    patient_id BIGINT NOT NULL,
    result VARCHAR(50) NOT NULL,
    confidence DECIMAL(8, 6),
    tested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    remark VARCHAR(255),
    INDEX idx_test_records_patient_time (patient_id, tested_at),
    CONSTRAINT fk_test_records_patient
        FOREIGN KEY (patient_id) REFERENCES patients(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    action VARCHAR(100) NOT NULL,
    detail VARCHAR(500),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
