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

aws_conn = BaseHook.get_connection("nyc_taxi_dw_aws")
redshift_conn = BaseHook.get_connection("nyc_taxi_dw_redshift")


def get_boto3_client(service_name):
    session = boto3.session.Session(
        aws_access_key_id=aws_conn.login,
        aws_secret_access_key=aws_conn.password,
        region_name=Variable.get("nyc_taxi_dw_region_name"),
    )

    return session.client(service_name)


def get_parquet_s3_key(
    url: str | None = None, year: int | None = None, month: int | None = None
):
    if url is not None:
        filename = url.split("/")[-1]
        tmp_year = filename.split("_")[-1].split("-")[0]
        key = f"raw/fhvhv/{tmp_year}/{filename}"
    elif year is not None and month is not None:
        key = f"raw/fhvhv/{year}/fhvhv_tripdata_{year}-{month:02d}.parquet"
    else:
        raise ValueError("Either url or year and month must be provided")

    return key


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

        key = get_parquet_s3_key(year=year, month=month)
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

        filename = f"fhvhv_tripdata_{year}-{month:02d}.parquet"

        source_html = requests.get(NYC_TAXI_SITE_URL).text
        tree = html.fromstring(source_html)
        fhvhv_urls = tree.xpath(f'//a[contains(@href, "{filename}")]/@href')
        if not fhvhv_urls:
            raise ValueError(f"Could not find URL for {filename}")

        return str(fhvhv_urls[0]).strip()

    @task()
    def save_to_s3(url):
        response = requests.get(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            sleep(10)
            response = requests.get(url)
            response.raise_for_status()
        except Exception as ex:
            raise ex

        key = get_parquet_s3_key(url=url)
        file_obj = BytesIO(response.content)
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
    parquet_file_key = (
        "s3://diogovalentium-nyc-taxi-dw/raw/fhvhv/2025/fhvhv_tripdata_2025-01.parquet"
    )

    @task()
    def build_emr_steps():
        logger.info(redshift_conn.host)
        logger.info(redshift_conn.port)
        logger.info(redshift_conn.login)
        logger.info(redshift_conn.password)
        logger.info(aws_conn.login)
        logger.info(aws_conn.password)
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
                        "--aws_access_key_id",
                        aws_conn.login,
                        "--aws_secret_access_key",
                        aws_conn.password,
                        "--aws_region",
                        Variable.get("nyc_taxi_dw_region_name"),
                        "--s3_bucket_name",
                        Variable.get("nyc_taxi_dw_bucket_name"),
                        "--redshift_host",
                        redshift_conn.host,
                        "--redshift_port",
                        str(redshift_conn.port),
                        "--redshift_dbname",
                        Variable.get("nyc_taxi_dw_redshift_dbname"),
                        "--redshift_username",
                        redshift_conn.login,
                        "--redshift_password",
                        redshift_conn.password,
                        "--redshift_table",
                        Variable.get("nyc_taxi_dw_redshift_table"),
                        "--input_file_uri",
                        parquet_file_key,
                    ],
                },
            }
        ]

    emr_steps = build_emr_steps()

    step_adder = EmrAddStepsOperator(
        task_id="add_steps",
        job_flow_id="{{ ti.xcom_pull(task_ids='get_job_flow_id') }}",
        steps="{{ ti.xcom_pull(task_ids='build_emr_steps') }}",
        aws_conn_id="aws_default",
    )

    step_checker = EmrStepSensor(
        task_id="watch_step",
        job_flow_id="{{ ti.xcom_pull('get_job_flow_id') }}",
        step_id="{{ ti.xcom_pull(task_ids='add_steps', key='return_value')[0] }}",
        aws_conn_id="aws_default",
    )

    job_flow_id >> emr_steps >> step_adder >> step_checker
