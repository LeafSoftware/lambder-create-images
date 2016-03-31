import boto3
import logging
import pprint
import time
from datetime import datetime

class Backer:
  BACKUP_TAG = "LambderBackup"
  REPLICATE_TAG = "LambderReplicate"

  def __init__(self):
    self.ec2 = boto3.resource('ec2')
    logging.basicConfig()
    self.logger = logging.getLogger()

  def list_all_instances(self):
    for instance in self.ec2.instances.all():
      self.logger.info("instance id: {}".format(instance.id))

  def get_instances_to_backup(self):
    filters = [{'Name':'tag-key', 'Values': [self.BACKUP_TAG]}]
    instances = self.ec2.instances.filter(Filters=filters)
    return instances

  def backup_name(self, source_name):
    time_str = datetime.utcnow().isoformat() + 'Z'
    time_str = time_str.replace(':', '').replace('+', '')
    return source_name + '-' + time_str

  def create_image(self, instance, name, description='', no_reboot=True):
    return instance.create_image(
      Name=name,
      Description=description,
      NoReboot=no_reboot
    )

  def get_snapshot_for_image(self, image):
    devices = image.block_device_mappings
    root_vol = filter(lambda x: x['DeviceName'] == '/dev/sda1', devices)[0]
    return root_vol['Ebs']['SnapshotId']

  # Deregister the ami, then delete the associated volume
  def delete_image(self, image):
    snapshot_id = self.get_snapshot_for_image(image)
    snapshot = self.ec2.Snapshot(snapshot_id)
    image.deregister()
    time.sleep(5) # HACK wait for image to deregister.
    snapshot.delete()

  # Takes a list of images (sorted oldest to newest),
  # and optional maximum number to keep.
  # Returns a list of images to delete
  def get_images_to_delete(self, images, max_to_keep=3):
    images_to_delete = []

    if len(images) >= max_to_keep:
      # remove one extra to make room for the next backup image
      number_to_delete = len(images) - max_to_keep + 1
      images_to_delete = images[0:number_to_delete]

    return images_to_delete

  # Takes an image or instance, returns the backup source
  def get_backup_source(self, resource):
    tags = filter(lambda x: x['Key'] == self.BACKUP_TAG, resource.tags)

    if len(tags) < 1:
      return None

    return tags[0]['Value']

  # return a Dict() of {backupsource: list_of_images}
  def get_images_by_backup_source(self):
    filters = [{'Name':'tag-key', 'Values': [self.BACKUP_TAG]}]
    images = self.ec2.images.filter(Filters=filters)

    results = {}
    for image in images:
      tag = self.get_backup_source(image)
      if tag in results:
        results[tag].append(image)
      else:
        results[tag] = [image]

    for key in results.keys():
      results[key] = sorted(results[key], key=lambda x: x.creation_date)

    return results

  def prune(self):
    pp = pprint.PrettyPrinter()
    images_by_source = self.get_images_by_backup_source()

    self.logger.debug('images_by_source: ' + pp.pformat(images_by_source))

    for source in images_by_source.keys():
      all_backups = images_by_source[source]
      to_delete = self.get_images_to_delete(all_backups)

      self.logger.debug('to_delete: ' + pp.pformat(to_delete))

      for condemned in to_delete:
        self.logger.info("deleting " + condemned.name)
        self.delete_image(condemned)

  def run(self):
    # prune old backups if needed
    self.prune()

    # create new backups
    instances = self.get_instances_to_backup()
    instance_count = len(list(instances))

    self.logger.info("Found {0} instances to be backed up".format(instance_count))

    for instance in instances:
      source = self.get_backup_source(instance)
      self.logger.info('Backing up ' + source + ' ' + instance.id)

      name        = self.backup_name(source)
      description = "Backup of " + source

      image = self.create_image(instance, name, description)

      # add backup source tag to image
      image.create_tags(Tags=[{'Key': self.BACKUP_TAG, 'Value': source}])
