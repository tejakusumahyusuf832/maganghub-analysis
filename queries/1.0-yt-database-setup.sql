/*
===============================================================================
Database Setup: maganghub_analysis_db
Description: DDL script to initialize the database schema for MagangHub Analysis.
===============================================================================
*/

-- 1. Create Database (Run this separately if using a UI, or uncomment below)
-- CREATE DATABASE maganghub_analysis_db;

-- Connect to your database before running the tables below.

/* ===============================================================================
TABLES
===============================================================================
*/

-- 1. Administrative Divisions
CREATE TABLE IF NOT EXISTS administrative_divisions (
    regency_id SMALLINT PRIMARY KEY,
    province_id SMALLINT,
    regency VARCHAR(50),
    province VARCHAR(50)
);
COMMENT ON TABLE administrative_divisions IS 'Registry of Indonesian cities and regencies with their assigned provinces.';

-- 2. Internship Positions
CREATE TABLE IF NOT EXISTS internship_positions (
    job_id VARCHAR(50) PRIMARY KEY,
    published_at TIMESTAMP WITH TIME ZONE NOT NULL,
    job_title TEXT NOT NULL,
    company TEXT NOT NULL,
    job_location VARCHAR(50),
    education_level VARCHAR(50),
    allowed_major TEXT NOT NULL,
    job_description TEXT,
    weekly_working_day SMALLINT DEFAULT 0,
    requested_quota SMALLINT DEFAULT 0,
    approved_quota SMALLINT DEFAULT 0,
    applicant_count SMALLINT DEFAULT 0
);
COMMENT ON TABLE internship_positions IS 'Stores all the available internship positions with their information from the MagangHub website.';

/* ===============================================================================
INDEXES
===============================================================================
*/

-- 1. Filter Indexes 
-- Indexing job_location speeds up queries to pull data for specific cities into Python.
CREATE INDEX idx_internship_positions_job_location ON internship_positions(job_location);
CREATE INDEX idx_admin_divisions_province_id ON administrative_divisions(province_id);

-- 2. Sorting & Exact Match Indexes
CREATE INDEX idx_internship_positions_published_at ON internship_positions(published_at DESC);
CREATE INDEX idx_internship_positions_company ON internship_positions(company);