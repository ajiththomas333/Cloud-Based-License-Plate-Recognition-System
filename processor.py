import cv2
import easyocr
import boto3
import json
import os
import time
from botocore.exceptions import ClientError

# ==========================
# CONFIGURATION
# ==========================
REGION = "us-east-1"
QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/aws/video-processing-queue"

SENDER_EMAIL = "ajiththomas@gmail.com"
RECEIVER_EMAIL = "ajiththomas@gmail.com"

# ==========================
# AWS CLIENTS
# ==========================
try:
    sts = boto3.client("sts")
    print("AWS Identity:")
    print(sts.get_caller_identity())

    sqs = boto3.client("sqs", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    ses = boto3.client("ses", region_name=REGION)

    table = dynamodb.Table("WatchlistPlates")

    print("AWS services initialized successfully")

except Exception as e:
    print(f"AWS initialization failed: {e}")
    raise

# ==========================
# EASYOCR MODEL
# ==========================
print("Initializing EasyOCR...")
reader = easyocr.Reader(["en"])

# ==========================
# VIDEO PROCESSING
# ==========================
def process_video(video_path):
    detected_plates = set()

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Unable to open video: {video_path}")
        return []

    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()

        if not ret:
            break

        if frame_count % fps == 0:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                results = reader.readtext(gray)

                for (bbox, text, prob) in results:
                    clean_text = "".join(
                        c for c in text if c.isalnum()
                    ).upper()

                    if len(clean_text) >= 4:
                        detected_plates.add(clean_text)

            except Exception as e:
                print(f"OCR Error: {e}")

        frame_count += 1

    cap.release()

    return list(detected_plates)

# ==========================
# WATCHLIST CHECK
# ==========================
def check_watchlist_and_alert(plates):

    for plate in plates:

        try:
            response = table.get_item(
                Key={
                    "PlateNumber": plate
                }
            )

            if "Item" in response:

                print(f"ALERT: Match found -> {plate}")

                ses.send_email(
                    Source=SENDER_EMAIL,
                    Destination={
                        "ToAddresses": [RECEIVER_EMAIL]
                    },
                    Message={
                        "Subject": {
                            "Data": "WATCHLIST VEHICLE DETECTED"
                        },
                        "Body": {
                            "Html": {
                                "Data": f"""
                                <h3>Security Alert</h3>
                                <p>
                                Vehicle plate
                                <b>{plate}</b>
                                was detected.
                                </p>
                                """
                            }
                        }
                    }
                )

                print("Email sent")

        except ClientError as e:
            print(f"DynamoDB/SES Error: {e}")

# ==========================
# MAIN WORKER LOOP
# ==========================
print("Worker started. Waiting for SQS messages...")

while True:

    try:

        response = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20
        )

        if "Messages" not in response:
            time.sleep(1)
            continue

        message = response["Messages"][0]

        receipt_handle = message["ReceiptHandle"]

        body = json.loads(message["Body"])

        bucket = body["bucket"]
        key = body["key"]

        local_file = f"/tmp/{os.path.basename(key)}"

        print(f"Received file: s3://{bucket}/{key}")

        try:

            s3.download_file(
                bucket,
                key,
                local_file
            )

            print("Download completed")

            plates_found = process_video(local_file)

            print(f"Detected Plates: {plates_found}")

            check_watchlist_and_alert(
                plates_found
            )

        except Exception as e:
            print(f"Processing Error: {e}")

        finally:

            if os.path.exists(local_file):
                os.remove(local_file)

            sqs.delete_message(
                QueueUrl=QUEUE_URL,
                ReceiptHandle=receipt_handle
            )

            print("SQS message deleted")

    except Exception as e:

        print(f"Worker Error: {e}")

        time.sleep(10)
