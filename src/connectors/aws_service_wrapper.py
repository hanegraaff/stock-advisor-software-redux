"""Author: Mark Hanegraaff -- 2020

This module wraps the boto SDK an offers the following value add to the application:

    1) simplify AWS responses and make them easier to use.
    2) Use paginators when available and combine results.
    2) Automatically catch AWS exceptions and rethrow them as a custom exception
    3) Provide filtering options that are meaningful to the application
"""
import boto3
from exception.exceptions import ValidationError, AWSError
from support import util, constants
import logging

log = logging.getLogger()

# Global clients available to this module]
try:
    CF_CLIENT = boto3.client('cloudformation')
    S3_CLIENT = boto3.client('s3')
    SNS_CLIENT = boto3.client('sns')

except Exception as e:
    raise AWSError("Could not connect to AWS", e)

# A simple in memory cached used to reduce roundtrips to AWS
# pylint: disable=invalid-name
aws_response_cache = {}


def cf_list_exports(stack_name_filter: list):
    '''
        Reads all ClouFormation exports and returns only the ones
        included in the stack_name_filter list

        Parmeters
        ---------
        stack_name_filter : list
            A list of strings representing the names of the stacks used as a filter

        Returns
        ---------
        A dictionary {export_name, export_value} with the filtered values. e.g.

        {
            'export-name-1': 'value1',
            'export-name-2': 'value2',
        }
    '''
    def get_stackname_from_stackarn(arn: str):

        # arn:aws:cloudformation:region:acct:stack/app-infra-base/c9481160-6df5-11ea-ac9f-121b58656156
        try:
            arn_elements = arn.split(':')
            stack_id = arn_elements[5]

            stack_elements = stack_id.split("/")
            return stack_elements[1]
        except Exception as e:
            raise ValidationError("Could not parse stack ID from arn", e)

    if stack_name_filter is None:
        stack_name_filter = []

    return_dict = {}

    key_name = 'get_stackname_from_stackarn'

    try:
        log.debug("looking for cached cloudformation exports")
        return aws_response_cache[key_name]
    except KeyError:
        log.debug("Exports not found. Looking them up")

    try:
        paginator = CF_CLIENT.get_paginator('list_exports')
        response_iterator = paginator.paginate()

        for page in response_iterator:
            for export in page['Exports']:
                stack_name = get_stackname_from_stackarn(
                    export['ExportingStackId'])
                if (stack_name in stack_name_filter):
                    return_dict[export['Name']] = export['Value']

        aws_response_cache[key_name] = return_dict

        return return_dict

    except Exception as e:
        raise AWSError("Could not list Cloudformation exports", e)


def cf_read_export_value(export_name: str):
    '''
        Helper function to read the value of a specific CloudFormation export
        given the supplied export name
    '''
    filter_list = constants.APP_CF_STACK_NAMES

    app_cf_exports = cf_list_exports(filter_list)
    try:
        return app_cf_exports[export_name]
    except Exception:
        raise ValidationError(
            "%s could not be found in clouformation exports." % export_name, None)


def s3_download_object(bucket_name: str, object_name: str, dest_path: str):
    '''
        Downloads an s3 object to the local filesystem and saves it to
        the destination path (path + filename)
    '''
    try:
        S3_CLIENT.download_file(bucket_name, object_name, dest_path)
    except Exception as e:
        raise AWSError("Could not download s3://%s/%s --> %s" %
                       (bucket_name, object_name, dest_path), e)


def s3_upload_object(source_path: str, bucket_name: str, object_name: str):
    '''
        Uploads a file from the source_path (path + file) to the destination bucket
    '''
    try:
        S3_CLIENT.upload_file(source_path, bucket_name, object_name)
    except Exception as e:
        raise AWSError("Could not upload %s --> s3://%s/%s" %
                       (source_path, bucket_name, object_name), e)


def s3_upload_ascii_string(object_contents: str, s3_bucket_name: str, s3_object_name: str):
    '''
        Uploads an ASCII string directly to S3, bypassing a local file.
    '''
    try:
        S3_CLIENT.put_object(
            Body=bytes(object_contents, 'ascii'),
            Bucket=s3_bucket_name,
            Key=s3_object_name
        )
    except Exception as e:
        raise AWSError("Could not upload String to s3://%s/%s" %
                       (s3_bucket_name, s3_object_name), e)


def sns_publish_notification(topic_arn: str, subject: str, message: str):
    '''
        Publishes a simple SNS message
    '''
    try:
        SNS_CLIENT.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject=subject
        )
    except Exception as e:
        raise AWSError("Cannot publish message to SNS topic: %s" %
                       topic_arn, e)


def notify_error(exception: object, service_name: str, stack_trace: str, app_ns: str):
    '''
        Sends an SNS notification indicating that an error prevented the service from running

        Parameters
        ----------
        exception: object
            The underlining exception object
        service_name: str
            The name of the service that is sending the notification
        stack_trace: str
            The stack trace of the error formattes uing 'traceback'
        app_ns: str
            The application namespace supplied to the command line
            used to identify the appropriate CloudFormation exports
    '''
    sns_topic_arn = cf_read_export_value(
        constants.sns_app_notifications_topic_arn(app_ns))
    subject = "%s Error" % service_name
    message = "There was an error running the %s: %s\n\n%s" % \
        (service_name, str(exception), stack_trace)

    log.info("Publishing error event to SNS topic: %s" %
             sns_topic_arn)
    sns_publish_notification(
        sns_topic_arn, subject, message)
