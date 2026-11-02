-- =====================================================================
--  Cloud-Based Feedback Collection System — database schema
--  Target: Supabase PostgreSQL (works on any PostgreSQL 13+)
--
--  How to run:
--    Option A: Supabase Dashboard → SQL Editor → paste this file → Run
--    Option B: from backend/:  python manage.py init-db
--
--  The script is idempotent: running it twice does not break anything
--  or delete existing data.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. students — accounts for students who want to see their history
--    (submitting feedback does NOT require an account)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    id             SERIAL PRIMARY KEY,
    student_id     VARCHAR(20)  NOT NULL UNIQUE,      -- college roll / enrolment no.
    full_name      VARCHAR(100) NOT NULL,
    department     VARCHAR(80)  NOT NULL,
    password_hash  TEXT         NOT NULL,             -- scrypt hash, never plain text
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT students_student_id_format CHECK (student_id ~ '^[A-Z0-9/_-]{3,20}$'),
    CONSTRAINT students_name_length       CHECK (char_length(full_name) BETWEEN 2 AND 100)
);

-- ---------------------------------------------------------------------
-- 2. feedback — one row per submitted feedback form
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id                  SERIAL PRIMARY KEY,
    student_name        VARCHAR(100) NOT NULL,
    student_id          VARCHAR(20)  NOT NULL,
    department          VARCHAR(80)  NOT NULL,
    semester            SMALLINT     NOT NULL,
    category            VARCHAR(40)  NOT NULL,
    rating              SMALLINT     NOT NULL,
    description         TEXT         NOT NULL,
    suggestions         TEXT,
    -- set only when the student was logged in while submitting;
    -- used for the "My Submissions" history page
    student_account_id  INTEGER REFERENCES students(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT feedback_rating_range      CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT feedback_semester_range    CHECK (semester BETWEEN 1 AND 8),
    CONSTRAINT feedback_category_allowed  CHECK (category IN (
        'Faculty and Teaching',
        'Infrastructure',
        'Library',
        'Canteen',
        'Events and Workshops',
        'Overall College Experience'
    )),
    CONSTRAINT feedback_name_length        CHECK (char_length(student_name) BETWEEN 2 AND 100),
    CONSTRAINT feedback_description_length CHECK (char_length(description) BETWEEN 10 AND 2000),
    CONSTRAINT feedback_suggestions_length CHECK (suggestions IS NULL OR char_length(suggestions) <= 1000)
);

-- Indexes for the queries the admin dashboard runs most often
CREATE INDEX IF NOT EXISTS idx_feedback_created_at  ON feedback (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_category    ON feedback (category);
CREATE INDEX IF NOT EXISTS idx_feedback_rating      ON feedback (rating);
CREATE INDEX IF NOT EXISTS idx_feedback_student_id  ON feedback (student_id);
CREATE INDEX IF NOT EXISTS idx_feedback_account     ON feedback (student_account_id);

-- ---------------------------------------------------------------------
-- 3. admins — administrator accounts
--    No default admin is inserted here on purpose (a password in a SQL
--    file would end up on GitHub). Create one with:
--        python manage.py create-admin
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admins (
    id             SERIAL PRIMARY KEY,
    username       VARCHAR(50) NOT NULL UNIQUE,
    password_hash  TEXT        NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT admins_username_format CHECK (username ~ '^[A-Za-z0-9_.-]{3,50}$')
);

-- ---------------------------------------------------------------------
-- 4. Lock the tables away from Supabase's public Data API
--
--    Supabase automatically exposes every table in the "public" schema
--    through a REST API that anyone holding the project's anon key can
--    call. Our app never uses that API — only the Flask backend talks to
--    the database, using the private connection string. Enabling Row
--    Level Security with NO policies means the anon/authenticated roles
--    can read nothing. The backend connects as the table owner
--    ("postgres"), which is not affected by RLS.
-- ---------------------------------------------------------------------
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE admins   ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON students, feedback, admins FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'REVOKE ALL ON students, feedback, admins FROM authenticated';
    END IF;
END
$$;
