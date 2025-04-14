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


def get_redshift_conn(cluster_name: str, master_username: str, master_password: str):
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

    return psycopg2.connect(
        host=cluster["Endpoint"]["Address"],
        port=cluster["Endpoint"]["Port"],
        user=master_username,
        password=master_password,
        dbname=cluster["DBName"],
    )


def create_db_tables(
    conn: psycopg2.extensions.connection,
):
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
    ]
    create_mwaa_variables(
        env_name=os.environ["TF_VAR_mwaa_env_name"],
        variables=mwaa_variables,
    )

    mwaa_connections = [
        {
            "connection_id": "aws_default",
            "conn_type": "aws",
            "login": os.environ["TF_VAR_aws_access_key_id"],
            "password": os.environ["TF_VAR_aws_secret_access_key"],
            "extra": '{"region_name": "' + os.environ["TF_VAR_aws_region"] + '"}',
        }
    ]
    create_mwaa_connections(
        env_name=os.environ["TF_VAR_mwaa_env_name"],
        connections=mwaa_connections,
    )

    redshift_cluster_name = os.environ["TF_VAR_redshift_cluster_name"]
    redshift_master_username = os.environ["TF_VAR_redshift_master_username"]
    redshift_master_password = os.environ["TF_VAR_redshift_master_password"]
    redshift_conn = get_redshift_conn(
        redshift_cluster_name,
        redshift_master_username,
        redshift_master_password,
    )
    create_db_tables(redshift_conn)


if __name__ == "__main__":
    main()
