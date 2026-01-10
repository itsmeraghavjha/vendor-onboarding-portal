from app.extensions import celery, mail, db
from flask_mail import Message
from app.models import VerificationLog
from app import create_app
import logging



logger = logging.getLogger(__name__)


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



@celery.task(bind=True, max_retries=3, name="app.tasks.log_audit_entry")
def log_audit_entry(self, vendor_id, v_type, ext_id, status, input_data, response_data):
    """
    Background task to save audit logs.
    Runs inside Celery worker with proper Flask app context.
    """
    app = create_app()

    with app.app_context():
        try:
            log = VerificationLog(
                vendor_request_id=vendor_id,
                verification_type=v_type,
                external_ref_id=ext_id,
                status=status,
                input_payload=input_data,
                api_response=response_data,
            )

            db.session.add(log)
            db.session.commit()

            logger.info(f"✅ [Async Audit] Saved: {v_type} - {status}")
            return "Logged"

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ [Async Audit] Failed: {e}")
            raise self.retry(exc=e, countdown=30)