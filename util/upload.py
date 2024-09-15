import boto3
from botocore.exceptions import NoCredentialsError
import os
import zipfile

# Initialize the S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_S3_REGION')
)

# Function to zip the point cloud directory before upload
def zip_point_cloud_dir(point_cloud_dir, zip_file_path):
    print(f"Zipping point cloud directory: {point_cloud_dir} to {zip_file_path}...")
    with zipfile.ZipFile(zip_file_path, 'w') as zipf:
        for root, dirs, files in os.walk(point_cloud_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, point_cloud_dir))
    print(f"Point cloud directory zipped successfully to: {zip_file_path}")

# Function to upload point cloud to S3 and return its URL
def upload_to_edgestore(point_cloud_dir):
    try:
        # Create a zip file for the point cloud directory
        zip_file_path = f"{point_cloud_dir}.zip"
        zip_point_cloud_dir(point_cloud_dir, zip_file_path)

        # Define the S3 key (filename in the bucket)
        s3_key = os.path.basename(zip_file_path)

        # Upload the zip file to S3
        bucket_name = os.getenv('AWS_S3_BUCKET')
        print(f"Uploading {zip_file_path} to S3 bucket {bucket_name}...")
        s3_client.upload_file(zip_file_path, bucket_name, s3_key)

        # Generate the public S3 URL
        s3_url = f"https://{bucket_name}.s3.{os.getenv('AWS_S3_REGION')}.amazonaws.com/{s3_key}"
        print(f"File uploaded successfully. S3 URL: {s3_url}")

        return s3_url

    except FileNotFoundError:
        print("The file was not found.")
        raise
    except NoCredentialsError:
        print("Credentials not available.")
        raise
