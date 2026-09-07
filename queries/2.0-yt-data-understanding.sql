/* ====================================================================================
   SCRIPT: 2.0-yt-data-understanding.sql
   OBJECTIVE: Establish a baseline understanding of dataset structure, health, and 
              statistical distributions for the Indonesian internship market.
   NOTE: This script demonstrates advanced PostgreSQL profiling techniques, 
                   including continuous percentile calculations for skewed data and 
                   array unnesting to simulate Python's .explode() natively in SQL.
   ==================================================================================== */

-- ------------------------------------------------------------------------------------
-- 1. STRUCTURAL CHECKS & HEALTH ASSESSMENT
-- Prove the datasets are exceptionally clean (0 missing values, 0 duplicates).
-- ------------------------------------------------------------------------------------

-- 1.1 Row counts for both tables
SELECT 
    'internship_positions' AS table_name, 
    COUNT(*) AS total_rows 
FROM internship_positions
UNION ALL
SELECT 
    'administrative_divisions' AS table_name, 
    COUNT(*) AS total_rows 
FROM administrative_divisions;

-- 1.2 Primary Key Duplicate Check
-- Returns 0 if data is perfectly healthy
SELECT 
    'Duplicate Job IDs' AS health_check,
    COUNT(job_id) - COUNT(DISTINCT job_id) AS duplicate_count
FROM internship_positions;

-- 1.3 Missing Value Matrix (Checking critical columns)
SELECT 
    COUNT(*) FILTER (WHERE job_title IS NULL) AS missing_titles,
    COUNT(*) FILTER (WHERE company IS NULL) AS missing_companies,
    COUNT(*) FILTER (WHERE job_location IS NULL) AS missing_locations,
    COUNT(*) FILTER (WHERE requested_quota IS NULL) AS missing_req_quotas,
    COUNT(*) FILTER (WHERE applicant_count IS NULL) AS missing_applicants
FROM internship_positions;


-- ------------------------------------------------------------------------------------
-- 2. DESCRIPTIVE STATISTICS: NUMERICAL DISTRIBUTIONS
-- Calculate Min, Max, Mean, Standard Deviation, and Quartiles (using PERCENTILE_CONT) 
-- to prove heavy right-skewness mathematically.
-- ------------------------------------------------------------------------------------

SELECT 
    'requested_quota' AS metric_name,
    MIN(requested_quota) AS min_val,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY requested_quota) AS p25,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY requested_quota) AS median_val,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY requested_quota) AS p75,
    MAX(requested_quota) AS max_val,
    ROUND(AVG(requested_quota), 2) AS mean_val,
    ROUND(STDDEV(requested_quota), 2) AS stddev_val
FROM internship_positions

UNION ALL

SELECT 
    'approved_quota' AS metric_name,
    MIN(approved_quota) AS min_val,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY approved_quota) AS p25,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY approved_quota) AS median_val,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY approved_quota) AS p75,
    MAX(approved_quota) AS max_val,
    ROUND(AVG(approved_quota), 2) AS mean_val,
    ROUND(STDDEV(approved_quota), 2) AS stddev_val
FROM internship_positions

UNION ALL

SELECT 
    'applicant_count' AS metric_name,
    MIN(applicant_count) AS min_val,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY applicant_count) AS p25,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY applicant_count) AS median_val,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY applicant_count) AS p75,
    MAX(applicant_count) AS max_val,
    ROUND(AVG(applicant_count), 2) AS mean_val,
    ROUND(STDDEV(applicant_count), 2) AS stddev_val
FROM internship_positions;


-- ------------------------------------------------------------------------------------
-- 3. DESCRIPTIVE STATISTICS: CATEGORICAL DISTRIBUTIONS
-- Identify the top baseline entities across the raw text columns.
-- ------------------------------------------------------------------------------------

-- 3.1 Top 5 Job Titles
SELECT 
    job_title, 
    COUNT(*) AS frequency,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM internship_positions), 2) AS pct_of_total
FROM internship_positions
GROUP BY job_title
ORDER BY frequency DESC
LIMIT 5;

-- 3.2 Top 5 Companies Hiring
SELECT 
    company, 
    COUNT(*) AS frequency
FROM internship_positions
GROUP BY company
ORDER BY frequency DESC
LIMIT 5;


-- ------------------------------------------------------------------------------------
-- 4. ADVANCED STRING PARSING (NATIVE SQL .EXPLODE() EQUIVALENT)
-- The allowed_major column contains comma-separated strings.
-- Using PostgreSQL's string_to_array() and unnest() to flatten the list into rows 
-- to find the true frequency of individual majors.
-- ------------------------------------------------------------------------------------

SELECT 
    TRIM(unnest(string_to_array(allowed_major, ','))) AS distinct_major,
    COUNT(*) AS frequency
FROM internship_positions
WHERE allowed_major IS NOT NULL
GROUP BY distinct_major
ORDER BY frequency DESC
LIMIT 10;