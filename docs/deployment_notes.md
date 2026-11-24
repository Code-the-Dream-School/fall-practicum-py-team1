# Deployment notes and runtime configuration

**AWS region:** us-east-2 (Ohio)
*Last updated: 2026-11-24*

> Rule for this doc: list secret and variable **names** only. Never paste a value.

## 1. AWS resources created and what each does

- **Secrets Manager secret `production/supabase/database`**: holds the Supabase database connection details.
  Ticket: SCRUM-34 | Owner: Reading | Status: created (keys inside to confirm)

- **IAM user/role (limited) and Budgets alert**: day-to-day access without root, and a spend warning.
  Ticket: SCRUM-34 | Owner: Reading | Status: in progress (confirm)

- **Lambda handler and packaging**: the code the Lambda runs, with its libraries.
  Ticket: SCRUM-35 | Owner: Priya | Status: in progress

- **Ingest Lambda**: runs extract, load_raw and transform.
  Ticket: SCRUM-36 | Owner: Sid | Status: not deployed yet

- **EventBridge schedule and CloudWatch logs**: runs the Lambda on a schedule and keeps logs of each run.
  Ticket: SCRUM-40 | Owner: TBD (not assigned) | Status: not started

- **A basic CloudWatch alarm**: alerts the team when the Lambda reports errors.
  Ticket: SCRUM-39 | Owner: TBD (not assigned) | Status: not started

- **LLM enrichment as a second Lambda**: runs LLM enrichment separately.
  Ticket: SCRUM-38 | Owner: Natalia | Status: not started

- **GitHub Actions workflow**: deploys on merge to main.
  Ticket: not assigned | Owner: TBD | Status: not started

### Planned Lambda permissions (least privilege, confirm at deploy)

- Write logs to CloudWatch (the basic Lambda execution permission)
- `secretsmanager:GetSecretValue` on `production/supabase/database-*` only (the `-*` is needed because AWS adds a random suffix to the secret's ARN)
- Nothing else



## 2. Configuration and secrets

Each line: variable name, whether it's secret, where it lives, whether it can be committed.

- **OPENWEATHER_API_KEY**: secret | lives in: TBD (ask Reading) | commit: never
- **SUPABASE_URL**: not secret, but keep out of code | lives in: TBD | commit: never
- **SUPABASE_KEY**: secret | lives in: TBD | commit: never
- **SUPABASE_DB_HOST**: not secret, but keep out of code | lives in: likely `production/supabase/database` (confirm) | commit: never
- **SUPABASE_DB_PORT**: not secret | optional, defaults to 5432 | commit: yes
- **SUPABASE_DB_NAME**: not secret, but keep out of code | lives in: likely `production/supabase/database` (confirm) | commit: never
- **SUPABASE_DB_USER**: not secret, but keep out of code | lives in: likely `production/supabase/database` (confirm) | commit: never
- **SUPABASE_DB_PASSWORD**: secret | lives in: likely `production/supabase/database` (confirm) | commit: never

Not needed by the ingest Lambda: OPENAI_API_KEY and OPENAI_MODEL (enrichment Lambda only).

The extract stage also writes a run record to Supabase (`log_run.py`), so Supabase credentials are needed from the first stage, not only at load time.

**What is safe to commit:** variable names, and non-sensitive defaults such as the DB port. The `.env` file is git-ignored and is never committed.

## 3. How local and cloud runs differ

**Configuration**
- Local: a `.env` file, git-ignored, one per developer, loaded with python-dotenv
- Cloud: Lambda environment variables, filled from Secrets Manager

**How it starts**
- Local: `run_pipeline.py` in `services/pipeline` (calls `pipeline.cli`)
- Cloud: `lambda_handler`, by manual invoke now and EventBridge later

**Libraries**
- Local: the full `requirements.txt` (17 libraries)
- Cloud: `requirements_lambda.txt` only: requests, supabase, psycopg[binary], python-dotenv, pandas, numpy

**Logs**
- Local: terminal
- Cloud: CloudWatch

**Locations file**
- Local: read from disk
- Cloud: inside the package at `src/pipeline/extract/locations.json` (committed to git). The code finds the file relative to its own location (`Path(__file__).parent`), so no path setting is needed. When packaging, copy all of `src`, not just the `.py` files.
- Confirmed: `locations.py` builds the JSON path from its own file location, so it works the same locally and in Lambda.

### Packaging (draft, confirm with Priya)
Lambda runs Linux, and team members develop on Windows and Mac. A normal `pip install` on either would download libraries that won't run on Lambda, so install with the Linux options on both. Copy all of src.

- Run from `services/pipeline`.
- Windows: PowerShell. Mac: Terminal.
- Install command (the same on both; put it on one line):
  `pip install -r requirements_lambda.txt --target build --platform manylinux2014_x86_64 --python-version 3.13 --implementation cp --only-binary=:all: --upgrade`
- Match `--python-version` to the Lambda's runtime.
- The `--platform` value assumes the Lambda's architecture is x86_64. If the Lambda is set to arm64, use `manylinux2014_aarch64` instead. This applies to Apple Silicon Macs too, because the flag describes the Lambda's machine and not the developer's own computer.
- Libraries go into the git-ignored `build/` folder, and the code from `src` is added before zipping.
- Zip step differs by system:
  - Mac: `zip -r lambda.zip .` from inside `build`
  - Windows: avoid PowerShell's `Compress-Archive`, because it can create zips with backslash paths that break on Lambda. Use 7-Zip, or build the zip with a short Python script (to confirm with Priya).
- Lambda limits: about 50 MB zipped for a direct upload, 250 MB unzipped. Check the size after building.


### Lambda settings to decide at deploy

- Runtime: Python version (must match the packaging)
- Timeout: the default is 3 seconds, which is too short for an API call plus database writes
- Memory: TBD

## 4. Known issues and open questions

- The ticket says SSM Parameter Store, but the secrets were added to Secrets Manager. Confirm which one the team is using.
- Unknown what keys are inside `production/supabase/database`, and whether the OpenWeather key, Supabase URL and Supabase key are stored anywhere yet.
- The handler does not read Secrets Manager yet. Something must load the secrets into the environment variables at startup.
- `logging.basicConfig` may hide INFO logs in Lambda. Check after the first run.
- The README does not document how to run the pipeline locally.
- `.gitignore` has no `*.zip` rule, so a Lambda zip could be committed by accident. Keep it inside `build/`, which is ignored.
- `.env.*` is ignored, which would also hide a `.env.example` file unless an exception (`!.env.example`) is added.
- Packaging steps are written for Windows and Mac. Confirm the zip step with Priya and test it on both systems.