import os
import time
import json
import pandas as pd
from awscrt import mqtt
from awsiot import mqtt_connection_builder


# ==========================================
# CONFIGURATION & AWS IoT CORE SETTINGS
# ==========================================

# AWS IoT Core Data Endpoint
AWS_ENDPOINT = "a3f1b3iwt8cu5c-ats.iot.ap-south-1.amazonaws.com"

# MQTT Client ID
CLIENT_ID = "basicPubSub"

# MQTT topic where grid telemetry will be published
MQTT_TOPIC = "sdk/test/python"

# Paths to AWS IoT Core security certificates
PATH_TO_ROOT_CA = "/home/loki/Documents/aws-eee-workshop/aws-events-Demo/AmazonRootCA1.pem"
PATH_TO_CERT = "/home/loki/Documents/aws-eee-workshop/aws-events-Demo/f4a34761b49302961d72b0f17b34e84fa4e28d05ff0e71070d8141a68bb203aa-certificate.pem.crt"
PATH_TO_KEY = "/home/loki/Documents/aws-eee-workshop/aws-events-Demo/f4a34761b49302961d72b0f17b34e84fa4e28d05ff0e71070d8141a68bb203aa-private.pem.key"

# Excel dataset
DATASET_PATH = "/home/loki/Documents/aws-eee-workshop/aws-events-Demo/smart_grid_dataset_15.xlsx"

# Time gap between messages
STREAM_DELAY_SECONDS = 1.0


# ==========================================
# MQTT CONNECTION CALLBACKS
# ==========================================

def on_connection_interrupted(connection, error, **kwargs):
    print(f"⚠️ Connection interrupted. Error: {error}")


def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print(
        f"🔄 Connection resumed. "
        f"Return Code: {return_code}, "
        f"Session Present: {session_present}"
    )


# ==========================================
# INITIALIZE MQTT CONNECTION
# ==========================================

def init_mqtt_connection():

    print("🔌 Initializing secure TLS connection to AWS IoT Core...")

    # Verify certificates exist
    for path in [PATH_TO_ROOT_CA, PATH_TO_CERT, PATH_TO_KEY]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Missing required certificate file: {path}"
            )

    # Build secure MQTT connection
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=AWS_ENDPOINT,
        port=8883,
        cert_filepath=PATH_TO_CERT,
        pri_key_filepath=PATH_TO_KEY,
        ca_filepath=PATH_TO_ROOT_CA,
        on_connection_interrupted=on_connection_interrupted,
        on_connection_resumed=on_connection_resumed,
        client_id=CLIENT_ID,
        clean_session=False,
        keep_alive_secs=30
    )

    connect_future = mqtt_connection.connect()
    connect_future.result()

    print("✅ Successfully connected to AWS IoT Core!")

    return mqtt_connection


# ==========================================
# GRID DATA STREAM SIMULATION
# ==========================================

def stream_grid_data():

    # Check dataset
    if not os.path.exists(DATASET_PATH):
        print(f"❌ Dataset file not found: {DATASET_PATH}")
        return

    print(f"📖 Reading grid dataset from: {DATASET_PATH}")

    # Read Excel dataset
    df = pd.read_excel(DATASET_PATH)

    print(f"📊 Loaded {len(df)} grid records.")

    # Establish AWS IoT Core connection
    try:
        connection = init_mqtt_connection()

    except Exception as e:
        print(f"❌ Failed to connect to AWS IoT Core: {e}")
        return

    print(
        f"🚀 Starting Smart Grid simulation. "
        f"Streaming {len(df)} records "
        f"at {STREAM_DELAY_SECONDS}s intervals..."
    )

    print("-" * 90)

    # ==========================================
    # SEND ONE DATASET ROW AT A TIME
    # ==========================================

    for index, row in df.iterrows():

        payload = {
            "Grid_ID": str(row["Grid_ID"]),
            "Timestamp": str(row["Timestamp"]),
            "Voltage_kV": float(row["Voltage_kV"]),
            "Current_A": float(row["Current_A"]),
            "Frequency_Hz": float(row["Frequency_Hz"]),
            "Active_Power_MW": float(row["Active_Power_MW"]),
            "Reactive_Power_MVAR": float(row["Reactive_Power_MVAR"]),
            "Power_Factor": float(row["Power_Factor"]),
            "Transformer_Temp_C": float(row["Transformer_Temp_C"]),
            "Load_Percent": float(row["Load_Percent"]),
            "Energy_MWh": float(row["Energy_MWh"]),
            "Breaker_Status": str(row["Breaker_Status"]),
            "Grid_Status": str(row["Grid_Status"])
        }

        # Convert dictionary to JSON
        json_payload = json.dumps(payload)

        # Display record in terminal
        print(
            f"📡 [{index + 1}/{len(df)}] "
            f"{payload['Grid_ID']} | "
            f"Load: {payload['Load_Percent']}% | "
            f"Temp: {payload['Transformer_Temp_C']}°C | "
            f"Frequency: {payload['Frequency_Hz']} Hz | "
            f"Status: {payload['Grid_Status']}"
        )

        # ==========================================
        # PUBLISH TO AWS IoT CORE
        # ==========================================

        publish_future, packet_id = connection.publish(
            topic=MQTT_TOPIC,
            payload=json_payload,
            qos=mqtt.QoS.AT_LEAST_ONCE
        )

        # Wait for AWS IoT Core acknowledgement
        publish_future.result()

        print(f"   ✅ Published to topic: {MQTT_TOPIC}")

        # Wait before sending next record
        time.sleep(STREAM_DELAY_SECONDS)

    # ==========================================
    # SIMULATION COMPLETED
    # ==========================================

    print("-" * 90)
    print("🏁 Smart Grid dataset processing completed.")

    # Disconnect from AWS IoT Core
    disconnect_future = connection.disconnect()
    disconnect_future.result()

    print("🔒 Disconnected cleanly from AWS IoT Core.")


# ==========================================
# PROGRAM ENTRY POINT
# ==========================================

if __name__ == "__main__":
    stream_grid_data()
