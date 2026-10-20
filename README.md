# Book A Ride WhatsApp Bot (Ikere-Ekiti pilot)

Files: `main.py` (webhook + conversation flow), `locations.py` (12 BKR pickup points, zones, fares),
`drivers.py` (mock driver pool), `state.py` (in-memory sessions), `requirements.txt`.

## Run locally
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
    ngrok http 8000        # paste https://<id>.ngrok.app/webhook into Twilio

Without Twilio credentials the bot runs in DRY RUN mode (proactive messages print to the console).

## Deploy on Render
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Env vars: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER` (default is the sandbox number)
- Twilio Console > Messaging > WhatsApp sandbox > "When a message comes in": `https://<your-app>.onrender.com/webhook` (POST)
- Optional hardening: `VALIDATE_TWILIO=1` and `PUBLIC_WEBHOOK_URL=https://<your-app>.onrender.com/webhook`

## Before real users
- Replace schematic x/y in `locations.py` with GPS and a real distance calculation.
- Sessions are in memory and reset on restart; move to Redis/Postgres.
- Share mode charges the per-student price assuming 3 riders; real rider matching is not built yet.
- Replace the lifecycle sleeps in `run_ride_lifecycle` with real driver-app events.
