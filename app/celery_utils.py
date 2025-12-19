from celery import Celery

def init_celery(app, celery_app):
    """
    Configures the global celery_app with Flask's config.
    """
    celery_app.conf.update(app.config)

    # ContextTask ensures the task runs inside Flask's "app context"
    # This allows the task to access the Database (db.session).
    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    celery_app.main = app.import_name
    return celery_app