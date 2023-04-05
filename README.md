# Octopus Mattermost Plugin

This AWS Lambda Function does the following:
- Pulls Octopus Energy Consumption data from the Octopus Energy API
- Calculates peak/off-peak usage
- Posts the data in markdown table format to a Mattermost channel


## Usage
- Change the provider.tf state bucket configuration
- Rename template.tfvars to terraform.tfvars and include your own values