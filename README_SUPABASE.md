# JobTrack Pro - Supabase version

## What changed
- SQLite removed for persistent app data
- Jobs and users stored in Supabase Postgres
- Resume PDFs stored in Supabase Storage bucket `resumes`
- Existing Flask login/session flow kept, so the UI changes are minimal

## 1. Create tables
Run `supabase_setup.sql` inside the Supabase SQL Editor.

## 2. Create storage bucket
In Supabase Dashboard -> Storage -> New bucket
- Name: `resumes`
- Public: OFF

## 3. Add environment variables
Create `.env` in the project root using `.env.example` as reference.

Required:
- `SECRET_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_BUCKET=resumes`

## 4. Install and run
```bash
pip install -r requirements.txt
python app.py
```

## 5. Test
- open `http://127.0.0.1:5000/health`
- then open `http://127.0.0.1:5000`
- demo login: `demo@example.com` / `demo123`

## Important
- Never put `SUPABASE_SERVICE_ROLE_KEY` in frontend JavaScript or HTML.
- Keep it only in your Flask backend / server environment.
- For Render deployment later, move these `.env` values into Render environment variables.
