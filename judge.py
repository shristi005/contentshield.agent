import os
import time
import json
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

def judge_violation(original_title, rights_owner, content_type,
                    suspect_url, suspect_title, snippet, match_percentage, platform_risk):
    """
    Uses the Gemini API to make a legal enforcement decision about a potential 
    copyright violation.
    """
    # Default response in case of API failure or parsing errors
    default_response = {
        "verdict": "UNCLEAR",
        "confidence": 0,
        "reasoning": "System encountered an error evaluating the content.",
        "severity": "LOW",
        "action": "ESCALATE",
        "escalation_reason": "API error or missing response.",
        "revenue_risk": "LOW"
    }

    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY not found in environment.")
        return default_response

    system_instruction = (
        "You are ContentShield, an autonomous digital rights enforcement AI. "
        "You protect any type of digital media — sports, film, music, news. "
        "You always respond in valid JSON only. No preamble. No explanation outside JSON."
    )

    prompt = f"""
Please evaluate the following potential copyright violation.

Original Content:
- Title: {original_title}
- Rights Owner: {rights_owner}
- Content Type: {content_type}

Suspect Content:
- URL: {suspect_url}
- Title: {suspect_title}
- Snippet: {snippet}

Detection Metrics:
- Fingerprint Match Percentage: {match_percentage * 100:.1f}%
- Platform Risk Score: {platform_risk} (Scale 0.0 to 1.0)

Consider these rules:
- Match below 60% = likely not same content
- News clips under 30 seconds may be fair use
- Verified partners may be licensed
- Reaction/commentary videos are gray area
- Full reuploads are always INFRINGING

Respond ONLY with a JSON object containing exactly these fields:
{{
  "verdict": "INFRINGING" or "FAIR_USE" or "LICENSED_LIKELY" or "UNCLEAR" or "NOT_INFRINGING",
  "confidence": <integer from 0-100>,
  "reasoning": "<one sentence explanation>",
  "severity": "CRITICAL" or "HIGH" or "MEDIUM" or "LOW",
  "action": "AUTO_TAKEDOWN" or "ESCALATE" or "MONITOR" or "IGNORE",
  "escalation_reason": "<why human is needed if applicable or empty string>",
  "revenue_risk": "LOW" or "MEDIUM" or "HIGH"
}}
"""

    try:
        # Sleep for 1 second to avoid rate limiting
        time.sleep(1)
        
        text = call_ai(prompt, system_instruction).strip()
        
        # Safely clean up markdown blocks if the model somehow returns them despite the mime_type
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
            
        result = json.loads(text.strip())
        
        # Validate that essential keys are present
        expected_keys = ["verdict", "confidence", "reasoning", "severity", "action", "escalation_reason", "revenue_risk"]
        for key in expected_keys:
            if key not in result:
                raise ValueError(f"Missing expected key '{key}' in JSON response")
                
        return result
        
    except json.JSONDecodeError as e:
        print(f"Error parsing Gemini response as JSON: {e}")
        return default_response
    except Exception as e:
        print(f"Error during Groq API call or processing: {e}")
        return default_response

def calculate_risk_score(match_pct, confidence, platform_risk):
    """
    Calculates a single risk score from 0 to 100 based on detection metrics.
    Formula: (match_pct * 40) + (confidence * 0.4) + (platform_risk * 20)
    Caps the maximum risk score at 100.
    """
    try:
        # match_pct could arrive as a 0.0-1.0 float or a 0-100 percentage
        # We normalize it to a 0.0-1.0 float to align with the formula weightings
        normalized_match = match_pct / 100.0 if match_pct > 1.0 else match_pct
        
        score = (normalized_match * 40) + (confidence * 0.4) + (platform_risk * 20)
        
        return min(100.0, score)
    except Exception as e:
        print(f"Error calculating risk score: {e}")
        return 0.0

def get_action_emoji(action):
    """
    Returns an emoji corresponding to the recommended action.
    """
    action_upper = str(action).upper().strip()
    
    if action_upper == "AUTO_TAKEDOWN":
        return "🚨"
    elif action_upper == "ESCALATE":
        return "⚠️"
    elif action_upper == "MONITOR":
        return "👁️"
    elif action_upper == "IGNORE":
        return "✅"
    else:
        return "❓"
