import boto3
import json
import os
import uuid
import datetime
from urllib.parse import unquote_plus
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
from boto3.dynamodb.conditions import Key

patch_all()

dynamodb = boto3.resource('dynamodb')
job_table = dynamodb.Table(os.environ['JOB_TABLE'])
create_hls = os.environ['ENABLE_HLS']
segment_time = os.environ['DEFAULT_SEGMENT_TIME']
sfn_client = boto3.client('stepfunctions')

dataset_table = dynamodb.Table('serverless-video-transcode-datasets')


def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])
        object_prefix = key[:key.rfind('/') + 1]
        object_name = key[key.rfind('/') + 1:]

        # create a job item in dynamodb
        job_id = str(uuid.uuid4())
        job_table.put_item(
            Item={
                'id': job_id,
                'bucket': bucket,
                'key': key,
                'object_prefix': object_prefix,
                'object_name': object_name,
                'created_at': datetime.datetime.now().isoformat()
            }
        )

        #Try to update the ddb table for status

        response = dataset_table.query(
            IndexName='s3_key-index',
            KeyConditionExpression=Key('status').eq(key)
        )
        print("GUMING DEBUG>> response of query is "+response)


        # kick start the main statemachine for transcoding
        response = sfn_client.start_execution(
            stateMachineArn=os.environ['SFN_ARN'],
            input= json.dumps({
                'job_id': job_id,
                'bucket': bucket,
                'key': key,
                'object_prefix': object_prefix,
                'object_name': object_name,
                "segment_time": segment_time,
                'create_hls': create_hls
            })
        )
