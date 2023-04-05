resource "aws_s3_bucket" "terraform_backend" {
  bucket = "octopus-mattermost-terraform-backend"
}

# For new setups, deploy without the backend first, the add the backend stanza and run terraform init
terraform {
  backend "s3" {
    bucket = "octopus-mattermost-terraform-backend"
    key    = "terraform.tfstate"
    region = "eu-west-1"
  }
}

provider "aws" {
  region = var.aws_region
}