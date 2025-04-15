resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr

  tags = {
    Name = var.vpc_name
  }
}

resource "aws_subnet" "priv1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.mwaa_subnet1_cidr
  availability_zone       = local.azs[0]
  map_public_ip_on_launch = false

  tags = {
    Name = "mwaa-priv-subnet1"
  }
}

resource "aws_subnet" "priv2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.mwaa_subnet2_cidr
  availability_zone       = local.azs[1]
  map_public_ip_on_launch = false

  tags = {
    Name = "mwaa-priv-subnet2"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.pub_subnet_cidr
  map_public_ip_on_launch = true

  tags = {
    Name = "pub-subnet"
  }
}

resource "aws_route_table" "pub_sub" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.pub-subnet.id
  }

  tags = {
    Name = "${var.vpc_name}-pub-subnet-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.pub_sub.id
}

resource "aws_internet_gateway" "pub-subnet" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.vpc_name}-pub-subnet-igw"
  }
}

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "${var.vpc_name}-nat-eip"
  }

  depends_on = [aws_internet_gateway.pub-subnet]
}

resource "aws_nat_gateway" "gw" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id

  depends_on = [aws_internet_gateway.pub-subnet]

  tags = {
    Name = "${var.vpc_name}-nat-gateway"
  }
}

resource "aws_route_table" "priv_sub" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.gw.id
  }

  tags = {
    Name = "${var.vpc_name}-priv-subnets-rt"
  }
}

resource "aws_route_table_association" "priv1" {
  subnet_id      = aws_subnet.priv1.id
  route_table_id = aws_route_table.priv_sub.id
}

resource "aws_route_table_association" "priv2" {
  subnet_id      = aws_subnet.priv2.id
  route_table_id = aws_route_table.priv_sub.id
}
