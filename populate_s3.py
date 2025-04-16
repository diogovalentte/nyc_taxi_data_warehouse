"""
Script to download all the NYC taxi data files from the TLC website and upload them to S3 for testing.
"""

import os
from io import BytesIO
from time import sleep

import boto3
import requests
from boto3.s3.transfer import TransferConfig
from lxml import html

NYC_TAXI_SITE_URL = "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page"
BUCKET_NAME = os.environ["TF_VAR_bucket_name"]


def get_urls():
    source_html = requests.get(NYC_TAXI_SITE_URL).text
    tree = html.fromstring(source_html)
    fhvhv_urls = tree.xpath('//a[contains(@href, "fhvhv_tripdata_")]/@href')

    return fhvhv_urls


def check_if_file_exists(object_key):
    s3 = boto3.client("s3")

    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=object_key)
    except Exception as ex:
        if (
            "An error occurred (404) when calling the HeadObject operation: Not Found"
            in str(ex)
        ):
            return False
        raise ex

    return True


def save_to_s3(url, object_key):
    response = requests.get(url)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        sleep(10)
        response = requests.get(url)
        response.raise_for_status()
    except Exception as ex:
        raise ex

    file_obj = BytesIO(response.content)
    s3 = boto3.client("s3")
    config = TransferConfig(
        multipart_threshold=1024 * 1024 * 10,
        max_concurrency=10,
        multipart_chunksize=1024 * 1024 * 5,
        use_threads=True,
    )

    s3.upload_fileobj(
        file_obj,
        BUCKET_NAME,
        object_key,
        Config=config,
    )


def main():
    urls = get_urls()
    for url in urls:
        url = str(url).strip()
        print(f"Saving {url} to S3")
        filename = url.split("/")[-1]
        year = filename.split("_")[-1].split("-")[0]
        object_key = f"raw/fhvhv/{year}/{filename}"
        if check_if_file_exists(object_key):
            print(f"File {object_key} already exists in S3, skipping...")
            continue
        save_to_s3(url, object_key)
        print(f"Saved {url} to S3 with key {object_key}")


if __name__ == "__main__":
    main()
