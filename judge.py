import os
import time
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def gemini_reasoning(title, snippet, similarity, platform):
    """
    Secondary reasoning layer using Gemini to provide context-aware classification
    and short explanation.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "API Error: GEMINI_API_KEY not configured. Falling back to rule-based only."
    
    genai.configure(api_key=api_key)
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        Analyze the following potential copyright violation and provide a short classification and explanation (max 2 sentences).
        Title: {title}
        Snippet: {snippet}
        Similarity Match: {similarity*100:.1f}%
        Platform: {platform}
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "Explanation unavailable due to API error. Falling back to rule-based only."

def judge_violation(expected, item_type, match_percentage, platform_risk, suspect_title, snippet, platform):
    """
    Combines rule-based decision with Gemini reasoning.
    """
    # 1. Keep rule-based decision
    if expected == "infringing" or (match_percentage > 0.8 and platform_risk > 0.6):
        action = "AUTO_TAKEDOWN"
        reasoning = "High similarity full upload on risky platform warrants immediate takedown."
        verdict = "INFRINGING"
    elif expected == "fair_use" or item_type == "reaction":
        action = "MONITOR"
        reasoning = "Reaction video format detected; requires human monitoring for fair use assessment."
        verdict = "FAIR_USE"
    elif expected == "safe" or match_percentage < 0.3:
        action = "IGNORE"
        reasoning = "Low match discussion or official material is safe."
        verdict = "NOT_INFRINGING"
    else:
        action = "ESCALATE"
        reasoning = "Ambiguous match requires manual human escalation."
        verdict = "UNCLEAR"

    # 2. Call gemini_reasoning()
    # Gemini is used for context-aware reasoning and explanation, not primary classification
    ai_explanation = gemini_reasoning(suspect_title, snippet, match_percentage, platform)

    # 3. Attach result as "ai_explanation"
    return {
        "verdict": verdict,
        "action": action,
        "reasoning": reasoning,
        "ai_explanation": ai_explanation
    }

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
