# Smart Grid IoT Simulator — End-to-End Guide

A complete handbook for setting up and running the Smart Grid IoT simulator that streams telemetry data from an Excel dataset to AWS IoT Core over MQTT.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture & Flow](#architecture--flow)
3. [Prerequisites](#prerequisites)
4. [Project Structure](#project-structure)
5. [AWS IoT Core Setup](#aws-iot-core-setup)
6. [Environment Setup](#environment-setup)
7. [Configuration Reference](#configuration-reference)
8. [Running the Simulator](#running-the-simulator)
9. [Verifying Data in AWS IoT Core](#verifying-data-in-aws-iot-core)
10. [MQTT Payload Schema](#mqtt-payload-schema)
11. [Troubleshooting](#troubleshooting)

---

## Overview

This simulator reads smart grid telemetry records from an Excel file and publishes each row as a JSON message to AWS IoT Core via MQTT over a secure TLS connection (port 8883). It is designed for workshops, demos, and testing IoT pipelines without real hardware.

---

## Architecture & Flow

```
smart_grid_dataset_15.xlsx
        │
        │  pandas reads row by row
        ▼
smart_grid_iot_simulator.py
        │
        │  MQTT over TLS (port 8883)
        │  Client ID : basicPubSub
        │  Topic     : sdk/test/python
        ▼
AWS IoT Core  (ap-south-1)
        │
        ├──► IoT Rule Engine  →  (DynamoDB / S3 / Lambda / etc.)
        └──► MQTT Test Client (live monitoring)
```

**Step-by-step flow:**

1. Script starts and reads `smart_grid_dataset_15.xlsx` into a DataFrame.
2. Establishes a mutual-TLS MQTT connection to AWS IoT Core using X.509 certificates.
3. Iterates through each row of the dataset.
4. Serialises the row into a JSON payload.
5. Publishes the payload to the `sdk/test/python` topic with QoS 1 (AT_LEAST_ONCE).
6. Waits for acknowledgement (PUBACK) from the broker.
7. Sleeps 1 second before the next record.
8. Disconnects cleanly after all records are sent.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.8+ | Check with `python3 --version` |
| AWS account | With IoT Core access in `ap-south-1` |
| AWS IoT Thing created | With a certificate and policy attached |
| Certificates downloaded | `.crt`, `.key`, and Root CA `.pem` files |
| Excel dataset | `smart_grid_dataset_15.xlsx` in project folder |

---

## Project Structure

```
aws-events-Demo/
├── smart_grid_iot_simulator.py                          # Main simulator script
├── smart_grid_dataset_15.xlsx                           # Telemetry dataset
├── AmazonRootCA1.pem                                    # AWS Root CA certificate
├── 9e557a...certificate.pem.crt                         # Device certificate
├── 9e557a...private.pem.key                             # Device private key
├── 9e557a...public.pem.key                              # Device public key (not used by script)
├── thing-policy                                         # IoT Thing policy document
├── venv/                                                # Python virtual environment (created below)
└── SMART_GRID_IOT_GUIDE.md                              # This file
```

---

## AWS IoT Core Setup

### 1. Create a Thing

```
AWS Console → IoT Core → Manage → Things → Create things
→ Create single thing → Name: smart-grid-thing → Next
→ Auto-generate certificates → Next
→ Attach policy (see step 2) → Create thing
→ Download: certificate.pem.crt, private.pem.key, AmazonRootCA1.pem
```

### 2. The Policy — What It Controls and Why It Matters

The IoT policy is the gatekeeper. It controls three things independently:

- Which **Client IDs** are allowed to connect (`iot:Connect`)
- Which **topics** the device can publish to (`iot:Publish`)
- Which **topic filters** the device can subscribe to (`iot:Subscribe`)

**If any of these don't match exactly, the connection is dropped with `AWS_ERROR_MQTT_UNEXPECTED_HANGUP`.**

The policy used in this project (`demo-grid-thing-Policy`) is:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iot:Publish",
        "iot:Receive",
        "iot:PublishRetain"
      ],
      "Resource": [
        "arn:aws:iot:ap-south-1:444952541615:topic/sdk/test/java",
        "arn:aws:iot:ap-south-1:444952541615:topic/sdk/test/python",
        "arn:aws:iot:ap-south-1:444952541615:topic/sdk/test/js"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "iot:Subscribe"
      ],
      "Resource": [
        "arn:aws:iot:ap-south-1:444952541615:topicfilter/sdk/test/java",
        "arn:aws:iot:ap-south-1:444952541615:topicfilter/sdk/test/python",
        "arn:aws:iot:ap-south-1:444952541615:topicfilter/sdk/test/js"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "iot:Connect"
      ],
      "Resource": [
        "arn:aws:iot:ap-south-1:444952541615:client/sdk-java",
        "arn:aws:iot:ap-south-1:444952541615:client/basicPubSub",
        "arn:aws:iot:ap-south-1:444952541615:client/sdk-nodejs-*"
      ]
    }
  ]
}
```

This policy allows:

| Permission | Allowed Values |
|---|---|
| Connect (Client IDs) | `sdk-java`, `basicPubSub`, `sdk-nodejs-*` |
| Publish (Topics) | `sdk/test/java`, `sdk/test/python`, `sdk/test/js` |
| Subscribe (Filters) | `sdk/test/java`, `sdk/test/python`, `sdk/test/js` |

**The script is configured to use `basicPubSub` as the Client ID and `sdk/test/python` as the topic** — both are explicitly allowed by this policy.

> ⚠️ Do not change `CLIENT_ID` or `MQTT_TOPIC` in the script without also updating the policy, or the connection will be rejected.

### 3. Find Your Endpoint

```
AWS Console → IoT Core → Settings → Device data endpoint
```

It will look like:
```
a3f1b3iwt8cu5c-ats.iot.ap-south-1.amazonaws.com
```

Copy this — it goes into `AWS_ENDPOINT` in the script.

### 4. Verify Certificate Status

```
AWS Console → IoT Core → Security → Certificates
```

Confirm your certificate:
- Shows **Active** status
- Has the policy (`demo-grid-thing-Policy`) attached under **Policies**

> The certificate does not need to be attached to a Thing for publishing to work. The policy alone controls access.

---

## Environment Setup

All commands are run from the project directory:

```bash
cd ~/Documents/aws-eee-workshop/aws-events-Demo
```

### Step 1 — Create a Python virtual environment

```bash
python3 -m venv venv
```

> On Kali/Debian, system-wide `pip install` is blocked. Always use a venv.

### Step 2 — Install dependencies

```bash
venv/bin/pip install awsiotsdk pandas openpyxl
```

- `awsiotsdk` — AWS IoT Device SDK, pulls in `awscrt` automatically
- `pandas` — reads the Excel dataset
- `openpyxl` — required by pandas to open `.xlsx` files

### Step 3 — Verify installation

```bash
venv/bin/python -c "from awsiot import mqtt_connection_builder; print('OK')"
```

Expected output: `OK`

---

## Configuration Reference

These values are set at the top of `smart_grid_iot_simulator.py`:

| Variable | Current Value | Description |
|---|---|---|
| `AWS_ENDPOINT` | `a3f1b3iwt8cu5c-ats.iot.ap-south-1.amazonaws.com` | IoT Core data endpoint |
| `CLIENT_ID` | `basicPubSub` | Must match an allowed client in the policy |
| `MQTT_TOPIC` | `sdk/test/python` | Must match an allowed topic in the policy |
| `PATH_TO_ROOT_CA` | `…/AmazonRootCA1.pem` | Amazon Root CA certificate |
| `PATH_TO_CERT` | `…/9e557a…certificate.pem.crt` | Device certificate |
| `PATH_TO_KEY` | `…/9e557a…private.pem.key` | Device private key |
| `DATASET_PATH` | `…/smart_grid_dataset_15.xlsx` | Telemetry data source |
| `STREAM_DELAY_SECONDS` | `1.0` | Delay (seconds) between each published message |

To change the publish rate, edit `STREAM_DELAY_SECONDS`. Set to `0` for maximum speed.

> **Critical:** `CLIENT_ID` and `MQTT_TOPIC` must always match what the attached IoT policy explicitly allows. Mismatches cause silent connection drops.

---

## Running the Simulator

```bash
cd ~/Documents/aws-eee-workshop/aws-events-Demo

venv/bin/python smart_grid_iot_simulator.py
```

### Expected terminal output

```
📖 Reading grid dataset from: .../smart_grid_dataset_15.xlsx
📊 Loaded 15 grid records.
🔌 Initializing secure TLS connection to AWS IoT Core...
✅ Successfully connected to AWS IoT Core!
🚀 Starting Smart Grid simulation. Streaming 15 records at 1.0s intervals...
──────────────────────────────────────────────────────────────────────────────────────────
📡 [1/15] GRID_001 | Load: 62.0% | Temp: 58.2°C | Frequency: 50.01 Hz | Status: Normal
   ✅ Published to topic: sdk/test/python
📡 [2/15] GRID_002 | Load: 68.0% | Temp: 61.5°C | Frequency: 49.99 Hz | Status: Normal
   ✅ Published to topic: sdk/test/python
📡 [3/15] GRID_003 | Load: 76.0% | Temp: 66.8°C | Frequency: 50.03 Hz | Status: Warning
   ✅ Published to topic: sdk/test/python
...
📡 [15/15] GRID_015 | Load: 60.0% | Temp: 56.8°C | Frequency: 50.04 Hz | Status: Normal
   ✅ Published to topic: sdk/test/python
──────────────────────────────────────────────────────────────────────────────────────────
🏁 Smart Grid dataset processing completed.
🔒 Disconnected cleanly from AWS IoT Core.
```

---

## Verifying Data in AWS IoT Core

### Using the MQTT Test Client (Console)

1. Go to **AWS Console → IoT Core → MQTT test client**
2. Click **Subscribe to a topic**
3. Enter topic filter: `sdk/test/python`
4. Click **Subscribe**
5. Run the simulator — messages will appear live in the console as they are published

### Live view tip

Open the MQTT Test Client **before** starting the simulator so you don't miss the first few records.

---

## MQTT Payload Schema

Each message published to the `sdk/test/python` topic is a JSON object with this structure:

```json
{
  "Grid_ID":             "GRID_001",
  "Timestamp":           "2024-01-15 08:00:00",
  "Voltage_kV":          11.2,
  "Current_A":           320.5,
  "Frequency_Hz":        50.01,
  "Active_Power_MW":     3.5,
  "Reactive_Power_MVAR": 1.2,
  "Power_Factor":        0.94,
  "Transformer_Temp_C":  58.2,
  "Load_Percent":        62.0,
  "Energy_MWh":          3.5,
  "Breaker_Status":      "Closed",
  "Grid_Status":         "Normal"
}
```

| Field | Type | Description |
|---|---|---|
| `Grid_ID` | string | Unique grid node identifier |
| `Timestamp` | string | Reading timestamp |
| `Voltage_kV` | float | Line voltage in kilovolts |
| `Current_A` | float | Current in amperes |
| `Frequency_Hz` | float | Grid frequency in hertz (normal: ~50.0) |
| `Active_Power_MW` | float | Active power in megawatts |
| `Reactive_Power_MVAR` | float | Reactive power in MVAR |
| `Power_Factor` | float | Power factor (0–1) |
| `Transformer_Temp_C` | float | Transformer temperature in °C |
| `Load_Percent` | float | Load as percentage of capacity |
| `Energy_MWh` | float | Energy in megawatt-hours |
| `Breaker_Status` | string | `Open` or `Closed` |
| `Grid_Status` | string | `Normal`, `Warning`, or `Critical` |

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'awsiot'`

The system Python does not have the package. Always run the script with the venv Python:

```bash
venv/bin/python smart_grid_iot_simulator.py
```

Or reinstall into the venv:

```bash
venv/bin/pip install awsiotsdk
```

---

### `AWS_ERROR_MQTT_UNEXPECTED_HANGUP`

This is the most common error. It means the connection was accepted at the network level but then immediately dropped by AWS IoT Core. The cause is always a **policy mismatch**. Check in this order:

**1. Is the Client ID allowed by the policy?**

The policy's `iot:Connect` resource must include the Client ID used in the script.
Current script uses `CLIENT_ID = "basicPubSub"` — verify `basicPubSub` is in the policy's connect resources.

**2. Is the topic allowed by the policy?**

The policy's `iot:Publish` resource must include the exact topic.
Current script uses `MQTT_TOPIC = "sdk/test/python"` — verify it's in the policy's topic resources.

**3. Is the certificate Active?**

```
IoT Core → Security → Certificates → check status = Active
```

**4. Is the policy attached to the certificate?**

```
IoT Core → Security → Certificates → [your cert] → Policies tab
```

> The script's `CLIENT_ID` and `MQTT_TOPIC` values were specifically chosen to match the existing policy. Do not change them without updating the policy accordingly.

---

### `FileNotFoundError: Missing required certificate file`

Check that all three certificate files exist in the project directory:

```bash
ls -lh *.pem *.crt *.key
```

Then verify the paths in the script match the actual filenames exactly.

---

### Port 8883 connectivity check

```bash
nc -zv a3f1b3iwt8cu5c-ats.iot.ap-south-1.amazonaws.com 8883
```

Expected: `8883 (?) open` — if this fails, there is a network/firewall issue.

---

### `❌ Dataset file not found`

```bash
ls -lh smart_grid_dataset_15.xlsx
```

Make sure the file is in the project directory and `DATASET_PATH` in the script points to it with the correct absolute path.

---

### `openpyxl` missing error when reading Excel

```bash
venv/bin/pip install openpyxl
```

---

### Cannot install packages — `externally-managed-environment` error

This happens on Kali/Debian systems. Always use the virtual environment:

```bash
# Create venv (only once)
python3 -m venv venv

# Install into venv
venv/bin/pip install awsiotsdk pandas openpyxl

# Run with venv Python
venv/bin/python smart_grid_iot_simulator.py
```

---

*Guide generated for the AWS EEE Workshop — Smart Grid IoT Demo*
