import os
import time
import random
import hashlib
import base64
import secrets
import requests
import uvicorn
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# ══════════════════════════════════════════════════════════
#  CONFIG & ENVIRONMENT (UPDATED & LOADED FIRST)
# ══════════════════════════════════════════════════════════
from dotenv import load_dotenv

# Force load the .env file at the very start
load_dotenv()

GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY",    "").strip()
GROQ_API_KEY      = os.getenv("GROQ_API_KEY",      "").strip()
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY",    "").strip()
HF_API_KEY        = os.getenv("HF_API_KEY",        "").strip()
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL", "").strip()

# ── SMTP CONFIGURATION ────────────────────────────────────
SMTP_HOST        = os.getenv("SMTP_HOST",        "smtp.gmail.com").strip()
try:
    SMTP_PORT    = int(os.getenv("SMTP_PORT",    "587").strip())
except ValueError:
    SMTP_PORT    = 587

SMTP_USER        = os.getenv("SMTP_USER",        "").strip()
SMTP_PASSWORD    = os.getenv("SMTP_PASSWORD",    "").strip()
SENDER_EMAIL     = os.getenv("SENDER_EMAIL",     SMTP_USER).strip()

# ── FRONTEND & CORS CONFIG ────────────────────────────────
FRONTEND_URL     = os.getenv("FRONTEND_URL",      "http://127.0.0.1:5500").strip().rstrip("/")
raw_origins      = os.getenv("ALLOWED_ORIGINS",   "*")
ALLOWED_ORIGINS  = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

# ── APP INITIALIZATION ────────────────────────────────────
app = FastAPI(title="NexusAI Backend", version="9.6")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── IN-MEMORY STORES (Reset on server restart) ────────────
otp_store:        dict = {}
reset_store:      dict = {}
link_reset_store: dict = {}
OTP_TTL = 300  # 5 minutes

# ── EXACT MODEL → PROVIDER MAPPING ───────────────────────
# All valid model IDs that the frontend can send
SUPPORTED_MODELS = {
    "gemini-2.5-flash": "Gemini",
    "qwen/qwen3.6-27b":  "Groq",
    "gpt-5.6-luna":            "OpenAI",
}

# ══════════════════════════════════════════════════════════
#  STARTUP PROVIDER STATUS LOG
# ══════════════════════════════════════════════════════════
@app.on_event("startup")
def log_provider_status():
    print("\n" + "═" * 50)
    print("  NexusAI v9.6 — Provider Configuration Status")
    print("═" * 50)
    print(f"  Gemini configured : {'✅ YES' if GEMINI_API_KEY  else '❌ NO  (set GEMINI_API_KEY in .env)'}")
    print(f"  Groq   configured : {'✅ YES' if GROQ_API_KEY    else '❌ NO  (set GROQ_API_KEY in .env)'}")
    print(f"  OpenAI configured : {'✅ YES' if OPENAI_API_KEY  else '❌ NO  (set OPENAI_API_KEY in .env)'}")
    print(f"  HF     configured : {'✅ YES' if HF_API_KEY      else '❌ NO  (set HF_API_KEY in .env)'}")
    print(f"  SMTP   configured : {'✅ YES' if SMTP_USER and SMTP_PASSWORD else '❌ NO'}")
    print("═" * 50 + "\n")

# ══════════════════════════════════════════════════════════
#  DATABASE UTILS (GOOGLE SHEETS INTEGRATION)
# ══════════════════════════════════════════════════════════
def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()

def sheet_request(data: dict) -> dict:
    if not GOOGLE_SCRIPT_URL:
        return {"success": False, "message": "Google Script URL not configured"}
    try:
        r = requests.post(GOOGLE_SCRIPT_URL, json=data, timeout=15)
        return r.json()
    except Exception as e:
        return {"success": False, "message": str(e)}

def sheet_find_user(email: str) -> dict:
    return sheet_request({"action": "login", "email": email.lower().strip()})

def sheet_save_user(name: str, email: str, pw_hash: str) -> dict:
    return sheet_request({
        "action": "saveUser", "name": name,
        "email": email.lower().strip(), "passwordHash": pw_hash, "status": "active"
    })

def sheet_update_password(email: str, pw_hash: str) -> dict:
    return sheet_request({
        "action": "updatePassword",
        "email": email.lower().strip(),
        "passwordHash": pw_hash
    })

# ══════════════════════════════════════════════════════════
#  SMTP EMAIL DISPATCHER
# ══════════════════════════════════════════════════════════
def send_email_via_smtp(to_email: str, subject: str, html_body: str) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        print("❌ SMTP Error: Credentials missing. Set SMTP_USER and SMTP_PASSWORD in .env")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"NexusAI <{SENDER_EMAIL or SMTP_USER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SENDER_EMAIL or SMTP_USER, to_email, msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SENDER_EMAIL or SMTP_USER, to_email, msg.as_string())
        print(f"📧 SMTP Sent → {to_email} [{subject}]")
        return True
    except Exception as e:
        print(f"❌ SMTP Exception: {e}")
        return False

# ══════════════════════════════════════════════════════════
#  PROFESSIONAL MODERN HTML EMAIL TEMPLATES
# ══════════════════════════════════════════════════════════
def _shell(subtitle: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>NexusAI</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7;padding:40px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:540px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,0.06);border:1px solid #eaedf1;">
          <tr>
            <td style="background:#0f172a;padding:32px 40px;text-align:center;">
              <div style="color:#ffffff;font-size:26px;font-weight:800;letter-spacing:-0.5px;line-height:1;">
                Nexus<span style="color:#6366f1;">AI</span>
              </div>
              <p style="margin:8px 0 0;color:#94a3b8;font-size:11px;font-weight:600;letter-spacing:2px;text-transform:uppercase;">{subtitle}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:36px 40px;">
              {body}
            </td>
          </tr>
          <tr>
            <td style="padding:0 40px;">
              <hr style="border:none;border-top:1px solid #f1f5f9;margin:0;"/>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 40px;text-align:center;">
              <p style="margin:0 0 6px;color:#94a3b8;font-size:12px;font-weight:500;">
                © NexusAI Inc. · Next-Gen Intelligence
              </p>
              <p style="margin:0;color:#cbd5e1;font-size:11px;">
                This is an automated system email. Please do not reply directly.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

def _otp_html(name: str, otp: str, purpose: str = "email verification", reset_link: str = "") -> str:
    link_block = ""
    if reset_link:
        link_block = f"""
        <tr>
          <td style="padding-top:8px;padding-bottom:28px;text-align:center;">
            <p style="margin:0 0 16px;color:#64748b;font-size:13px;">— or skip code and reset directly —</p>
            <a href="{reset_link}" target="_blank"
               style="display:inline-block;background:#6366f1;color:#ffffff;text-decoration:none;padding:14px 32px;border-radius:10px;font-size:14px;font-weight:600;">
              🔐 Reset Password Directly
            </a>
          </td>
        </tr>"""
    body = f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="padding-bottom:12px;"><p style="margin:0;color:#0f172a;font-size:20px;font-weight:700;">Hello {name} 👋</p></td></tr>
        <tr><td style="padding-bottom:24px;"><p style="margin:0;color:#475569;font-size:14px;line-height:1.6;">Use the single-use code below to complete your <strong style="color:#0f172a;">{purpose}</strong>:</p></td></tr>
        <tr>
          <td style="padding-bottom:24px;">
            <div style="background:#f8fafc;border:2px dashed #e2e8f0;border-radius:12px;padding:24px;text-align:center;">
              <p style="margin:0 0 8px;color:#94a3b8;font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">One-Time Code</p>
              <p style="margin:0;font-size:42px;font-weight:800;letter-spacing:12px;color:#0f172a;font-family:'Courier New',Courier,monospace;line-height:1.1;">{otp}</p>
            </div>
          </td>
        </tr>
        {link_block}
        <tr>
          <td style="padding-bottom:20px;">
            <div style="background:#fffbe0;border-left:4px solid #f59e0b;border-radius:6px;padding:12px 16px;">
              <p style="margin:0;color:#b45309;font-size:13px;line-height:1.5;">⏱️ Valid for <strong>5 minutes</strong>. Never share this code with anyone.</p>
            </div>
          </td>
        </tr>
        <tr><td><p style="margin:0;color:#94a3b8;font-size:12px;line-height:1.5;">If you did not initiate this request, safely ignore this email.</p></td></tr>
      </table>"""
    return _shell("Security Verification", body)

def _welcome_html(name: str) -> str:
    body = f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="padding-bottom:12px;"><p style="margin:0;color:#0f172a;font-size:22px;font-weight:700;">Welcome to NexusAI, {name}! 🎉</p></td></tr>
        <tr><td style="padding-bottom:28px;"><p style="margin:0;color:#475569;font-size:14px;line-height:1.7;">Your account is fully activated. You can now access language AI models and instant image generation directly in your workspace.</p></td></tr>
        <tr>
          <td style="text-align:center;padding-bottom:28px;">
            <a href="{FRONTEND_URL}" target="_blank" style="display:inline-block;background:#0f172a;color:#ffffff;text-decoration:none;padding:14px 36px;border-radius:10px;font-size:14px;font-weight:600;">Open Workspace →</a>
          </td>
        </tr>
      </table>"""
    return _shell("Account Activation", body)

# ══════════════════════════════════════════════════════════
#  AI PROVIDERS  —  exact model IDs, clear error messages
# ══════════════════════════════════════════════════════════
def call_gemini(messages: list, model: str = "gemini-2.5-flash") -> str:
    if not GEMINI_API_KEY:
        raise ValueError("Gemini API key not configured. Add GEMINI_API_KEY to .env")
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )
    try:
        r = requests.post(
            url,
            json={"contents": contents,
                  "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192}},
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except requests.exceptions.HTTPError as e:
        raise ValueError(f"Gemini API error: {e.response.status_code} — {e.response.text[:200]}")
    except requests.exceptions.Timeout:
        raise ValueError("Gemini API error: Request timed out (>90s)")


def call_groq(messages: list, model: str = "qwen/qwen3.6-27b") -> str:
    if not GROQ_API_KEY:
        raise ValueError("Groq API key not configured. Add GROQ_API_KEY to .env")
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": model, "messages": messages,
                  "temperature": 0.7, "max_tokens": 4096},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        raise ValueError(f"Groq API error: {e.response.status_code} — {e.response.text[:200]}")
    except requests.exceptions.Timeout:
        raise ValueError("Groq API error: Request timed out (>60s)")


def call_openai(messages: list, model: str = "gpt-5.6-luna") -> str:
    if not OPENAI_API_KEY:
        raise ValueError("OpenAI API key not configured. Add OPENAI_API_KEY to .env")
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": model, "messages": messages},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        raise ValueError(f"OpenAI API error: {e.response.status_code} — {e.response.text[:200]}")
    except requests.exceptions.Timeout:
        raise ValueError("OpenAI API error: Request timed out (>60s)")

# ══════════════════════════════════════════════════════════
#  PYDANTIC MODELS
# ══════════════════════════════════════════════════════════
class LoginRequest(BaseModel):
    email: str
    password: str

class SendOTPRequest(BaseModel):
    name: str
    email: str

class ResendOTPRequest(BaseModel):
    name: str
    email: str

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str

class SavePasswordRequest(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str

class ResetByTokenRequest(BaseModel):
    token: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    email: str
    current_password: str
    new_password: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    model: str = "gemini-2.5-flash"
    history: List[ChatMessage] = []
    email: Optional[str] = None

class ImageRequest(BaseModel):
    prompt: str

# ══════════════════════════════════════════════════════════
#  HEALTH ENDPOINT
# ══════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {
        "status": "NexusAI v9.6 Online ✅",
        "providers": {
            "gemini": bool(GEMINI_API_KEY),
            "groq":   bool(GROQ_API_KEY),
            "openai": bool(OPENAI_API_KEY),
        },
        "smtp_configured": bool(SMTP_USER and SMTP_PASSWORD),
    }

# ══════════════════════════════════════════════════════════
#  AUTH — LOGIN
# ══════════════════════════════════════════════════════════
@app.post("/login")
def api_login(data: LoginRequest):
    email = data.email.strip().lower()
    if not email or not data.password:
        return {"success": False, "message": "All fields required"}
    result = sheet_find_user(email)
    if not result.get("success"):
        return {"success": False, "message": "Email not registered"}
    if result.get("passwordHash", "") != hash_password(data.password):
        return {"success": False, "message": "Incorrect password"}
    return {"success": True, "name": result.get("name", ""), "email": email}

# ══════════════════════════════════════════════════════════
#  AUTH — REGISTRATION (OTP FLOW)
# ══════════════════════════════════════════════════════════
@app.post("/send-otp")
def api_send_otp(data: SendOTPRequest, bg: BackgroundTasks):
    name, email = data.name.strip(), data.email.strip().lower()
    if not name or not email:
        return {"success": False, "message": "All fields required"}
    if sheet_find_user(email).get("success"):
        return {"success": False, "message": "Email already registered"}
    otp = str(random.randint(100000, 999999))
    otp_store[email] = {
        "otp": otp, "name": name,
        "expires_at": time.time() + OTP_TTL, "verified": False
    }
    bg.add_task(send_email_via_smtp, email, "Your NexusAI Verification Code",
                _otp_html(name, otp, "email verification"))
    return {"success": True, "message": "OTP sent"}

@app.post("/resend-otp")
def api_resend_otp(data: ResendOTPRequest, bg: BackgroundTasks):
    email = data.email.strip().lower()
    pending = otp_store.get(email)
    if not pending:
        return {"success": False, "message": "No pending registration found"}
    otp = str(random.randint(100000, 999999))
    pending.update({"otp": otp, "expires_at": time.time() + OTP_TTL})
    bg.add_task(send_email_via_smtp, email, "Your NexusAI Verification Code",
                _otp_html(pending["name"], otp, "email verification"))
    return {"success": True, "message": "OTP resent"}

@app.post("/verify-otp")
def api_verify_otp(data: VerifyOTPRequest):
    email = data.email.strip().lower()
    pending = otp_store.get(email)
    if not pending or time.time() > pending["expires_at"]:
        return {"success": False, "message": "OTP expired or not found"}
    if data.otp.strip() != pending["otp"]:
        return {"success": False, "message": "Incorrect OTP"}
    otp_store[email]["verified"] = True
    return {"success": True, "message": "Verified"}

@app.post("/save-password")
def api_save_password(data: SavePasswordRequest, bg: BackgroundTasks):
    email = data.email.strip().lower()
    pending = otp_store.get(email)
    if not pending or not pending.get("verified"):
        return {"success": False, "message": "Unauthorized — complete OTP verification first"}
    if not data.password or len(data.password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters"}
    res = sheet_save_user(pending["name"], email, hash_password(data.password))
    if res.get("success"):
        del otp_store[email]
        bg.add_task(send_email_via_smtp, email, "Welcome to NexusAI! 🎉",
                    _welcome_html(pending["name"]))
        return {"success": True, "name": pending["name"], "email": email}
    return {"success": False, "message": res.get("message", "Database error")}

# ══════════════════════════════════════════════════════════
#  AUTH — FORGOT & RESET PASSWORD
# ══════════════════════════════════════════════════════════
@app.post("/forgot-password")
def api_forgot_password(data: ForgotPasswordRequest, bg: BackgroundTasks):
    email = data.email.strip().lower()
    if not email:
        return {"success": False, "message": "Email required"}
    result = sheet_find_user(email)
    if result.get("success"):
        name = result.get("name", "User")
        otp = str(random.randint(100000, 999999))
        reset_store[email] = {
            "otp": otp, "name": name,
            "expires_at": time.time() + OTP_TTL, "verified": False
        }
        token = secrets.token_urlsafe(32)
        link_reset_store[token] = {
            "email": email, "name": name,
            "expires_at": time.time() + OTP_TTL
        }
        reset_link = f"{FRONTEND_URL}?reset_token={token}"
        bg.add_task(send_email_via_smtp, email, "Reset Your NexusAI Password",
                    _otp_html(name, otp, "password reset", reset_link))
    return {"success": True, "message": "If that email is registered, a reset email has been sent"}

@app.post("/verify-reset-otp")
def api_verify_reset_otp(data: VerifyOTPRequest):
    email = data.email.strip().lower()
    pending = reset_store.get(email)
    if not pending or time.time() > pending["expires_at"]:
        return {"success": False, "message": "OTP expired or not found. Request a new one."}
    if data.otp.strip() != pending["otp"]:
        return {"success": False, "message": "Incorrect OTP"}
    reset_store[email]["verified"] = True
    return {"success": True, "message": "OTP verified"}

@app.post("/reset-password")
def api_reset_password(data: ResetPasswordRequest):
    email = data.email.strip().lower()
    pending = reset_store.get(email)
    if not pending or not pending.get("verified"):
        return {"success": False, "message": "Unauthorized — complete OTP verification first"}
    if not data.new_password or len(data.new_password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters"}
    res = sheet_update_password(email, hash_password(data.new_password))
    if res.get("success"):
        del reset_store[email]
        return {"success": True, "message": "Password updated successfully"}
    return {"success": False, "message": res.get("message", "Failed to update password")}

@app.post("/reset-by-token")
def api_reset_by_token(data: ResetByTokenRequest):
    token = data.token.strip()
    pending = link_reset_store.get(token)
    if not pending:
        return {"success": False, "message": "Invalid reset link. Please request a new one."}
    if time.time() > pending["expires_at"]:
        del link_reset_store[token]
        return {"success": False, "message": "Reset link expired. Please request a new one."}
    if not data.new_password or len(data.new_password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters"}
    res = sheet_update_password(pending["email"], hash_password(data.new_password))
    if res.get("success"):
        del link_reset_store[token]
        return {"success": True, "message": "Password updated successfully", "email": pending["email"]}
    return {"success": False, "message": res.get("message", "Failed to update password")}

@app.post("/change-password")
def api_change_password(data: ChangePasswordRequest):
    email = data.email.strip().lower()
    if not email or not data.current_password or not data.new_password:
        return {"success": False, "message": "All fields required"}
    if len(data.new_password) < 6:
        return {"success": False, "message": "New password must be at least 6 characters"}
    result = sheet_find_user(email)
    if not result.get("success"):
        return {"success": False, "message": "User not found"}
    if result.get("passwordHash", "") != hash_password(data.current_password):
        return {"success": False, "message": "Current password is incorrect"}
    if hash_password(data.current_password) == hash_password(data.new_password):
        return {"success": False, "message": "New password must differ from current password"}
    res = sheet_update_password(email, hash_password(data.new_password))
    if res.get("success"):
        return {"success": True, "message": "Password changed successfully"}
    return {"success": False, "message": res.get("message", "Failed to update password")}

# ══════════════════════════════════════════════════════════
#  CHAT ENDPOINT — EXACT MODEL ROUTING (no fuzzy matching)
# ══════════════════════════════════════════════════════════
@app.post("/api/chat")
def api_chat(data: ChatRequest):
    model = data.model.strip()
    history = [{"role": m.role, "content": m.content} for m in data.history]
    messages = [*history, {"role": "user", "content": data.message}]

    # ── Route by EXACT model ID ───────────────────────────
    if model == "gemini-2.5-flash":
        provider = "Gemini"
        print(f"AI REQUEST → provider=Gemini  model={model}")
        call_fn = lambda: call_gemini(messages, model)

    elif model == "qwen/qwen3.6-27b":
        provider = "Groq"
        print(f"AI REQUEST → provider=Groq    model={model}")
        call_fn = lambda: call_groq(messages, model)

    elif model == "gpt-5.6-luna":
        provider = "OpenAI"
        print(f"AI REQUEST → provider=OpenAI  model={model}")
        call_fn = lambda: call_openai(messages, model)

    else:
        print(f"AI REQUEST → UNKNOWN model: {model!r}")
        return {
            "response": "",
            "error": (
                f"Unknown model '{model}'. "
                f"Supported models: {', '.join(SUPPORTED_MODELS.keys())}"
            )
        }

    # ── Call the provider ─────────────────────────────────
    try:
        response = call_fn()
        print(f"AI RESPONSE ✅ provider={provider} chars={len(response)}")
        return {"response": response, "error": False}

    except ValueError as e:
        # Our own descriptive errors (key missing, HTTP error, timeout)
        print(f"AI ERROR ❌ provider={provider}: {e}")
        return {"response": "", "error": str(e)}

    except Exception as e:
        print(f"AI ERROR ❌ provider={provider} unexpected: {e}")
        return {"response": "", "error": f"{provider} error: {e}"}

# ══════════════════════════════════════════════════════════
#  IMAGE GENERATION
# ══════════════════════════════════════════════════════════
HF_MODEL_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"

@app.post("/generate-image")
def api_generate_image(data: ImageRequest):
    if not HF_API_KEY:
        return {"success": False, "message": "HF_API_KEY not configured. Add it to your .env file."}
    if not data.prompt or not data.prompt.strip():
        return {"success": False, "message": "Prompt cannot be empty"}
    try:
        r = requests.post(
            HF_MODEL_URL,
            headers={"Authorization": f"Bearer {HF_API_KEY}",
                     "Content-Type": "application/json"},
            json={"inputs": data.prompt.strip()},
            timeout=120,
        )
        if r.status_code == 200:
            img_b64 = base64.b64encode(r.content).decode("utf-8")
            return {"success": True, "image": f"data:image/png;base64,{img_b64}"}
        if r.status_code == 503:
            return {"success": False, "message": "Model is warming up on HuggingFace. Wait 20–30 s and try again."}
        try:
            err_detail = r.json().get("error", r.text)
        except Exception:
            err_detail = r.text
        return {"success": False, "message": f"HuggingFace error {r.status_code}: {err_detail}"}
    except requests.exceptions.Timeout:
        return {"success": False, "message": "Request timed out (>120 s). Try a simpler prompt."}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ══════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
