-- Patient ID format setup (run in psql or pgAdmin on database: hms)
-- Switch active format: set is_selected = true on ONE row only.

-- 1) Insert default formats (skip if any row already exists)
INSERT INTO patient_no_formats (
    id, code, name, pattern, sample_output,
    seq_pad_width, is_selected, sort_order, is_active, created_at, updated_at
)
SELECT * FROM (VALUES
    (gen_random_uuid(), 'SECTION_DAILY', 'Section + Full Date + Daily Seq',
     '{SECTION}{YYYYMMDD}{SEQ:3}', 'P20260619001', 3, true, 1, true, now(), now()),
    (gen_random_uuid(), 'PREFIX_DAILY', 'Prefix + Full Date + Daily Seq',
     '{PREFIX}{YYYYMMDD}{SEQ:3}', 'P20260619001', 3, false, 2, true, now(), now()),
    (gen_random_uuid(), 'PREFIX_SHORT_DATE', 'Prefix + Short Date + Daily Seq',
     '{PREFIX}{YYMMDD}{SEQ:3}', 'P260619002', 3, false, 3, true, now(), now()),
    (gen_random_uuid(), 'SIMPLE', 'Simple Incremental',
     '{SEQ}', '1', 0, false, 4, true, now(), now())
) AS v(id, code, name, pattern, sample_output, seq_pad_width, is_selected, sort_order, is_active, created_at, updated_at)
WHERE NOT EXISTS (SELECT 1 FROM patient_no_formats LIMIT 1);

-- 2) Examples: pick ONE format for your hospital
-- Simple 1, 2, 3:
--   UPDATE patient_no_formats SET is_selected = false;
--   UPDATE patient_no_formats SET is_selected = true WHERE code = 'SIMPLE';

-- P20260619001 style (section letter + full date + daily seq):
--   UPDATE patient_no_formats SET is_selected = false;
--   UPDATE patient_no_formats SET is_selected = true WHERE code = 'SECTION_DAILY';

-- P260619002 style (prefix + short date + daily seq):
--   UPDATE patient_no_formats SET is_selected = false;
--   UPDATE patient_no_formats SET is_selected = true WHERE code = 'PREFIX_SHORT_DATE';

-- View current setup:
-- SELECT code, name, pattern, sample_output, is_selected FROM patient_no_formats ORDER BY sort_order;
