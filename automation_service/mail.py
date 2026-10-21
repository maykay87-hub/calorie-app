"""Transactional SMTP only. No marketing, passwords or health details in emails."""
from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import smtplib
import ssl

def ics_time(epoch): return datetime.fromtimestamp(epoch,timezone.utc).strftime('%Y%m%dT%H%M%SZ')

class MailSender:
    def __init__(self,settings): self.settings=settings
    def __call__(self,key,payload):
        s=self.settings
        if not all([s.smtp_host,s.smtp_user,s.smtp_password,s.mail_from]):
            raise RuntimeError('Transactional email is not configured.')
        msg=EmailMessage()
        msg['From']=s.mail_from; msg['To']=payload['to']; msg['Subject']=payload['subject']
        msg['Message-ID']=f"<{hashlib.sha256(key.encode()).hexdigest()}@maybloomwellness.com>"
        msg.set_content(payload['body'])
        if payload.get('booking_id'):
            event='\r\n'.join(['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//May Bloom//Consultations//EN',
                'BEGIN:VEVENT',f"UID:{payload['booking_id']}@maybloomwellness.com",
                f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",f"DTSTART:{ics_time(payload['starts_at'])}",
                f"DTEND:{ics_time(payload['ends_at'])}",'SUMMARY:May Bloom online consultation',
                'DESCRIPTION:Meeting link will be provided separately by May.','END:VEVENT','END:VCALENDAR',''])
            msg.add_attachment(event.encode(),maintype='text',subtype='calendar',filename='MayBloom-consultation.ics')
        with smtplib.SMTP(s.smtp_host,s.smtp_port,timeout=20) as smtp:
            smtp.starttls(context=ssl.create_default_context()); smtp.login(s.smtp_user,s.smtp_password)
            smtp.send_message(msg)
