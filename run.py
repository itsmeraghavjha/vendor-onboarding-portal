from app import create_app, celery  # <--- Import celery here


app = create_app()
app.app_context().push()  # Optional: ensures app context is active


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)