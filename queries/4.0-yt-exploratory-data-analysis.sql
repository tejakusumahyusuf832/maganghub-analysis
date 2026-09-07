/* ====================================================================================
   SCRIPT: 4.0-yt-exploratory-data-analysis.sql
   OBJECTIVE: Replicate analytical insights (bottlenecks, correlation, gatekeeping) 
              using the flattened analytical view.
   PORTFOLIO NOTE: This script demonstrates advanced PostgreSQL analytical capabilities, 
                   including Window Functions for Spearman Rank, PERCENTILE_CONT for 
                   medians, and conditional aggregation to natively simulate PivotTables.
   ==================================================================================== */

-- ------------------------------------------------------------------------------------
-- 1. UNIVARIATE ANALYSIS: REGIONAL BASELINES
-- Isolate the geographic center of gravity.
-- ------------------------------------------------------------------------------------

SELECT 
    province,
    COUNT(*) AS total_postings,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS market_share_pct
FROM vw_analytical_internship_postings
GROUP BY province
ORDER BY total_postings DESC
LIMIT 5;


-- ------------------------------------------------------------------------------------
-- 2. BIVARIATE ANALYSIS: SPEARMAN RANK CORRELATION
-- Simulating Spearman Rank mathematically in SQL by generating statistical ranks 
-- via Window Functions, then calculating the Pearson correlation of those ranks.
-- ------------------------------------------------------------------------------------

WITH ranked_data AS (
    SELECT 
        RANK() OVER (ORDER BY requested_quota ASC) AS rank_requested,
        RANK() OVER (ORDER BY approved_quota ASC) AS rank_approved,
        RANK() OVER (ORDER BY applicant_count ASC) AS rank_applicants,
        RANK() OVER (ORDER BY acceptance_percentage ASC) AS rank_acceptance
    FROM vw_analytical_internship_postings
)
SELECT 
    ROUND(CORR(rank_requested, rank_approved)::NUMERIC, 2) AS rho_req_vs_approved,
    ROUND(CORR(rank_applicants, rank_acceptance)::NUMERIC, 2) AS rho_applicants_vs_acceptance
FROM ranked_data;



-- ------------------------------------------------------------------------------------
-- 3. MULTIVARIATE "SLICER" SIMULATION: THE GENERALIST SURGE
-- Simulating an interactive dashboard filter natively in SQL using WHERE clauses
-- to prove how major requirements act as massive multipliers for applicant volume.
-- ------------------------------------------------------------------------------------

-- Scenario A: Baseline metrics when filtering for Social & Law majors (The Generalist Surge)
SELECT 
    'Social & Law Allowed' AS scenario,
    province,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY applicant_count) AS median_applicants,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY acceptance_percentage)::NUMERIC, 2) AS median_acceptance_pct
FROM vw_analytical_internship_postings
WHERE allows_social_and_law_majors = 'Yes'
GROUP BY province
ORDER BY median_acceptance_pct ASC
LIMIT 5;

-- Scenario B: Baseline metrics when filtering for IT & Computer majors (The Tech Baseline)
SELECT 
    'IT & Computer Allowed' AS scenario,
    province,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY applicant_count) AS median_applicants,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY acceptance_percentage)::NUMERIC, 2) AS median_acceptance_pct
FROM vw_analytical_internship_postings
WHERE allows_it_and_computer_majors = 'Yes'
GROUP BY province
ORDER BY median_acceptance_pct ASC
LIMIT 5;