import boto3
from datetime import date
from datetime import timedelta

def lambda_handler(data, _context):
    s3 = boto3.client('s3')
    all_buckets = s3.list_buckets()

    bucket_name_prefixes = data['bucket_names'].split(',')
    result = []

    for bucket in all_buckets['Buckets']:
        for bucket_name_prefix in bucket_name_prefixes:
            if bucket['Name'].startswith(bucket_name_prefix.strip()):
                result.append(bucket['Name'])

    data['bucket_names'] = result

    explicit_date = data.get('date')
    if not explicit_date:
        today = date.today()
        yesterday = today - timedelta(days = 1)
        data['date'] = str(yesterday)

    return data
