output "vpc_id" {
  value = aws_vpc.main.id
}
output "pub_subnet_id" {
  value = aws_subnet.public.id
}
output "priv_subnet_ids" {
  value = [aws_subnet.priv1.id, aws_subnet.priv2.id]
}
