/* ====================================================================================
   SCRIPT: 3.0-yt-data-preparation.sql
   OBJECTIVE: Transform raw relational data into a flattened, analytical schema.
   NOTE: This script demonstrates advanced PostgreSQL ETL workflows using 
                   Common Table Expressions (CTEs), robust NULL handling (NULLIF), 
                   text mining (ILIKE), and dynamic binning via CASE WHEN.
   ==================================================================================== */

CREATE OR REPLACE VIEW vw_analytical_internship_postings AS

WITH joined_data AS (
    -- 1. DATA INTEGRATION
    -- Join the primary positions table with the administrative divisions dimension table
    SELECT 
        ip.job_id,
        ip.published_at,
        ip.job_title,
        ip.company,
        ip.job_location,
        ad.province, -- Enriched from dimension table
        ip.allowed_major,
        ip.weekly_working_day,
        ip.requested_quota,
        ip.approved_quota,
        ip.applicant_count
    FROM internship_positions ip
    LEFT JOIN administrative_divisions ad
        ON ip.job_location = ad.regency
),

calculated_metrics AS (
    -- 2. FEATURE ENGINEERING: CALCULATIONS
    -- Safely calculate acceptance percentage preventing division by zero using NULLIF
    SELECT 
        *,
        ROUND(
            (approved_quota::NUMERIC / NULLIF(applicant_count + approved_quota, 0)) * 100, 
            2
        ) AS acceptance_percentage
    FROM joined_data
),

text_mining_majors AS (
    -- 3. FEATURE ENGINEERING: TEXT MINING (BOOLEAN FLAGS)
    -- Extract archetype flags from the comma-separated 'allowed_major' string using ILIKE
    SELECT 
        *,
        CASE 
            WHEN allowed_major ILIKE '%Manajemen%' 
              OR allowed_major ILIKE '%Ekonomi%' 
              OR allowed_major ILIKE '%Akuntansi%' 
              OR allowed_major ILIKE '%Bisnis%' THEN 'Yes' 
            ELSE 'No' 
        END AS allows_business_majors,

        CASE 
            WHEN allowed_major ILIKE '%Informatika%' 
              OR allowed_major ILIKE '%Komputer%' 
              OR allowed_major ILIKE '%Sistem Informasi%' THEN 'Yes' 
            ELSE 'No' 
        END AS allows_it_and_computer_majors,

        CASE 
            WHEN allowed_major ILIKE '%Hukum%' 
              OR allowed_major ILIKE '%Sosial%' 
              OR allowed_major ILIKE '%Komunikasi%' THEN 'Yes' 
            ELSE 'No' 
        END AS allows_social_and_law_majors
        
        -- Note: Additional major flags (Engineering, Health, Agriculture, etc.) 
        -- follow this identical robust parsing pattern.
    FROM calculated_metrics
)

-- 4. FEATURE ENGINEERING: DYNAMIC BINNING
-- Generate statistical buckets for Exploratory Data Analysis cross-tabs
SELECT 
    *,
    -- Binning Applicant Counts
    CASE 
        WHEN applicant_count <= 5 THEN '0 to 5'
        WHEN applicant_count BETWEEN 6 AND 10 THEN '6 to 10'
        WHEN applicant_count BETWEEN 11 AND 20 THEN '11 to 20'
        WHEN applicant_count BETWEEN 21 AND 50 THEN '21 to 50'
        ELSE '50+' 
    END AS applicant_count_category,

    -- Binning Quotas
    CASE 
        WHEN requested_quota <= 2 THEN '1 to 2'
        WHEN requested_quota BETWEEN 3 AND 5 THEN '3 to 5'
        WHEN requested_quota BETWEEN 6 AND 10 THEN '6 to 10'
        ELSE '11+' 
    END AS requested_quota_category,

    -- Binning Acceptance Rates
    CASE 
        WHEN acceptance_percentage <= 10.00 THEN '0 - 10%'
        WHEN acceptance_percentage BETWEEN 10.01 AND 25.00 THEN '11 - 25%'
        WHEN acceptance_percentage BETWEEN 25.01 AND 50.00 THEN '26 - 50%'
        ELSE '50%+' 
    END AS acceptance_percentage_category

FROM text_mining_majors;

-- 5. SHOWING THE VIEW
SELECT * FROM vw_analytical_internship_postings
LIMIT 50;