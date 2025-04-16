import argparse
import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col

spark = SparkSession.builder.appName("nyc_taxi_dw").getOrCreate()


def save_to_redshift(
    bucket_name: str,
    input_file_uri: str,
    redshift_host: str,
    redshift_port: int,
    redshift_dbname: str,
    redshift_table: str,
    redshift_username: str,
    redshift_password: str,
):
    df = spark.read.parquet(input_file_uri)
    df = df.withColumns(
        {
            "pu_location_id": col("PULocationID").cast("integer"),
            "do_location_id": col("DOLocationID").cast("integer"),
        }
    )

    cols = [
        "hvfhs_license_num",
        "dispatching_base_num",
        "request_datetime",
        "on_scene_datetime",
        "pickup_datetime",
        "dropoff_datetime",
        "pu_location_id",
        "do_location_id",
        "sales_tax",
        "congestion_surcharge",
        "airport_fee",
        "tips",
        "driver_pay",
    ]
    df = df.select(*cols)

    redshift_url = f"jdbc:redshift://{redshift_host}:{redshift_port}/{redshift_dbname}"

    df.write.format("jdbc").option("url", redshift_url).option(
        "dbtable", redshift_table
    ).option("user", redshift_username).option("password", redshift_password).option(
        "tempdir", f"s3://{bucket_name}/staging"
    ).option(
        "driver", "com.amazon.redshift.jdbc42.Driver"
    ).mode(
        "append"
    ).save()


def main(args):
    os.environ["AWS_ACCESS_KEY_ID"] = args.aws_access_key_id
    os.environ["AWS_SECRET_ACCESS_KEY"] = args.aws_secret_access_key
    os.environ["AWS_REGION"] = args.aws_region
    save_to_redshift(
        args.s3_bucket_name,
        args.input_file_uri,
        args.redshift_host,
        args.redshift_port,
        args.redshift_dbname,
        args.redshift_table,
        args.redshift_username,
        args.redshift_password,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--aws_access_key_id")
    parser.add_argument("--aws_secret_access_key")
    parser.add_argument("--aws_region")
    parser.add_argument("--s3_bucket_name")
    parser.add_argument("--redshift_host")
    parser.add_argument("--redshift_port")
    parser.add_argument("--redshift_dbname")
    parser.add_argument("--redshift_username")
    parser.add_argument("--redshift_password")
    parser.add_argument("--redshift_table")
    parser.add_argument("--input_file_uri")
    args = parser.parse_args()
    main(args)
