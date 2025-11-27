import json
import os
import time
import logging


import requests
from dotenv import load_dotenv
from kubernetes import client, config
from flask import Flask, jsonify
from multiprocessing import Process, Value


app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify(status="ok"), 200

def get_pods_labels_on_current_node():
    # Load Kubernetes configuration
    # If running inside a pod, use config.load_incluster_config()
    # Otherwise, for local development, use config.load_kube_config()
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    v1 = client.CoreV1Api()

    exit_code = 0

    # Get the current node name (assuming running in a pod with Downward API)
    # If not in a pod, you would need to determine the node name differently
    current_node_name = os.environ.get("MY_NODE_NAME")
    if not current_node_name:
        logger.warning("Warning: MY_NODE_NAME environment variable not set. Cannot filter by current node.")
        logger.warning("Please ensure your pod is configured to expose spec.nodeName via Downward API.")
        # Fallback to listing all pods if node name isn't available
        all_pods = v1.list_pod_for_all_namespaces().items
        pods_on_current_node = all_pods # Treat all pods as potentially on current node without filtering
    else:
        all_pods = v1.list_pod_for_all_namespaces().items
        pods_on_current_node = [
            pod for pod in all_pods if pod.spec.node_name == current_node_name
        ]

    if not pods_on_current_node:
        logger.info("No pods found on node: {current_node_name}")
        exit_code = 0
        return exit_code

    logger.info("Pods and their labels on node: {current_node_name or 'unknown'}")
    for pod in pods_on_current_node:
        logger.debug("  Pod: {pod.metadata.name}, Namespace: {pod.metadata.namespace}")
        if pod.metadata.labels:
            for key, value in pod.metadata.labels.items():
                logger.debug("    Label: {key}={value}")
                if key == app_label_name and value == app_label_value:
                    logger.debug("      Found application label: {value}")
                    exit_code = 1
        else:
            logger.debug("    No labels found for this pod.")
    return exit_code

def send_slack_message(notice):
    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*[non-prod] Spot notification:*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Event:*\n"+notice.id+"\n*Node:*"+notice.detail+"\n*InstanceID:*"+notice.instanceid+"\n*Comments:* "+notice
                },
                "accessory": {
                    "type": "image",
                    "image_url": "https://api.slack.com/img/blocks/bkb_template_images/approvalsNewDevice.png",
                    "alt_text": "computer thumbnail"
                }
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)

    if response.status_code == 200:
        logger.info("Slack message sent successfully!")
        return True
    else:
        logger.error("Error sending Slack message: {response.status_code} - {response.text}")
        return False

def check_termination_notice():
    try:
        response = requests.get("http://169.254.169.254/latest/meta-data/spot/instance-action", timeout=1)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return None

def check_loop():
    while True:
        termination_notice = check_termination_notice()
        if termination_notice:
            logger.info("Termination notice received: {termination_notice}")
            if get_pods_labels_on_current_node() > 0 :
                logger.info("Application '{app_label_value}' is still running on this node. Exiting without sending termination notice.")
                send_slack_message(termination_notice)
                # Implement your graceful shutdown logic here
                # e.g., stop processing new requests, save state, exit
                break
        time.sleep(5) # Poll every 5 seconds
        logger.debug("No termination notice yet, continuing to monitor...")


log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

# Get a logger instance
logger = logging.getLogger(__name__)

if __name__ == "__main__":


    logger.info("Starting application...")
    load_dotenv()
    logger.info("Setting up the application...")

    webhook_url = os.getenv("WEBHOOK_URL", "YOUR_SLACK_WEBHOOK_URL")
    app_label_name = os.getenv("APP_LABEL_NAME", "app.kubernetes.io/name")
    app_label_value = os.getenv("APP_LABEL_VALUE", "my-app")
    application_name = os.getenv("APPLICATION_NAME", "MyApp")

    logger.info("Monitoring application "+app_label_value+" with label '"+app_label_name+"' on node "+os.environ.get('MY_NODE_NAME', 'unknown')+" for termination notices.")
    process = Process(target=check_loop)
    process.start()
    app.run(debug=True, host="0.0.0.0", use_reloader=False, port=3000)
    process.join()
    logger.info("Exiting application...")
    exit(0)




