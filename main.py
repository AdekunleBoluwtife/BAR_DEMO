"""
Book A Ride WhatsApp Bot: FastAPI + Twilio WhatsApp API (Ikere-Ekiti pilot)

Flow:
  1. "ride" -> bot lists the 12 pickup points, asks for pickup
  2. pickup -> asks for drop-off
  3. drop-off -> shows Solo and Share fares, rider replies 1 (Solo) or 2 (Share)
  4. choice confirms the ride -> driver matched, live status updates are pushed
     (arriving -> arrived -> in transit -> completed)
  5. "status" anytime, "cancel" to cancel
"""
import asyncio
import os

from fastapi import FastAPI, HTTPException, Request, Response
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from drivers import find_available_driver
from locations import estimate_fare, list_locations, match_location, pickup_name, RATE_PER_KM
from state import RideState, get_session

app = FastAPI(title="Book A Ride WhatsApp Bot")

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
# Set VALIDATE_TWILIO=1 and PUBLIC_WEBHOOK_URL=https://<your-app>.onrender.com/webhook in production
VALIDATE_TWILIO = os.environ.get("VALIDATE_TWILIO", "0") == "1"
PUBLIC_WEBHOOK_URL = os.environ.get("PUBLIC_WEBHOOK_URL", "")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None
validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None


def naira(n: float) -> str:
    return f"₦{n:,.0f}"


def send_whatsapp(to: str, body: str) -> None:
    """Proactive WhatsApp message (background status updates)."""
    if not twilio_client:
        print(f"[DRY RUN] Would send to {to}: {body}")
        return
    twilio_client.messages.create(from_=TWILIO_WHATSAPP_NUMBER, to=to, body=body)


async def run_ride_lifecycle(phone: str) -> None:
    """
    Simulated driver progress. Replace the sleeps with real driver-app events.
    Each step re-checks state AND ride_id so a cancelled or rebooked ride is never touched.
    """
    session = get_session(phone)
    rid = session.ride_id

    def alive(expected: RideState) -> bool:
        return session.ride_id == rid and session.state == expected

    await asyncio.sleep(3)
    if not alive(RideState.MATCHED):
        return
    session.state = RideState.DRIVER_ARRIVING
    d = session.driver
    send_whatsapp(phone, f"🚗 {d['name']} is on the way in a {d['vehicle']} ({d['plate']}). ETA ~4 mins.")

    await asyncio.sleep(8)
    if not alive(RideState.DRIVER_ARRIVING):
        return
    session.state = RideState.DRIVER_ARRIVED
    send_whatsapp(phone, f"📍 {d['name']} has arrived at {pickup_name(session.pickup)}. Please head out!")

    await asyncio.sleep(6)
    if not alive(RideState.DRIVER_ARRIVED):
        return
    session.state = RideState.IN_TRANSIT
    send_whatsapp(phone, f"🛣️ Ride started, heading to {pickup_name(session.dropoff)}.")

    await asyncio.sleep(10)
    if not alive(RideState.IN_TRANSIT):
        return
    fare = session.fare
    session.state = RideState.COMPLETED
    send_whatsapp(
        phone,
        f"✅ Trip complete! Fare: {naira(fare)}. Thanks for riding with Book A Ride 🎓\n\n"
        f"Send *ride* anytime to book another trip.",
    )
    session.reset()


def handle_message(phone: str, text: str) -> str:
    session = get_session(phone)
    t = text.strip().lower()

    # Global commands
    if t in ("cancel", "stop"):
        if session.state == RideState.IDLE:
            return "You don't have an active request. Send *ride* to book one."
        session.reset()
        return "❌ Your ride request has been cancelled. Send *ride* to start a new one."

    if t == "status":
        return status_message(session)

    if t in ("hi", "hello", "menu", "help"):
        return (
            "👋 Welcome to *Book A Ride*, smarter rides for Ikere-Ekiti!\n\n"
            "Send *ride* to book a trip.\n"
            "Send *status* to check an active ride.\n"
            "Send *cancel* to cancel a request."
        )

    if session.state == RideState.IDLE:
        if t in ("ride", "book", "book a ride"):
            session.state = RideState.AWAITING_PICKUP
            return (
                "🚕 Let's get you a ride! Where are you being picked up from?\n"
                "Reply with a number or name.\n\n" + list_locations()
            )
        return "Send *ride* to book a trip, or *help* to see what I can do."

    if session.state == RideState.AWAITING_PICKUP:
        code = match_location(t)
        if not code:
            return "I couldn't find that pickup point. Reply with a number or name:\n\n" + list_locations()
        session.pickup = code
        session.state = RideState.AWAITING_DROPOFF
        return f"Got it, pickup at *{pickup_name(code)}* ({code}). Where are you headed?\n\n" + list_locations()

    if session.state == RideState.AWAITING_DROPOFF:
        code = match_location(t)
        if not code:
            return "I couldn't find that drop-off. Reply with a number or name:\n\n" + list_locations()
        if code == session.pickup:
            return "Drop-off can't be the same as pickup. Where are you headed?"
        session.dropoff = code
        km, fares = estimate_fare(session.pickup, code)
        session.distance_km, session.fares = km, fares
        session.state = RideState.AWAITING_CONFIRM
        return (
            f"📋 *Ride Summary*\n"
            f"From: {pickup_name(session.pickup)} ({session.pickup})\n"
            f"To: {pickup_name(code)} ({code})\n"
            f"Distance: ~{km} km at {naira(RATE_PER_KM)}/km\n\n"
            f"*1. Solo*: whole car, {naira(fares['solo'])}\n"
            f"*2. Share*: up to 3 students split it, ~{naira(fares['share'])} each\n\n"
            f"Reply *1* or *2* to confirm, or *cancel* to abort."
        )

    if session.state == RideState.AWAITING_CONFIRM:
        choice = {"1": "solo", "solo": "solo", "2": "share", "share": "share"}.get(t)
        if not choice:
            return "Reply *1* for Solo or *2* for Share, or *cancel* to abort."
        session.mode = choice
        session.fare = session.fares[choice]
        driver = find_available_driver()
        session.driver = driver
        session.state = RideState.MATCHED
        asyncio.create_task(run_ride_lifecycle(phone))
        label = "Solo" if choice == "solo" else "Share (fare shown assumes a full car of 3)"
        return (
            f"✅ {label} ride confirmed, {naira(session.fare)}! Driver *{driver['name']}* "
            f"({driver['vehicle']}, plate {driver['plate']}) has been assigned.\n\n"
            f"You'll get live updates here. Send *status* anytime."
        )

    return status_message(session)


def status_message(session) -> str:
    d = session.driver
    messages = {
        RideState.IDLE: "You have no active ride. Send *ride* to book one.",
        RideState.AWAITING_PICKUP: "Waiting for your pickup point.",
        RideState.AWAITING_DROPOFF: "Waiting for your drop-off point.",
        RideState.AWAITING_CONFIRM: "Waiting for you to choose Solo (*1*) or Share (*2*).",
        RideState.MATCHED: f"Driver {d['name']} assigned, about to head your way." if d else "",
        RideState.DRIVER_ARRIVING: f"🚗 {d['name']} is on the way to {pickup_name(session.pickup)}." if d else "",
        RideState.DRIVER_ARRIVED: f"📍 {d['name']} has arrived. Please head out!" if d else "",
        RideState.IN_TRANSIT: f"🛣️ On the way to {pickup_name(session.dropoff)}." if session.dropoff else "",
        RideState.COMPLETED: "Your last ride is complete. Send *ride* to book another.",
    }
    return messages.get(session.state) or "Send *ride* to book a trip."


@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    """Twilio posts form data on every inbound WhatsApp message."""
    form = await request.form()
    if VALIDATE_TWILIO:
        sig = request.headers.get("X-Twilio-Signature", "")
        if not validator or not validator.validate(PUBLIC_WEBHOOK_URL, dict(form), sig):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    sender, body = form.get("From", ""), form.get("Body", "")
    if not sender:
        raise HTTPException(status_code=400, detail="Missing From")

    resp = MessagingResponse()          # escapes XML safely
    resp.message(handle_message(sender, body))
    return Response(content=str(resp), media_type="application/xml")


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "book-a-ride-whatsapp-bot"}
