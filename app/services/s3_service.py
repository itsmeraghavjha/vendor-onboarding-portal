import boto3
from botocore.exceptions import ClientError
from flask import current_app
from botocore.client import Config

class S3Service:
    def __init__(self):
        """Initializes the S3 client using Flask config."""
        region = current_app.config['AWS_REGION']
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=region,
            # 👇 THIS IS THE FIX: Explicitly set the regional endpoint
            endpoint_url=f'https://s3.{region}.amazonaws.com',
            # 👇 RECOMMENDED: Enforce S3v4 signature
            config=Config(signature_version='s3v4')
        )
        self.bucket = current_app.config['S3_BUCKET_NAME']

    def upload_file(self, file_obj, object_name):
        """
        Uploads a file-like object to S3.
        :param file_obj: The file object (from Flask request.files)
        :param object_name: The destination file name in S3 (e.g., 'docs/file.pdf')
        :return: object_name if successful, None otherwise
        """
        try:
            # Check for content type (MIME type) to ensure browser displays it correctly
            content_type = getattr(file_obj, 'content_type', 'application/octet-stream')
            
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket,
                object_name,
                ExtraArgs={'ContentType': content_type}
            )
            print(f"✅ S3 Upload Successful: {object_name}")
            return object_name
        except ClientError as e:
            print(f"❌ S3 Upload Error: {e}")
            return None

    def generate_presigned_url(self, object_name, expiration=3600):
        """Generates a temporary secure link to view the file."""
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': object_name},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            print(f"❌ S3 URL Generation Error: {e}")
            return None