variable "cluster_name" {
  type = string
}
variable "database_name" {
  type = string
}
variable "master_username" {
  type = string
}
variable "master_password" {
  type = string
}
variable "vpc_id" {
  type = string
}
variable "priv_subnet_ids" {
  type = list(string)
}
variable "pub_subnet_id" {
  type = string
}
