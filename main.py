import json
import os
import time

import requests
from dotenv import load_dotenv
from kubernetes import client, config


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
        print("Warning: MY_NODE_NAME environment variable not set. Cannot filter by current node.")
        print("Please ensure your pod is configured to expose spec.nodeName via Downward API.")
        # Fallback to listing all pods if node name isn't available
        all_pods = v1.list_pod_for_all_namespaces().items
        pods_on_current_node = all_pods # Treat all pods as potentially on current node without filtering
    else:
        all_pods = v1.list_pod_for_all_namespaces().items
        pods_on_current_node = [
            pod for pod in all_pods if pod.spec.node_name == current_node_name
        ]

    if not pods_on_current_node:
        print(f"No pods found on node: {current_node_name}")
        exit_code = 0
        return exit_code

    print(f"Pods and their labels on node: {current_node_name or 'unknown'}")
    for pod in pods_on_current_node:
        print(f"  Pod: {pod.metadata.name}, Namespace: {pod.metadata.namespace}")
        if pod.metadata.labels:
            for key, value in pod.metadata.labels.items():
                print(f"    Label: {key}={value}")
                if key == app_label_name and value == app_label_value:
                    print(f"      Found application label: {value}")
                    exit_code = 1
        else:
            print("    No labels found for this pod.")
    return exit_code

def send_slack_message(message_text = "Hello from Python!"):
    payload = {
        "text": message_text
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)

    if response.status_code == 200:
        print("Slack message sent successfully!")
        return True
    else:
        print(f"Error sending Slack message: {response.status_code} - {response.text}")
        return False

def check_termination_notice():
    try:
        response = requests.get("http://169.254.169.254/latest/meta-data/spot/instance-action", timeout=1)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return None

if __name__ == "__main__":
    load_dotenv()
    print(f"Setting up the application...")

    webhook_url = os.getenv("WEBHOOK_URL", "YOUR_SLACK_WEBHOOK_URL")
    app_label_name = os.getenv("APP_LABEL_NAME", "app.kubernetes.io/name")
    app_label_value = os.getenv("APP_LABEL_VALUE", "my-app")
    application_name = os.getenv("APPLICATION_NAME", "MyApp")
    print(f"Monitoring application '{app_label_value}' with label '{app_label_name}={app_label_value}' on node '{os.environ.get('MY_NODE_NAME', 'unknown')}'")

    while True:
        termination_notice = check_termination_notice()
        if termination_notice and get_pods_labels_on_current_node() > 0 :
            print(f"Termination notice received: {termination_notice}")
            print(
                f"Application '{app_label_value}' is still running on this node. Exiting without sending termination notice.")
            send_slack_message(termination_notice)
            # Implement your graceful shutdown logic here
            # e.g., stop processing new requests, save state, exit
            break
        time.sleep(5) # Poll every 5 seconds
        print(f"No termination notice yet, continuing to monitor...")



