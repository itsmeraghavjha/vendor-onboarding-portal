from app.extensions import celery, mail # <--- Import from extensions
from flask_mail import Message

@celery.task(bind=True, max_retries=3)
def send_async_email(self, subject, recipient, body_html):
    try:
        msg = Message(subject, recipients=[recipient])
        msg.html = body_html
        mail.send(msg)
        return f"Email sent to {recipient}"
    except Exception as e:
        # Retry in 60 seconds if it fails (e.g., Gmail is down)
        self.retry(exc=e, countdown=60)