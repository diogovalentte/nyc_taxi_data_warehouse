import os

import boto3
import boto3.session
import psycopg2

session = boto3.session.Session(
    aws_access_key_id=os.environ["TF_VAR_aws_access_key_id"],
    aws_secret_access_key=os.environ["TF_VAR_aws_secret_access_key"],
    region_name=os.environ["TF_VAR_aws_region"],
)


def create_mwaa_variables(env_name: str, variables: list[dict[str, str]]) -> None:
    mwaa = session.client("mwaa")
    for variable in variables:
        response = mwaa.invoke_rest_api(
            Name=env_name, Path="/variables", Method="POST", Body=variable
        )

        if response["RestApiStatusCode"] != 200:
            raise ValueError(
                f"Failed to create variable {variable['key']} in environment {env_name} {response['RestApiResponse']}"
            )


def create_mwaa_connections(env_name: str, connections: list[dict[str, str]]) -> None:
    mwaa = session.client("mwaa")
    for connection in connections:
        response = mwaa.invoke_rest_api(
            Name=env_name,
            Path="/connections",
            Method="POST",
            Body=connection,
        )

        if response["RestApiStatusCode"] != 200:
            raise ValueError(
                f"Failed to create connection {connection['connection_id']} in environment {env_name} {response['RestApiResponse']}"
            )


def get_redshift_cluster_addr(cluster_name: str):
    redshift = session.client("redshift")
    clusters = redshift.describe_clusters(
        ClusterIdentifier=cluster_name,
    )
    match len(clusters["Clusters"]):
        case 0:
            raise ValueError(
                f"Could not find Redshift cluster with name {cluster_name}"
            )
        case 1:
            cluster = clusters["Clusters"][0]
        case _:
            raise ValueError(
                f"Found multiple Redshift clusters with name {cluster_name}"
            )

    return cluster["Endpoint"]["Address"], cluster["Endpoint"]["Port"]


def create_db_tables(
    host: str,
    port: str,
    dbname: str,
    username: str,
    password: str,
):
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=username,
        password=password,
    )
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fhvhv_tripdata (
            hvfhs_license_num CHAR(6),
            dispatching_base_num CHAR(6),
            request_datetime TIMESTAMP,
            on_scene_datetime TIMESTAMP,
            pickup_datetime TIMESTAMP,
            dropoff_datetime TIMESTAMP,
            pu_location_id INTEGER,
            do_location_id INTEGER,
            sales_tax FLOAT,
            congestion_surcharge FLOAT,
            airport_fee FLOAT,
            tips FLOAT,
            driver_pay FLOAT
        )
        """
    )
    conn.commit()
    cursor.close()


def main():
    bucket_name = os.environ["TF_VAR_bucket_name"]
    emr_cluster_name = os.environ["TF_VAR_emr_cluster_name"]
    mwaa_variables = [
        {
            "key": "nyc_taxi_dw_bucket_name",
            "value": bucket_name,
        },
        {
            "key": "nyc_taxi_dw_emr_cluster_name",
            "value": emr_cluster_name,
        },
        {
            "key": "nyc_taxi_dw_region_name",
            "value": os.environ["TF_VAR_aws_region"],
        },
        {
            "key": "nyc_taxi_dw_redshift_dbname",
            "value": os.environ["TF_VAR_redshift_dbname"],
        },
        {
            "key": "nyc_taxi_dw_redshift_table",
            "value": "fhvhv_tripdata",
        },
    ]
    create_mwaa_variables(
        env_name=os.environ["TF_VAR_mwaa_env_name"],
        variables=mwaa_variables,
    )

    redshift_cluster_name = os.environ["TF_VAR_redshift_cluster_name"]
    redshift_dbname = os.environ["TF_VAR_redshift_database_name"]
    redshift_master_username = os.environ["TF_VAR_redshift_master_username"]
    redshift_master_password = os.environ["TF_VAR_redshift_master_password"]
    redshift_host, redshift_port = get_redshift_cluster_addr(
        redshift_cluster_name,
    )

    mwaa_connections = [
        {
            "connection_id": "nyc_taxi_dw_aws",
            "conn_type": "aws",
            "login": os.environ["TF_VAR_aws_access_key_id"],
            "password": os.environ["TF_VAR_aws_secret_access_key"],
            "extra": '{"region_name": "'
            + os.environ["TF_VAR_aws_region"]
            + '"}',  # for some reason mwaa dag can't read the extra field
        },
        {
            "connection_id": "nyc_taxi_dw_redshift",
            "conn_type": "redshift",
            "host": redshift_host,
            "port": redshift_port,
            "login": redshift_master_username,
            "password": redshift_master_password,
        },
    ]
    create_mwaa_connections(
        env_name=os.environ["TF_VAR_mwaa_env_name"],
        connections=mwaa_connections,
    )

    create_db_tables(
        redshift_host,
        redshift_port,
        redshift_dbname,
        redshift_master_username,
        redshift_master_password,
    )


if __name__ == "__main__":
    main()
