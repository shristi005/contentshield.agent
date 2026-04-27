import os
import json
import smtplib
from email.message import EmailMessage
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def call_ai(prompt, system_instruction):
    api_key = os.getenv("GROQ_API_KEY")
    
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 1024
        }
    )
    
    result = response.json()
    return result["choices"][0]["message"]["content"]

def generate_email_body(protected_asset, content_type, scan_results):
    """
    Uses Gemini to write a natural, professional email body to the rights holder
    summarizing the scan results as a smart human colleague.
    """
    if not os.getenv("GROQ_API_KEY"):
        return f"Error: GROQ_API_KEY not configured. Cannot generate email for {protected_asset}."

    # Format the scan results for the prompt
    results_json = json.dumps(scan_results, indent=2)

    system_instruction = (
        "You are ContentShield, an autonomous digital rights enforcement AI agent. "
        "You act as a smart, capable human colleague reporting back to a rights holder. "
        "Do not sound like a software dashboard or automated system report."
    )

    prompt = f"""
Write an email to the rights holder reporting the results of our latest content scan.

Asset: {protected_asset}
Content Type: {content_type}
Scan Results:
{results_json}

Follow these strict instructions:
1. Open with one punchy sentence about what was found.
2. State what was auto-handled (AUTO_TAKEDOWN, IGNORE, MONITOR) in exactly one sentence. No details.
3. Clearly list ONLY the cases needing human decision (action = ESCALATE). Provide exactly one-line context for each based on its escalation_reason.
4. End with a specific yes/no question for the rights holder regarding how to proceed with the escalated cases.
5. Sound like a smart human colleague, not a system report.
6. Stay strictly under 200 words total.
7. Ensure the summary sentences for each URL reflect the specific violation. For example: 'Found a full-length pirate stream of the movie' instead of 'potential for reuploads'.
"""

    try:
        text = call_ai(prompt, system_instruction)
        return text.strip()
    except Exception as e:
        return f"Failed to generate email body: {e}"


def send_email(to_address, subject, body):
    """
    Sends an email using Gmail SMTP SSL on port 465.
    Requires GMAIL_SENDER and GMAIL_APP_PASSWORD in .env.
    """
    sender = os.getenv("GMAIL_SENDER")
    password = os.getenv("GMAIL_APP_PASSWORD")

    if not sender or not password:
        print("Error: GMAIL_SENDER or GMAIL_APP_PASSWORD not found in environment.")
        return False

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to_address

    try:
        print(f"Attempting to send email to {to_address}...")
        # Use SMTP_SSL for port 465
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("Email sent successfully!")
        return True
    except smtplib.SMTPAuthenticationError:
        print("SMTP Authentication Error: Check your GMAIL_SENDER and GMAIL_APP_PASSWORD.")
        return False
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def log_to_console(protected_asset, scan_results, content_type="UNKNOWN"):
    """
    Prints a visually impressive, emoji-rich summary of the scan results to the terminal.
    Accepts content_type as an optional argument to display in the header.
    """
    print("\n" + "="*50)
    print("🛡️  ContentShield Agent — Scan Complete 🛡️")
    print("="*50)
    
    header_title = f"🎬 Asset: {protected_asset}"
    if content_type and content_type != "UNKNOWN":
        header_title += f" ({content_type.upper()})"
    print(header_title)
    print("-" * 50)

    action_counts = {
        "AUTO_TAKEDOWN": 0,
        "ESCALATE": 0,
        "MONITOR": 0,
        "IGNORE": 0
    }

    action_emojis = {
        "AUTO_TAKEDOWN": "🚨",
        "ESCALATE": "⚠️",
        "MONITOR": "👁️",
        "IGNORE": "✅"
    }

    if not scan_results:
        print("No suspect URLs found.")
    else:
        for res in scan_results:
            url = res.get("url", "Unknown URL")
            verdict = res.get("verdict", "UNCLEAR")
            action = str(res.get("action", "MONITOR")).upper()
            risk = res.get("risk_score", 0.0)
            
            emoji = action_emojis.get(action, "❓")
            print(f"{emoji} {url}")
            print(f"   Verdict: {verdict} | Risk Score: {risk:.1f}")
            
            if action in action_counts:
                action_counts[action] += 1

    print("-" * 50)
    print("📊 Action Summary:")
    print(f"🚨 Auto-Takedowns: {action_counts['AUTO_TAKEDOWN']}")
    print(f"⚠️ Escalated:     {action_counts['ESCALATE']}")
    print(f"👁️ Monitoring:    {action_counts['MONITOR']}")
    print(f"✅ Ignored:       {action_counts['IGNORE']}")
    print("="*50 + "\n")


def generate_takedown_notice(rights_owner, original_title, infringing_url, match_percentage, detection_time):
    """
    Calls Gemini to write a formal DMCA takedown notice for an infringing URL.
    """
    if not os.getenv("GROQ_API_KEY"):
        return "Error: GROQ_API_KEY not configured. Cannot generate DMCA notice."

    system_instruction = (
        "You are a specialized legal AI assistant. "
        "You generate formal DMCA (Digital Millennium Copyright Act) takedown notices."
    )

    prompt = f"""
Write a formal DMCA takedown notice.
Include the following details:
- Rights Owner: {rights_owner}
- Original Work: {original_title}
- Infringing URL: {infringing_url}
- Match Confidence: {match_percentage * 100:.1f}%
- Detection Timestamp: {detection_time}

Follow these strict rules:
1. Use formal legal language appropriate for a standard DMCA takedown notice under penalty of perjury.
2. Keep it strictly under 300 words.
3. Structure it clearly (e.g., recipient, declaration of good faith, digital signature).
"""

    try:
        text = call_ai(prompt, system_instruction)
        return text.strip()
    except Exception as e:
        return f"Failed to generate takedown notice: {e}"
