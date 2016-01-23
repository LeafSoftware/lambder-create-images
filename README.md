# lambder-create-images

create-images is an AWS Lambda function for use with Lambder.

## REQUIRES:
* python-lambder

This lambda function creates an Amazon Machine Image from each EC2 instance
tagged with Key: 'LambderBackup'. By default, instances will not be rebooted
during the image creation process. The function will retain at most 3 images
and delete the oldest images to stay under this threshold.

## Installation

1. Clone this repo
2. `cp example_lambder.json  lambder.json`
3. Edit lambder.json to set your S3  bucket
4. `lambder function deploy`

## Usage

Schedule the function with a new event. Rember that the cron expression is
based on UTC.

    lambder events add \
      --name CreateImages \
      --function-name Lambder-create-images \
      --cron 'cron(0 6 ? * * *)'

## TODO

* Parameterize the tag in the input event object
* Parameterize number of old images to retain
* Parameterize no-reboot option
