# New York Taxi Data Warehouse

## Objectives

1. Create an AWS infrastructure with diverse services.
2. Create a data pipeline in Airflow to get the data from the [NYC Taxi & Limousine Commission](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) and save it to S3
3. Execute a PySpark script in an AWS EMR cluster to read from S3, process it, and save it into a Redshift table.

# Terraform

Terraform is used to automatically create and destroy the AWS infrastructure. The infrastructure is defined in the `terraform` directory. The following resources are created:

- S3 bucket for storing the raw data and config files
- Redshift cluster for the data warehouse
- EMR cluster for data processing
- Managed Airflow for orchestrating the data pipeline
- VPC and IAM resources

# Airflow DAG

The Airflow DAG is defined in the `data/airflow/dags` directory. The DAG is responsible for orchestrating the data pipeline. The following tasks are defined:

- Check if the raw file exists in S3. If not, download it from the NYC TLC website and process it.
- Save the current month's trip data to S3.
- Add a step to the EMR cluster to get the file from S3, process it using PySpark, and load it into a Redshift table.
- Wait until the step is finished.

As the data is available monthly, the DAG is scheduled to run on the last day of each month and process the current month's data.

# EMR Step PySpark File

The PySpark ETL file that runs on AWS EMR is at `data/emr/etl.py`.

# Running

## Prerequisites

- AWS account
- AWS CLI configured
- Terraform installed
- Python 3.7 or higher

## Steps

1. Copy the `.env.example` file to `.env` and fill in the required values.

2. Export the environment variables:

```bash
export $(cat .env | xargs)
```

3. Create the AWS infrastructure using Terraform:

```bash
cd terraform
terraform init
terraform apply
cd ..
```

It'll print the Airflow UI URL. Copy it and open it in your browser. Log in using the username `airflow` and password `airflow`. The Airflow UI will show the DAGs available. The DAG is called `save_nyc_data_to_s3`. **Don't start it yet.**

4. Install the Python dependencies:

```bash
pip install -r requirements.txt
```

5. Execute a script to set up the Airflow environment and create the Redshift tables:

```bash
python3 setup.py
```

6. Go to the Airflow UI and start the DAG `save_nyc_data_to_s3`. It will run the tasks in order. You can check the logs of each task to see the progress.
7. Once the DAG is finished, you can check the Redshift tables to see if the data was loaded correctly. You can use the AWS Console to connect to the Redshift cluster and run queries.

# Destroying

## Steps

1. Destroy the AWS infrastructure using Terraform. This will also delete the S3 bucket and all the data in it.

```bash
terraform destroy
```
