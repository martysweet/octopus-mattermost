# Copy the source code to ../build
resource "null_resource" "copy_source_code" {
  triggers = {
    always_run = timestamp()
  }

  provisioner "local-exec" {
    command = "rm -rf build/* && cp -r ../app/* ../build"
  }
}

# Run pip install
resource "null_resource" "pip_install" {
  depends_on = [null_resource.copy_source_code]
  triggers   = {
    always_run = timestamp()
  }

  provisioner "local-exec" {
    command = "cd ../build && pip install -r requirements.txt -t ."
  }
}

# Zip the build directory
data "archive_file" "lambda_function" {
  depends_on  = [null_resource.pip_install]
  type        = "zip"
  source_dir = "${path.module}/../build/"
  output_path = "${path.module}/lambda_function.zip"
}