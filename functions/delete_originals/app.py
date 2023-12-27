import os
import json
import boto3
from botocore.exceptions import ClientError


TMP_LOGS_BUCKET_NAME = os.environ['TMP_LOGS_BUCKET_NAME']

s3_client = boto3.client('s3')


def lambda_handler(data, _context):
    bucket_name = data['bucket_name']
    files = get_files(data['files'])

    if not files:
        print("No files to delete.")
        return

    n_files = len(files)
    print(f"{n_files} files to delete...")

    # Prepare a list of objects to delete along with their versions
    objects_to_delete = []
    for file_key in files:
        try:
            # Handle pagination
            paginator = s3_client.get_paginator('list_object_versions')
            page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=file_key)
            for page in page_iterator:
                for version in page.get('Versions', []) + page.get('DeleteMarkers', []):
                    objects_to_delete.append({'Key': file_key, 'VersionId': version['VersionId']})
        except ClientError as e:
            print(f"An error occurred: {e}")
            return

    # Delete objects in batches
    try:
        for i in range(0, len(objects_to_delete), 1000):  # S3 delete_objects API allows up to 1000 keys at once
            response = s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={
                    'Objects': objects_to_delete[i:i+1000],
                    'Quiet': True
                }
            )
            print(f"Deleted {len(response.get('Deleted', []))} items.")
    except ClientError as e:
        print(f"An error occurred during deletion: {e}")

    if isinstance(data['files'], str):
        try:
            s3_client.delete_object(
                Bucket=TMP_LOGS_BUCKET_NAME,
                Key=data['files']
            )
        except ClientError as e:
            print(f"An error occurred when deleting the manifest file: {e}")


def get_files(thing):
    if isinstance(thing, list):
        return thing

    try:
        response = s3_client.get_object(
            Bucket=TMP_LOGS_BUCKET_NAME,
            Key=thing,
        )
        files = json.loads(response['Body'].read())
        return files
    except ClientError as e:
        print(f"An error occurred when retrieving the file list: {e}")
        return []

