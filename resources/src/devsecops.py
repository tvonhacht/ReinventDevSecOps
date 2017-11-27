"""
devsecops.py

This is what our team came up with for offering Unicorn group DevSecOps...
Maybe a semi standard solution would have been better like:
https://aws.amazon.com/answers/devops/aws-cloudformation-validation-pipeline/
or
https://aws.amazon.com/blogs/devops/implementing-devsecops-using-aws-codepipeline/

But... On the otherhand, this one is small and fast, and available as an API..
So we can offer DevSecOps as a service to Unicorn divisions, via a handy API endpoint.
You need to implement static analysis via python, against the YAML templates,
and enforce our policies without failure.

Another team will *hopefully* close the loop doing dynamic analysis with:
AWS Cloudwatch Events
AWS Config Rules

or things like
https://github.com/capitalone/cloud-custodian
https://github.com/Netflix/security_monkey

And because DevSecOps is also about broadening the shared responsibility of security,
as well as automation, we have a basic function here for publishing to a Slack channel.

"""
import ruamel.yaml
import json
import base64
from urllib.parse import urljoin
from urllib.parse import urlencode
import urllib.request as urlrequest

#Configure these to Slack for ChatOps
SLACK_CHANNEL = '' #Slack Channel to target
HOOK_URL = "" #Like https://hooks.slack.com/services/T3KsdfVTL/B3dfNJ4V8/HmsgdXdzjW16pAD3CdASQChI

# Helper Function to enable us to put visibility into chat ops. Also outputs to Cloudwatch Logs.
# The Slack channel to send a message to stored in the slackChannel environment variable
def send_slack(message, username="SecurityBot", emoji=":exclamation:"):
    print(message)
    if not HOOK_URL:
        return None
    slack_message = {
        'channel': SLACK_CHANNEL,
        'text': message,
         "username": username
    }
    try:
        opener = urlrequest.build_opener(urlrequest.HTTPHandler())
        payload_json = json.dumps(slack_message)
        data = urlencode({"payload": payload_json})
        req = urlrequest.Request(HOOK_URL)
        response = opener.open(req, data.encode('utf-8')).read()
        return response.decode('utf-8')
    except requests.exceptions.RequestException:
        print("Slack connection failed. Valid webhook?")
        return None
        

# Define a YAML reader for parsing Cloudformation to handle !Functions like Ref
def general_constructor(loader, tag_suffix, node):
    return node.value
ruamel.yaml.SafeLoader.add_multi_constructor(u'!', general_constructor)

# Define basic security globals
SECURE_PORTS = ["443","22"]

#Our DevSecOps Logic
def handler(event, context):
    yaml = base64.b64decode(event['b64template'])
    cfn = ruamel.yaml.safe_load(yaml)
    
    # We return result for scoring. it needs a policyN entry for every rule, with count of violations.
    # Errors is for debug purposes only when testing
    result = {
        "pass":True,
        "policy0":0,
        "policy1":0, 
        "policy2":0, 
        "policy3":0,
        "errors":[]
    }
    
    send_slack("BUILD: Starting DevSecOps static code analysis of CFN template: {}".format(cfn['Description']))

    #Now we loop over resources in the template, looking for policy breaches
    for resource in cfn['Resources']:
        #Test for Security Groups for Unicorn Security policy0
        if cfn['Resources'][resource]["Type"] == """AWS::EC2::SecurityGroup""":
            if "SecurityGroupIngress" in cfn['Resources'][resource]["Properties"]:
                for rule in cfn['Resources'][resource]["Properties"]['SecurityGroupIngress']:

                    send_slack("BUILD: Found SG rule: {}".format(rule))

                    #Test that SG ports are only 22 or 443 if open to /0
                    if "CidrIp" in rule:
                        if (rule["FromPort"] not in SECURE_PORTS or rule["ToPort"] not in SECURE_PORTS) and rule["CidrIp"] == '0.0.0.0/0':
                            result['pass'] = False
                            result['policy0'] += 1 #Add one to our policy fail counter
                            result["errors"].append("policy0: Port {} not allowed for /0".format(rule["FromPort"]))

                        #lets catch ranges (i.e 22-443)
                        if rule["FromPort"] != rule["ToPort"] and rule["CidrIp"] == '0.0.0.0/0':
                            result['pass'] = False
                            result['policy0'] += 1 #Add one to our policy fail counter
                            result["errors"].append("policy0: Port range {}-{} in not allowed for /0".format(rule["FromPort"],rule["ToPort"]))



    # Now, how did we do? We need to return accurate statics of any policy failures.
    if not result["pass"]:
        for err in result["errors"]:
            print(err)
            send_slack(err)
        send_slack("Failed DevSecOps static code analysis. Please Fix policy breaches.", username="SecurityBotFAIL", emoji=":exclamation:")
    else:
        send_slack("Passed DevSecOps static code analysis Security Testing", username="SecurityBotPASS", emoji=":white_check_mark:")
    return result
