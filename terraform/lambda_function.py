import os
import json
import urllib.request
import boto3

def lambda_handler(event, context):
    pat    = os.environ['GITHUB_PAT']
    org    = os.environ['GITHUB_ORG']
    region = os.environ['AWS_REGION_']
    param  = os.environ['SSM_PARAM']

    # Call GitHub API to get a fresh runner registration token
    url = f'https://api.github.com/orgs/{org}/actions/runners/registration-token'
    req = urllib.request.Request(url, method='POST')
    req.add_header('Authorization', f'Bearer {pat}')
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')

    with urllib.request.urlopen(req) as response:
        data  = json.loads(response.read())
        token = data['token']

    # Write the fresh token to SSM Parameter Store
    ssm = boto3.client('ssm', region_name=region)
    ssm.put_parameter(
        Name=param,
        Value=token,
        Type='SecureString',
        Overwrite=True
    )

    return {'status': 'token refreshed successfully'}
