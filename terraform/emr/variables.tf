variable "bucket_name" {
  type = string
}

variable "vpc_id" {
  type = string
}
variable "subnet_id" {
  type = string
}

variable "cluster_name" {
  type = string
}
variable "master_instance_type" {
  type = string
}
variable "core_instance_type" {
  type = string
}
variable "core_instance_count" {
  type = number
}
variable "ebs_size" {
  type = number
}

variable "redshift_cluster_name" {
  type = string
}
