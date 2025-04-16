resource "aws_s3_object" "requirements" {
  bucket                 = var.bucket_name
  key                    = "airflow/requirements.txt"
  source                 = "../data/airflow/dags/requirements.txt"
  server_side_encryption = "AES256"
  bucket_key_enabled     = true

  etag = filemd5("../data/airflow/dags/requirements.txt")
}

resource "aws_s3_object" "dag" {
  bucket                 = var.bucket_name
  key                    = "airflow/dags/save_nyc_data_to_s3.py"
  source                 = "../data/airflow/dags/save_nyc_data_to_s3.py"
  server_side_encryption = "AES256"
  bucket_key_enabled     = true

  etag = filemd5("../data/airflow/dags/save_nyc_data_to_s3.py")
}

resource "aws_mwaa_environment" "mwaa" {
  airflow_version = "2.10.3"

  airflow_configuration_options = {
    "core.default_task_retries" = 1
    "core.parallelism"          = 3
  }

  dag_s3_path           = "airflow/dags/"
  requirements_s3_path  = "airflow/requirements.txt"
  execution_role_arn    = aws_iam_role.mwaa.arn
  name                  = var.env_name
  webserver_access_mode = "PUBLIC_ONLY"
  environment_class     = "mw1.micro"

  network_configuration {
    security_group_ids = [aws_security_group.sg.id]
    subnet_ids         = var.priv_subnet_ids
  }

  logging_configuration {
    dag_processing_logs {
      enabled   = true
      log_level = "INFO"
    }

    scheduler_logs {
      enabled   = true
      log_level = "INFO"
    }

    task_logs {
      enabled   = true
      log_level = "INFO"
    }

    webserver_logs {
      enabled   = true
      log_level = "INFO"
    }

    worker_logs {
      enabled   = true
      log_level = "INFO"
    }
  }

  source_bucket_arn = var.bucket_arn
}

resource "aws_iam_role" "mwaa" {
  name = "${var.env_name}-mwaa-role"

  assume_role_policy = jsonencode(
    {
      "Version" : "2012-10-17",
      "Statement" : [
        {
          "Effect" : "Allow",
          "Principal" : {
            "Service" : ["airflow.amazonaws.com", "airflow-env.amazonaws.com"]
          },
          "Action" : "sts:AssumeRole"
        }
      ]
    }
  )
}

resource "aws_iam_policy" "iam_policy" {
  name = "${var.env_name}-mwaa-policy"
  path = "/"

  policy = jsonencode(
    {
      "Version" = "2012-10-17",
      "Statement" = [
        {
          "Effect"   = "Allow",
          "Action"   = "airflow:PublishMetrics",
          "Resource" = "arn:aws:airflow:${var.aws_region}:*:environment/${var.env_name}"
        },
        {
          "Effect"   = "Deny",
          "Action"   = "s3:ListAllMyBuckets",
          "Resource" = "*",
        },
        {
          "Effect" = "Allow",
          "Action" = [
            "s3:GetObject*",
            "s3:PutObject*",
            "s3:GetBucket*",
            "s3:GetEncryptionConfiguration",
            "s3:List*"
          ],
          "Resource" = [
            "${var.bucket_arn}",
            "${var.bucket_arn}/*",
          ]
        },
        {
          "Effect" = "Allow"
          "Action" = [
            "elasticmapreduce:ListClusters",
            "elasticmapreduce:DescribeCluster",
            "elasticmapreduce:AddJobFlowSteps",
            "elasticmapreduce:DescribeStep",
            "elasticmapreduce:ListSteps"
          ]
          "Resource" = var.emr_cluster_arn
        },
        {
          "Effect" = "Allow",
          "Action" = [
            "logs:CreateLogStream",
            "logs:CreateLogGroup",
            "logs:PutLogEvents",
            "logs:GetLogEvents",
            "logs:GetLogRecord",
            "logs:GetLogGroupFields",
            "logs:GetQueryResults"
          ],
          "Resource" = [
            "arn:aws:logs:*:*:log-group:airflow-*:*"
          ]
        },
        {
          "Effect" = "Allow",
          "Action" = [
            "logs:DescribeLogGroups"
          ],
          "Resource" = [
            "*"
          ]
        },
        {
          "Effect"   = "Allow",
          "Action"   = "cloudwatch:PutMetricData",
          "Resource" = "*"
        },
        {
          "Effect" = "Allow"
          "Action" = [
            "ec2:CreateNetworkInterface",
            "ec2:DescribeNetworkInterfaces",
            "ec2:DeleteNetworkInterface",
            "ec2:DescribeSubnets",
            "ec2:DescribeSecurityGroups",
            "ec2:DescribeVpcs"
          ]
          "Resource" = "*"
        },
        {
          "Effect" = "Allow",
          "Action" = [
            "sqs:ChangeMessageVisibility",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes",
            "sqs:GetQueueUrl",
            "sqs:ReceiveMessage",
            "sqs:SendMessage"
          ],
          "Resource" = "arn:aws:sqs:${var.aws_region}:${var.account_id}:airflow-celery-*"
        },
        {
          "Effect" : "Allow",
          "Action" : [
            "kms:Decrypt",
            "kms:DescribeKey",
            "kms:GenerateDataKey*",
            "kms:Encrypt"

          ],
          "NotResource" : "arn:aws:kms:*:${var.account_id}:key/*",
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "mwaa_role_policy" {
  role       = aws_iam_role.mwaa.name
  policy_arn = aws_iam_policy.iam_policy.arn
}

resource "aws_security_group" "sg" {
  name   = "${var.env_name}-mwaa-sg"
  vpc_id = var.vpc_id

  tags = {
    Name = "${var.env_name}-mwaa-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "allow_443" {
  security_group_id            = aws_security_group.sg.id
  referenced_security_group_id = aws_security_group.sg.id
  from_port                    = 443
  ip_protocol                  = "tcp"
  to_port                      = 443
}

resource "aws_vpc_security_group_ingress_rule" "allow_db" {
  security_group_id            = aws_security_group.sg.id
  referenced_security_group_id = aws_security_group.sg.id
  from_port                    = 5432
  ip_protocol                  = "tcp"
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "allow_all_traffic_ipv4" {
  security_group_id = aws_security_group.sg.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
