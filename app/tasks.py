from app.extensions import celery, mail
from flask_mail import Message

@celery.task(bind=True, max_retries=3)
def send_async_email(self, subject, recipient, body, is_html=True):
    """
    Background task to send an email via Flask-Mail.
    """
    try:
        msg = Message(subject, recipients=[recipient])
        if is_html:
            msg.html = body
        else:
            msg.body = body
            
        mail.send(msg)
        return f"Email sent to {recipient}"
    except Exception as e:
        # Retry in 60 seconds if it fails (e.g., Network/SMTP issues)
        self.retry(exc=e, countdown=60)