from app import celery # You'll need to initialize this in __init__
from flask_mail import Message
from app.extensions import mail

@celery.task(bind=True, max_retries=3)
def send_async_email(self, subject, recipient, body_html):
    try:
        msg = Message(subject, recipients=[recipient])
        msg.html = body_html
        mail.send(msg)
        return "Sent"
    except Exception as e:
        # Enterprise Feature: Auto-retry if it fails!
        self.retry(exc=e, countdown=60)