import os
import json
import time
from flask import Flask, request, Response, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# Load env variables at startup
load_dotenv()

from hunter import hunt_for_content, classify_platform_risk
from judge import judge_violation, calculate_risk_score, get_action_emoji
from reporter import generate_email_body, send_email

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return send_file("app.html")

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
            yield send_event("log", "⚠️ Search API returned empty, using fallback demo URLs...")
            
            demo_urls = {
                "sports": [
                    "https://streameast.io/champions-league-semi-2024",
                    "https://youtube.com/watch?v=reaction123",
                    "https://reddit.com/r/soccer/comments/ucl"
                ],
                "film": [
                    "https://fmovies.to/dune-part-two-full",
                    "https://youtube.com/watch?v=dunereact456",
                    "https://dailymotion.com/video/dune2-unauthorized"
                ],
                "music_video": [
                    "https://freemp3.to/taylor-swift-eras",
                    "https://youtube.com/watch?v=erasreact",
                    "https://dailymotion.com/video/taylor-eras"
                ],
                "news": [
                    "https://streamsite.to/bbc-election-footage",
                    "https://youtube.com/watch?v=newsreact789",
                    "https://reddit.com/r/news/comments/bbc"
                ]
            }
            
            fallback_list = demo_urls.get(content_type, demo_urls["sports"])
            hunted_urls = [
                {
                    "url": url,
                    "title": f"Fallback Demo: {asset_name}",
                    "snippet": "Demo fallback result used because the primary search API returned zero results."
                } for url in fallback_list
            ]
            
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
            
            platform_risk = classify_platform_risk(url)
            # In a real integration this would run fingerprint.py dynamically.
            # We assume a fixed baseline score for simulation of the visual match here
            # since there's no original video uploaded through the UI.
            match_percentage = 0.85 
            
            judgment = judge_violation(
                original_title=asset_name,
                rights_owner=rights_owner,
                content_type=content_type,
                suspect_url=url,
                suspect_title=title,
                snippet=snippet,
                match_percentage=match_percentage,
                platform_risk=platform_risk
            )
            
            verdict = judgment.get("verdict", "UNCLEAR")
            action = judgment.get("action", "MONITOR")
            confidence = judgment.get("confidence", 0)
            
            risk_score = calculate_risk_score(match_percentage, confidence, platform_risk)
            emoji = get_action_emoji(action)
            
            result = {
                "url": url,
                "title": title,
                "platform_risk": platform_risk,
                "match_percentage": match_percentage,
                "verdict": verdict,
                "confidence": confidence,
                "reasoning": judgment.get("reasoning", ""),
                "severity": judgment.get("severity", "LOW"),
                "action": action,
                "escalation_reason": judgment.get("escalation_reason", ""),
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


if __name__ == "__main__":
    print("ContentShield Server Running on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
