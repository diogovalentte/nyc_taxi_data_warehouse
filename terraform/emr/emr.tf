resource "aws_s3_object" "etl" {
  bucket                 = var.bucket_name
  key                    = "emr/jobs/spark/etl.py"
  source                 = "../data/emr/etl.py"
  server_side_encryption = "AES256"
  bucket_key_enabled     = true

  etag = filemd5("../data/emr/etl.py")
}

resource "aws_emr_cluster" "cluster" {
  name          = var.cluster_name
  release_label = "emr-7.8.0"
  applications  = ["Spark"]

  termination_protection            = false
  keep_job_flow_alive_when_no_steps = true

  ec2_attributes {
    subnet_id                         = var.subnet_id
    emr_managed_master_security_group = aws_security_group.sg.id
    emr_managed_slave_security_group  = aws_security_group.sg.id
    instance_profile                  = aws_iam_instance_profile.emr_profile.arn
  }

  master_instance_group {
    instance_type = var.master_instance_type
  }

  core_instance_group {
    instance_type  = var.core_instance_type
    instance_count = var.core_instance_count

    ebs_config {
      size                 = var.ebs_size
      type                 = "gp2"
      volumes_per_instance = 1
    }
  }

  ebs_root_volume_size = var.ebs_size

  service_role = aws_iam_role.iam_emr_service_role.arn

  log_uri = "s3://${var.bucket_name}/emr-logs/"

  auto_termination_policy {
    idle_timeout = 14400 # 4 hours
  }

  depends_on = [aws_s3_object.etl]
}

resource "aws_security_group" "sg" {
  name   = "${var.cluster_name}-emr-sg"
  vpc_id = var.vpc_id
}

# resource "aws_vpc_security_group_ingress_rule" "allow_tls_ipv4" {
#   security_group_id = aws_security_group.allow_tls.id
#   cidr_ipv4         = aws_vpc.main.cidr_block
#   from_port         = 443
#   ip_protocol       = "tcp"
#   to_port           = 443
# }

resource "aws_vpc_security_group_egress_rule" "allow_all_traffic_ipv4" {
  security_group_id = aws_security_group.sg.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_iam_role" "iam_emr_service_role" {
  name = "${var.cluster_name}-emr-service-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = ""
        Principal = {
          Service = "elasticmapreduce.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_policy" "iam_emr_service_policy" {
  policy = jsonencode(
    {
      "Version" : "2012-10-17",
      "Statement" : [
        {
          "Effect" : "Allow",
          "Resource" : "*",
          "Action" : [
            "ec2:DescribeSecurityGroups",
            "ec2:AuthorizeSecurityGroupEgress",
            "ec2:AuthorizeSecurityGroupIngress",
            "ec2:RevokeSecurityGroupEgress",
            "ec2:RevokeSecurityGroupIngress",
            "ec2:CreateNetworkInterface",
            "ec2:RunInstances",
            "ec2:CreateFleet",
            "ec2:CreateLaunchTemplate",
            "ec2:CreateLaunchTemplateVersion",
            "ec2:AuthorizeSecurityGroupEgress",
            "ec2:AuthorizeSecurityGroupIngress",
            "ec2:RevokeSecurityGroupEgress",
            "ec2:RevokeSecurityGroupIngress",
            "ec2:CreateSecurityGroup",
            "iam:PassRole",
          ]
        },
        {
          "Effect" : "Allow",
          "Action" : [
            "redshift:GetClusterCredentials",
            "redshift:DescribeClusters"
          ],
          "Resource" : "arn:aws:redshift:::cluster/${var.redshift_cluster_name}"
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "iam_emr_service_default_emr_policy_attachment" {
  role       = aws_iam_role.iam_emr_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEMRServicePolicy_v2"
}

resource "aws_iam_role_policy_attachment" "iam_emr_service_policy_attachment" {
  role       = aws_iam_role.iam_emr_service_role.name
  policy_arn = aws_iam_policy.iam_emr_service_policy.arn
}

resource "aws_iam_instance_profile" "emr_profile" {
  name = "${var.cluster_name}-instance-profile"
  role = aws_iam_role.iam_instances_role.name
}

resource "aws_iam_service_linked_role" "ec2_spot" {
  aws_service_name = "spot.amazonaws.com"
}

resource "aws_iam_role" "iam_instances_role" {
  name = "${var.cluster_name}-emr-instances-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "iam_instances_policy_attachment" {
  role       = aws_iam_role.iam_instances_role.name
  policy_arn = aws_iam_policy.iam_emr_instances_policy.arn
}

resource "aws_iam_policy" "iam_emr_instances_policy" {
  policy = jsonencode(
    {
      "Version" : "2012-10-17",
      "Statement" : [
        {
          "Effect" : "Allow",
          "Resource" : "*",
          "Action" : [
            "cloudwatch:*",
            "ec2:Describe*",
            "elasticmapreduce:Describe*",
            "elasticmapreduce:ListBootstrapActions",
            "elasticmapreduce:ListClusters",
            "elasticmapreduce:ListInstanceGroups",
            "elasticmapreduce:ListInstances",
            "elasticmapreduce:ListSteps",
            "rds:Describe*",
          ]
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
        }
      ]
    },
  )
}
