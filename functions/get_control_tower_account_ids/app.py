from calendar import month
import os
import boto3
from botocore.config import Config

ORG_ID = os.environ['ORG_ID']

s3_config = Config(
    max_pool_connections=50,
    retries={'max_attempts': 10}
)

client = boto3.client('s3', config=s3_config)

def lambda_handler(data, _context):
    bucket_name = data['bucket_name']

    print(f"Checking existence of {bucket_name}...")
    client.head_bucket(Bucket=bucket_name)
    print("Bucket exists.")

    log_type = data['log_type']
    print(f"Processing {log_type} logs...")

    if log_type in ['CloudTrail', 'CloudTrail-Digest']:
        print(f"Checking whether the {log_type} log structure is that of Control Tower v3.0 or higher...")

        prefix = f'{ORG_ID}/AWSLogs/{ORG_ID}/'
        response = client.list_objects_v2(
            Bucket=bucket_name,
            Delimiter='/',
            Prefix=prefix
        )
        account_prefixes = list(map(lambda x: x['Prefix'], response['CommonPrefixes']))
        if account_prefixes:
            print(f"Version 3.0+ detected: logs found under {prefix}.")
            return account_prefixes
        print(f"No logs found under {prefix}, assuming Control Tower < v3.0.")

    prefix = f'{ORG_ID}/AWSLogs/'
    response = client.list_objects_v2(
        Bucket=bucket_name,
        Delimiter='/',
        Prefix=prefix
    )
    account_prefixes = list(map(lambda x: x['Prefix'], response['CommonPrefixes']))
    print(account_prefixes)
    return account_prefixes
