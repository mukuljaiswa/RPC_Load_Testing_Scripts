import os
import requests
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENTS = os.getenv("EMAIL_RECIPIENTS").split(",")

report_file = "locust_report.html"
locust_report_url = "http://localhost:8089/stats/report?theme=dark"  # New Locust report download URL

def remove_old_report():
    if os.path.exists(report_file):
        os.remove(report_file)
        print(f"[INFO] Removed old report: {report_file}")

def download_report():
    try:
        print("[INFO] Attempting to download latest Locust report...")
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(locust_report_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        with open(report_file, "wb") as f:
            f.write(response.content)
        
        print(f"[INFO] Report downloaded successfully: {report_file}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to download report: {e}")
        return False

def send_email():
    if os.path.exists(report_file):
        os.remove(report_file)
        print("[INFO] Deleted previous report before downloading new one.")
    
    if not download_report():
        print("[ERROR] Report download failed. Skipping email.")
        return
    
    if not os.path.exists(report_file):
        print("[ERROR] Report still not found. Skipping email.")
        return
    
    try:
        msg = EmailMessage()
        msg["Subject"] = "Locust Load Test Report"
        msg["From"] = EMAIL_SENDER
        msg["To"] = ", ".join(EMAIL_RECIPIENTS)
        msg.set_content("Please find the attached Locust HTML performance report.")
        
        with open(report_file, "rb") as f:
            file_data = f.read()
            msg.add_attachment(file_data, maintype="text", subtype="html", filename=os.path.basename(report_file))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        
        print(f"[INFO] Email sent successfully to {EMAIL_RECIPIENTS}")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
