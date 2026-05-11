"""
Billing Lambda — Stripe subscription management.

Routes (all require JWT auth except webhook):
  POST /billing/checkout  → create Stripe Checkout session, return {url}
  POST /billing/portal    → create Stripe Customer Portal session, return {url}
  POST /billing/webhook   → Stripe webhook (no JWT, verified by signature)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request

import boto3

from ddb_utils import get_user, get_user_by_stripe_id, upsert_user
from response import err, ok

ddb = boto3.resource("dynamodb")
ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))

USERS_TABLE = os.environ["USERS_TABLE"]
APP_URL     = os.environ.get("APP_URL", "https://rosetta-translate.com")

# SSM-cached secrets (loaded once per Lambda container)
_STRIPE_SECRET_KEY     = None
_STRIPE_WEBHOOK_SECRET = None
_STRIPE_PRO_PRICE_ID   = None
_SSM_PREFIX            = os.environ.get("SSM_PREFIX", "/rosetta/prod")


def _ssm(name: str) -> str:
    return ssm.get_parameter(Name=f"{_SSM_PREFIX}/{name}", WithDecryption=True)["Parameter"]["Value"]


def stripe_secret() -> str:
    global _STRIPE_SECRET_KEY
    if not _STRIPE_SECRET_KEY:
        _STRIPE_SECRET_KEY = _ssm("stripe_secret_key")
    return _STRIPE_SECRET_KEY


def webhook_secret() -> str:
    global _STRIPE_WEBHOOK_SECRET
    if not _STRIPE_WEBHOOK_SECRET:
        _STRIPE_WEBHOOK_SECRET = _ssm("stripe_webhook_secret")
    return _STRIPE_WEBHOOK_SECRET


def pro_price_id() -> str:
    global _STRIPE_PRO_PRICE_ID
    if not _STRIPE_PRO_PRICE_ID:
        _STRIPE_PRO_PRICE_ID = _ssm("stripe_pro_price_id")
    return _STRIPE_PRO_PRICE_ID


# ── Stripe API helper (no SDK — avoid dependency) ─────────────────────────────

def stripe_post(path: str, data: dict) -> dict:
    """Make a POST request to the Stripe API."""
    import urllib.parse
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        f"https://api.stripe.com/v1/{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {stripe_secret()}",
            "Content-Type":  "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def stripe_get(path: str) -> dict:
    """Make a GET request to the Stripe API."""
    req = urllib.request.Request(
        f"https://api.stripe.com/v1/{path}",
        headers={"Authorization": f"Bearer {stripe_secret()}"},
        method="GET",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


# ── Webhook signature verification ───────────────────────────────────────────

def verify_stripe_signature(payload: bytes, sig_header: str) -> bool:
    """Verify Stripe webhook signature using HMAC-SHA256."""
    try:
        parts = {k: v for k, v in (p.split("=", 1) for p in sig_header.split(","))}
        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")
        # Reject events older than 5 minutes
        if abs(time.time() - int(timestamp)) > 300:
            return False
        signed = f"{timestamp}.".encode() + payload
        expected = hmac.new(webhook_secret().encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


# ── Route handlers ────────────────────────────────────────────────────────────

def handle_checkout(user_id: str, user_email: str | None) -> dict:
    """Create a Stripe Checkout session for the Pro plan."""
    user = get_user(ddb, USERS_TABLE, user_id)

    # Reuse existing Stripe customer or create new one
    customer_id = user.get("stripeCustomerId")
    if not customer_id:
        customer_data = {"metadata[userId]": user_id}
        if user_email:
            customer_data["email"] = user_email
        customer = stripe_post("customers", customer_data)
        customer_id = customer["id"]
        upsert_user(ddb, USERS_TABLE, user_id, stripeCustomerId=customer_id)

    session = stripe_post("checkout/sessions", {
        "customer":                     customer_id,
        "mode":                         "subscription",
        "line_items[0][price]":         pro_price_id(),
        "line_items[0][quantity]":      "1",
        "success_url":                  f"{APP_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url":                   f"{APP_URL}/dashboard",
        "allow_promotion_codes":        "true",
        "billing_address_collection":   "auto",
        "metadata[userId]":             user_id,
    })
    return ok(200, {"url": session["url"]})


def handle_portal(user_id: str) -> dict:
    """Create a Stripe Customer Portal session (manage/cancel subscription)."""
    user = get_user(ddb, USERS_TABLE, user_id)
    customer_id = user.get("stripeCustomerId")
    if not customer_id:
        return err(400, "No active subscription found")

    session = stripe_post("billing_portal/sessions", {
        "customer":   customer_id,
        "return_url": f"{APP_URL}/dashboard",
    })
    return ok(200, {"url": session["url"]})


def handle_webhook(event: dict) -> dict:
    """Process Stripe webhook events to keep subscription state in sync."""
    body_bytes = (event.get("body") or "").encode()
    if event.get("isBase64Encoded"):
        import base64
        body_bytes = base64.b64decode(event["body"])

    sig = (event.get("headers") or {}).get("stripe-signature", "")
    if not verify_stripe_signature(body_bytes, sig):
        return err(400, "Invalid signature")

    payload  = json.loads(body_bytes)
    evt_type = payload.get("type", "")
    data_obj = payload.get("data", {}).get("object", {})

    if evt_type in ("customer.subscription.created", "customer.subscription.updated"):
        _sync_subscription(data_obj)
    elif evt_type == "customer.subscription.deleted":
        _cancel_subscription(data_obj)
    elif evt_type == "invoice.payment_failed":
        _handle_payment_failed(data_obj)

    return ok(200, {"received": True})


def _sync_subscription(sub: dict) -> None:
    """Update user tier based on active subscription."""
    customer_id = sub.get("customer")
    status      = sub.get("status")          # active, trialing, past_due, etc.
    user        = get_user_by_stripe_id(ddb, USERS_TABLE, customer_id)
    if not user:
        return

    is_active = status in ("active", "trialing")
    upsert_user(
        ddb, USERS_TABLE, user["userId"],
        tier="pro" if is_active else "free",
        quotaLimit=100 if is_active else 5,
        subscriptionStatus=status,
        subscriptionId=sub.get("id"),
    )


def _cancel_subscription(sub: dict) -> None:
    """Downgrade user to free tier on cancellation."""
    customer_id = sub.get("customer")
    user = get_user_by_stripe_id(ddb, USERS_TABLE, customer_id)
    if not user:
        return
    upsert_user(
        ddb, USERS_TABLE, user["userId"],
        tier="free",
        quotaLimit=5,
        subscriptionStatus="canceled",
    )


def _handle_payment_failed(invoice: dict) -> None:
    """Mark subscription as past_due on payment failure (Stripe retries)."""
    customer_id = invoice.get("customer")
    user = get_user_by_stripe_id(ddb, USERS_TABLE, customer_id)
    if not user:
        return
    upsert_user(ddb, USERS_TABLE, user["userId"], subscriptionStatus="past_due")


# ── Main handler ──────────────────────────────────────────────────────────────

def handler(event, context):
    route = event.get("routeKey", "")
    method, path = route.split(" ", 1) if " " in route else ("", route)

    if path == "/billing/webhook":
        return handle_webhook(event)

    # All other routes require JWT auth
    claims  = event["requestContext"]["authorizer"]["jwt"]["claims"]
    user_id = claims["sub"]
    email   = claims.get("email")

    if method == "POST" and path == "/billing/checkout":
        return handle_checkout(user_id, email)
    if method == "POST" and path == "/billing/portal":
        return handle_portal(user_id)

    return err(404, "Not found")
