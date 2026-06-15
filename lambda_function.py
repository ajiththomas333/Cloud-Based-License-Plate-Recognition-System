import json
import boto3
import urllib.parse

sqs = boto3.client('sqs')

QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/953650654815/video-processing-queue"

def lambda_handler(event, context):

    print("EVENT RECEIVED:")
    print(json.dumps(event))

    bucket = event['Records'][0]['s3']['bucket']['name']

    key = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['object']['key'],
        encoding='utf-8'
    )

    message_body = {
        "bucket": bucket,
        "key": key
    }

    response = sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message_body)
    )

    print("Message sent to SQS")

    return {
        "statusCode": 200,
        "body": json.dumps("Video queued successfully")
    }
