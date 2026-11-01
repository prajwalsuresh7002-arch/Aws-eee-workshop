import json
import boto3

sns_client = boto3.client('sns')
SNS_TOPIC_ARN = 'YOUR_SNS_TOPIC_ARN_HERE' 

def lambda_handler(event, context):
    for record in event['Records']:
        
        payload = json.loads(record['body'])
        print(f"📡 Received telemetry: {payload}")
        
        grid_id = payload.get('Grid_ID', 'UNKNOWN')
        transformer_temp = payload.get('Transformer_Temp_C', 0)
        current = payload.get('Current_A', 0)
        grid_status = payload.get('Grid_Status', 'Normal')
        
        # 3. Microcontroller Logic (Catches both Warnings and Criticals)
        if grid_status == "Critical" or (transformer_temp >= 80 or current >= 600):
            
            # TRIGGER 1: CRITICAL FAULT
            alert_message = (
                f"🚨 CRITICAL FAULT DETECTED 🚨\n\n"
                f"Location: {grid_id}\n"
                f"Status: {grid_status}\n"
                f"Transformer Temp: {transformer_temp}°C\n"
                f"Load Current: {current}A\n\n"
                f"Action: Immediate shutdown and maintenance required!"
            )
            sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=alert_message,
                Subject=f"🚨 EMERGENCY ALARM: {grid_id} Critical Failure"
            )
            print(f"🚨 Critical Alarm triggered for {grid_id}!")

        elif grid_status == "Warning" or (transformer_temp >= 65 or current >= 500):
            
            # TRIGGER 2: WARNING FAULT
            alert_message = (
                f"⚠️ SUBSTATION WARNING ⚠️\n\n"
                f"Location: {grid_id}\n"
                f"Status: {grid_status}\n"
                f"Transformer Temp: {transformer_temp}°C\n"
                f"Load Current: {current}A\n\n"
                f"Action: Dispatch technician for inspection."
            )
            sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=alert_message,
                Subject=f"⚠️ WARNING: {grid_id} High Load Detected"
            )
            print(f"⚠️ Warning Alarm triggered for {grid_id}!")
            
        else:
            print(f"✅ {grid_id} is operating safely.")
            
    return {'statusCode': 200, 'body': 'Processed successfully'}