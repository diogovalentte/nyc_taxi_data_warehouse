resource "aws_redshift_cluster" "main" {
  cluster_identifier        = var.cluster_name
  database_name             = var.database_name
  master_username           = var.master_username
  master_password           = var.master_password
  node_type                 = "ra3.large"
  cluster_type              = "single-node"
  skip_final_snapshot       = true
  port                      = 5439
  cluster_subnet_group_name = aws_redshift_subnet_group.main.name
  vpc_security_group_ids    = [aws_security_group.sg.id]
  publicly_accessible       = true
  elastic_ip                = aws_eip.main.public_ip
  encrypted                 = true
  apply_immediately         = true

  tags = {
    Name = var.cluster_name
  }
}

resource "aws_eip" "main" {
  domain = "vpc"

  tags = {
    Name = "${var.cluster_name}-redshift-cluster-eip"
  }

}

resource "aws_redshift_subnet_group" "main" {
  name       = "${var.cluster_name}-subnet-group"
  subnet_ids = [var.pub_subnet_id, var.priv_subnet_ids[0], var.priv_subnet_ids[1]]

  tags = {
    Name = "${var.cluster_name}-subnet-group"
  }
}

resource "aws_security_group" "sg" {
  name   = "${var.cluster_name}-redshift-sg"
  vpc_id = var.vpc_id

  tags = {
    Name = "${var.cluster_name}-redshift-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "allow_redshift" {
  security_group_id            = aws_security_group.sg.id
  referenced_security_group_id = aws_security_group.sg.id
  ip_protocol                  = "-1"
}

resource "aws_vpc_security_group_ingress_rule" "allow_db" {
  security_group_id = aws_security_group.sg.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 5439
  to_port           = 5439
}

resource "aws_vpc_security_group_egress_rule" "allow_all_traffic_ipv4" {
  security_group_id = aws_security_group.sg.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
