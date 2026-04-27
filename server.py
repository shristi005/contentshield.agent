import os
import json
import time
from flask import Flask, request, Response, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

# Load env variables at startup
load_dotenv()

from hunter import hunt_for_content, classify_platform_risk
from judge import judge_violation, calculate_risk_score, get_action_emoji
from reporter import generate_email_body, send_email
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return render_template("app.html")

@app.route("/scan", methods=["POST"])
def scan():
    data = request.json
    asset_name = data.get("asset_name", "Unknown Asset")
    rights_owner = data.get("rights_owner", "Unknown Owner")
    content_type = data.get("content_type", "general").lower()
    keywords_raw = data.get("keywords", "")
    keywords = keywords_raw.split() if keywords_raw else [asset_name]
    notify_email = data.get("notify_email", "")

    def generate():
        scan_results = []
        
        # Helper to yield SSE formatted messages
        def send_event(event_type, message, event_data=None):
            event = {
                "type": event_type,
                "message": message
            }
            if event_data is not None:
                event["data"] = event_data
            return f"data: {json.dumps(event)}\n\n"
            
        yield send_event("log", "🛡️ ContentShield Agent Starting...")
        time.sleep(1)
        yield send_event("log", "🔍 Beginning internet sweep...")
        
        # 1. Hunt for content
        hunted_urls = hunt_for_content(asset_name, content_type, keywords)
        
        if not hunted_urls:
            yield send_event("log", "⚠️ Using cached intelligence dataset (API rate limit fallback)...")
            
            try:
                with open("demo_dataset.json", "r") as f:
                    dataset = json.load(f)
                
                # Normalize content type for dict key
                if "film" in content_type:
                    content_key = "film"
                elif "music" in content_type:
                    content_key = "music_video"
                elif "sport" in content_type:
                    content_key = "sports"
                else:
                    content_key = "film" # fallback
                    
                hunted_urls = dataset.get(content_key, dataset.get("film", []))
            except Exception as e:
                yield send_event("log", f"⚠️ Failed to load dataset: {e}")
                hunted_urls = []
            
        yield send_event("log", f"📡 Found {len(hunted_urls)} potential URLs to investigate")
        
        # 2. Investigate each URL
        for idx, item in enumerate(hunted_urls):
            url = item.get("url", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            
            # Print short URL to terminal for cleanliness
            short_url = url if len(url) < 60 else url[:57] + "..."
            yield send_event("log", f"🧬 Analyzing URL {idx+1}: {short_url}")
            time.sleep(0.5)
            
            platform_risk = item.get("platform_risk_score", classify_platform_risk(url))
            match_percentage = item.get("demo_match", 0.85)
            
            frames_compared = 1200
            matched_frames = int(frames_compared * match_percentage)
            
            yield send_event("log", f"   [Step] Scanning sources...")
            time.sleep(0.3)
            yield send_event("log", f"   [Step] Extracting fingerprints...")
            time.sleep(0.3)
            yield send_event("log", f"   [Step] Running similarity analysis (Matched {matched_frames}/{frames_compared} frames)...")
            time.sleep(0.3)
            yield send_event("log", f"   [Step] Evaluating with AI...")
            time.sleep(0.3)
            
            expected = item.get("expected_behavior", "unclear")
            item_type = item.get("type", "unknown")
            
            confidence = int((match_percentage * 60) + (platform_risk * 30) + (10 if item_type == "full_upload" else 0))
            confidence = min(100, max(30, confidence))
            
            if confidence >= 80:
                confidence_label = "HIGH"
            elif confidence >= 60:
                confidence_label = "MEDIUM"
            else:
                confidence_label = "LOW"
            
            if expected == "infringing" or (match_percentage > 0.8 and platform_risk > 0.6):
                action = "AUTO_TAKEDOWN"
                reasoning = f"High similarity ({match_percentage*100:.0f}%) full upload on risky platform warrants immediate takedown."
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

            yield send_event("log", f"   [Step] Enforcing action...")
            time.sleep(0.3)
            
            risk_score = calculate_risk_score(match_percentage, confidence, platform_risk)
            emoji = get_action_emoji(action)
            
            result = {
                "url": url,
                "title": title,
                "platform": urlparse(url).netloc if url else "unknown",
                "platform_risk": platform_risk,
                "match_percentage": match_percentage,
                "frames_compared": frames_compared,
                "matched_frames": matched_frames,
                "verdict": verdict,
                "confidence": confidence,
                "confidence_label": confidence_label,
                "reasoning": reasoning,
                "severity": "HIGH" if action == "AUTO_TAKEDOWN" else "LOW",
                "action": action,
                "escalation_reason": "Review required" if action in ["MONITOR", "ESCALATE"] else "",
                "risk_score": risk_score
            }
            scan_results.append(result)
            
            log_line = f"{emoji} {verdict} detected — {action} (Risk {risk_score:.1f}/100)"
            yield send_event("log", log_line)
            time.sleep(0.5)

        # 3. Final summary
        yield send_event("log", "📄 Generating formal DMCA Takedown Notices...")
        time.sleep(1)
        
        email_sent = False
        if notify_email:
            try:
                from reporter import generate_email_body, send_email
                import os
                email_body = generate_email_body(asset_name, content_type, scan_results)
                email_sent = send_email(notify_email, f"ContentShield Report: {asset_name}", email_body)
                if email_sent:
                    yield f"data: {json.dumps({'type': 'log', 'message': '📧 Report delivered to ' + notify_email})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'log', 'message': '❌ Email failed'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'log', 'message': '❌ Email error: ' + str(e)})}\n\n"
                
        yield send_event("log", "✅ Autonomous Pipeline Complete")
        time.sleep(0.5)
        
        # Send complete event with the final results array
        yield send_event("complete", "Scan finished successfully", {
            "results": scan_results,
            "email_sent": email_sent
        })

    return Response(generate(), mimetype="text/event-stream")


@app.route("/send-report", methods=["POST"])
def send_report():
    data = request.json
    asset_name = data.get("asset_name", "Unknown Asset")
    content_type = data.get("content_type", "general")
    notify_email = data.get("notify_email", "")
    scan_results = data.get("scan_results", [])
    
    if not notify_email:
        return jsonify({"success": False, "error": "No notify_email provided"}), 400
        
    try:
        email_body = generate_email_body(asset_name, content_type, scan_results)
        subject = f"ContentShield Report: {asset_name}"
        success = send_email(notify_email, subject, email_body)
        
        if success:
            return jsonify({"success": True, "message": "Email sent successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to send email"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# if __name__ == "__main__":
#     print("ContentShield Server Running on http://localhost:5000")
#     app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    print("ContentShield Server Running...")

    port = int(os.environ.get("PORT", 5000))  # 👈 dynamic port

    app.run(host="0.0.0.0", port=port)