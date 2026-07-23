"""
email_engine.py
---------------
Automated email forwarder for the 3SBC Staffing Platform.
Uses SMTP to send hyper-personalized emails to vendors and candidates.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os

# To use this in production, the user must set these in Vercel Env Vars
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "your-email@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "your-app-password")

def send_vendor_email(vendor_email: str, vendor_name: str, candidate_name: str, job_title: str, ai_reasoning: str, resume_url: str):
    """Sends a human-sounding email to the vendor with the candidate's resume link."""
    if not EMAIL_ADDRESS or EMAIL_ADDRESS == "your-email@gmail.com":
        print("[email_engine] SMTP not configured. Skipping real email to vendor.")
        return False
        
    subject = f"Candidate Submission for {job_title} - {candidate_name}"
    
    # Format the AI reasoning so it looks like a real recruiter wrote it
    body = f"""Hi {vendor_name or 'there'},

I saw your open requirement for the {job_title} position and wanted to submit a very strong consultant from our bench, {candidate_name}.

{ai_reasoning}

You can review their full resume here: 
{resume_url}

Let me know if you have time for a quick chat about their profile this week. We can get them interviewed immediately.

Best regards,
3SBC Staffing Team
"""
    
    return _send_email(vendor_email, subject, body)


def send_candidate_email(candidate_email: str, candidate_name: str, job_title: str, company: str, location: str, ai_reasoning: str):
    """Sends a confirmation email to the candidate explaining why they were submitted."""
    if not EMAIL_ADDRESS or EMAIL_ADDRESS == "your-email@gmail.com" or not candidate_email:
        print("[email_engine] SMTP not configured or candidate missing email. Skipping real email.")
        return False
        
    subject = f"Your profile has been submitted for {job_title} at {company}!"
    
    body = f"""Hi {candidate_name},

Great news! We just submitted your profile for the {job_title} position located in {location}.

Our automated matching system flagged this role for you because:
{ai_reasoning}

We will let you know the moment we hear back from the vendor regarding interview steps. Make sure to keep your phone handy!

Best,
3SBC Staffing Team
"""
    
    return _send_email(candidate_email, subject, body)


def _send_email(to_email: str, subject: str, body: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"[email_engine] Successfully sent email to {to_email}")
        return True
    except Exception as e:
        print(f"[email_engine] Failed to send email to {to_email}: {e}")
        return False
