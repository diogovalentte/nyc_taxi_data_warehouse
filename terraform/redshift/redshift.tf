resource "aws_redshift_cluster" "main" {
  cluster_identifier  = var.cluster_name
  database_name       = var.database_name
  master_username     = var.master_username
  master_password     = var.master_password
  node_type           = "ra3.large"
  cluster_type        = "single-node"
  skip_final_snapshot = true
  port                = 5439

  tags = {
    Name = var.cluster_name
  }
}

resource "aws_security_group" "sg" {
  name   = "${var.cluster_name}-mwaa-sg"
  vpc_id = var.vpc_id

  tags = {
    Name = "${var.cluster_name}-mwaa-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "allow_443" {
  security_group_id            = aws_security_group.sg.id
  referenced_security_group_id = aws_security_group.sg.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
}

resource "aws_vpc_security_group_ingress_rule" "allow_db" {
  security_group_id = aws_security_group.sg.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 5439
  ip_protocol       = "tcp"
  to_port           = 5439
}

resource "aws_vpc_security_group_egress_rule" "allow_all_traffic_ipv4" {
  security_group_id = aws_security_group.sg.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
