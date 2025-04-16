variable "aws_access_key_id" {
  type = string
}
variable "aws_secret_access_key" {
  type = string
}
variable "aws_region" {
  type = string
}

variable "bucket_name" {
  type = string
}

variable "emr_cluster_name" {
  type = string
}
variable "emr_master_instance_type" {
  type = string
}
variable "emr_core_instance_type" {
  type = string
}
variable "emr_core_instance_count" {
  type = number
}
variable "emr_ebs_size" {
  type = number
}

variable "mwaa_env_name" {
  type = string
}

variable "vpc_name" {
  type = string
}
variable "vpc_cidr" {
  type = string
}
variable "pub_subnet_cidr" {
  type = string
}
variable "mwaa_subnet1_cidr" {
  type = string
}
variable "mwaa_subnet2_cidr" {
  type = string
}

variable "redshift_cluster_name" {
  type = string
}
variable "redshift_dbname" {
  type = string
}
variable "redshift_master_username" {
  type = string
}
variable "redshift_master_password" {
  type = string
}
