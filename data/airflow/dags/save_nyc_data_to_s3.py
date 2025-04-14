import logging
from datetime import datetime
from io import BytesIO
from time import sleep

import boto3
import boto3.session
import requests
from airflow import DAG
from airflow.decorators import task
from airflow.hooks.base import BaseHook
from airflow.models import Variable
from airflow.providers.amazon.aws.operators.emr import EmrAddStepsOperator
from airflow.providers.amazon.aws.sensors.emr import EmrStepSensor
from boto3.s3.transfer import TransferConfig
from lxml import html

NYC_TAXI_SITE_URL = "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page"

logger = logging.getLogger(__name__)


def get_boto3_client(service_name, conn_id="aws_default"):
    conn = BaseHook.get_connection(conn_id)
    extras = conn.extra_dejson
    logger.info(extras)

    session = boto3.session.Session(
        aws_access_key_id=conn.login,
        aws_secret_access_key=conn.password,
        region_name=extras["region_name"],
    )
    return session.client(service_name)


with DAG(
    dag_id="save_nyc_data_to_s3",
    start_date=datetime(2019, 2, 1),
    schedule="0 0 L * *",
    catchup=False,
) as dag:

    @task.branch
    def check_if_file_exists(execution_date=None):
        if execution_date is None:
            raise ValueError("execution_date is required")
        year = execution_date.year
        month = execution_date.month
        year = 2025
        month = 1

        key = f"raw/fhvhv/{year}/{month:02d}/fhvhv_tripdata.parquet"
        bucket_name = Variable.get("nyc_taxi_dw_bucket_name")
        s3 = get_boto3_client("s3")

        try:
            s3.head_object(Bucket=bucket_name, Key=key)
            return None
        except Exception as ex:
            if (
                "An error occurred (404) when calling the HeadObject operation: Not Found"
                in str(ex)
            ):
                return "save_to_s3"
            raise ex

    @task()
    def get_current_month_parquet_url(execution_date=None):
        if execution_date is None:
            raise ValueError("execution_date is required")
        year = execution_date.year
        month = execution_date.month
        year = 2025
        month = 1
        filename = f"fhvhv_tripdata_{year}-{month:02d}.parquet"

        source_html = requests.get(NYC_TAXI_SITE_URL).text
        tree = html.fromstring(source_html)
        fhvhv_urls = tree.xpath(f'//a[contains(@href, "{filename}")]/@href')
        if not fhvhv_urls:
            raise ValueError(f"Could not find URL for {filename}")

        return str(fhvhv_urls[0]).strip()

    @task()
    def save_to_s3(url, execution_date=None):
        if execution_date is None:
            raise ValueError("execution_date is required")
        year = execution_date.year
        month = execution_date.month
        year = 2025
        month = 1

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
        key = f"raw/fhvhv/{year}/{month:02d}/fhvhv_tripdata.parquet"
        bucket_name = Variable.get("nyc_taxi_dw_bucket_name")

        s3 = get_boto3_client("s3")
        config = TransferConfig(
            multipart_threshold=1024 * 1024 * 10,
            max_concurrency=10,
            multipart_chunksize=1024 * 1024 * 5,
            use_threads=True,
        )

        s3.upload_fileobj(
            file_obj,
            bucket_name,
            key,
            Config=config,
        )

        return key

    @task()
    def get_job_flow_id():
        emr_cluster_name = Variable.get("nyc_taxi_dw_emr_cluster_name")
        emr = get_boto3_client("emr")
        clusters = emr.list_clusters(ClusterStates=["RUNNING", "WAITING"])
        for cluster in clusters["Clusters"]:
            if cluster["Name"] == emr_cluster_name:
                return cluster["Id"]
        raise ValueError(f"Could not find EMR cluster with name {emr_cluster_name}")

    check_file_exists = check_if_file_exists()
    parquet_file_key = save_to_s3(get_current_month_parquet_url())
    job_flow_id = get_job_flow_id()

    check_file_exists >> parquet_file_key >> job_flow_id

    @task()
    def build_emr_steps(parquet_file_key):
        return [
            {
                "Name": "nyc_taxi_dw",
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Args": [
                        "spark-submit",
                        "--deploy-mode",
                        "cluster",
                        f"s3://{Variable.get('nyc_taxi_dw_bucket_name')}/emr/jobs/spark/etl.py",
                        "--arg1",
                        parquet_file_key,
                    ],
                },
            }
        ]

    step_adder = EmrAddStepsOperator(
        task_id="add_steps",
        job_flow_id="{{ task_instance.xcom_pull(task_ids='get_job_flow_id') }}",
        steps="{{ task_instance.xcom_pull(task_ids='build_emr_steps') }}",
        aws_conn_id="aws_default",
    )

    step_checker = EmrStepSensor(
        task_id="watch_step",
        job_flow_id="{{ task_instance.xcom_pull('get_job_flow_id') }}",
        step_id="{{ task_instance.xcom_pull(task_ids='add_steps', key='return_value')[0] }}",
        aws_conn_id="aws_default",
    )

    job_flow_id >> step_adder >> step_checker
