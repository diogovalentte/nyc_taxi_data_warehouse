terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key
  region     = var.aws_region
}

module "vpc" {
  source = "./vpc"

  vpc_name          = var.vpc_name
  vpc_cidr          = var.vpc_cidr
  pub_subnet_cidr   = var.pub_subnet_cidr
  mwaa_subnet1_cidr = var.mwaa_subnet1_cidr
  mwaa_subnet2_cidr = var.mwaa_subnet2_cidr
}

module "mwaa" {
  source = "./mwaa"

  bucket_arn  = module.s3.bucket_arn
  bucket_name = var.bucket_name

  aws_region = var.aws_region

  priv_subnet_ids = module.vpc.priv_subnet_ids
  vpc_id          = module.vpc.vpc_id
  vpc_cidr        = var.vpc_cidr

  env_name = var.mwaa_env_name

  emr_cluster_arn = module.emr.cluster_arn

  depends_on = [module.s3, module.emr]
}

module "emr" {
  source = "./emr"

  bucket_name = var.bucket_name

  subnet_id = module.vpc.pub_subnet_id
  vpc_id    = module.vpc.vpc_id

  cluster_name         = var.emr_cluster_name
  master_instance_type = var.emr_master_instance_type
  core_instance_type   = var.emr_core_instance_type
  core_instance_count  = var.emr_core_instance_count
  ebs_size             = var.emr_ebs_size

  redshift_cluster_name = var.redshift_cluster_name

  depends_on = [module.s3, module.redshift]
}

module "s3" {
  source = "./s3"

  bucket_name = var.bucket_name
}

module "redshift" {
  source = "./redshift"

  cluster_name    = var.redshift_cluster_name
  database_name   = var.redshift_database_name
  master_username = var.redshift_master_username
  master_password = var.redshift_master_password
  vpc_id          = module.vpc.vpc_id
}
