import serial
import requests
import time
import os
from dotenv import load_dotenv

# 1. Load the secret API Key from the .env file
load_dotenv()
THINGSPEAK_API_KEY = os.getenv("THINGSPEAK_API_KEY")
THINGSPEAK_READ_KEY = os.getenv("THINGSPEAK_READ_KEY")
THINGSPEAK_CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID")

# 2. Hardware and Cloud Configuration
SERIAL_PORT = "/dev/cu.usbmodem2201" # Update this to your Mac's specific Arduino port
BAUD_RATE = 115200
THINGSPEAK_URL = "https://api.thingspeak.com/update"
MIN_INTERVAL = 15.1  # 15.1 seconds to be perfectly safe with ThingSpeak limits

# 3. The Waiting Room
upload_queue = [] 

def calculate_and_send_master_goals(ser_conn):
    """Fetches history, applies gentle progressive overload, and transmits targets."""
    if not THINGSPEAK_READ_KEY or not THINGSPEAK_CHANNEL_ID:
        print("[Goal Engine] Missing Read Credentials in .env. Skipping goal sync.")
        return

    print("\n[Goal Engine] Fetching history to calculate progressive overload...")
    read_url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL_ID}/feeds.json?api_key={THINGSPEAK_READ_KEY}&results=10"
    
    try:
        response = requests.get(read_url)
        feeds = response.json().get('feeds', [])
        
        # Dictionary to track maxes: "ExerciseID": [MaxTotal, MaxExp, MaxCtl]
        max_stats = {
            "1": [10, 5, 5], # Default Pushup baselines
            "2": [5, 2, 3],  # Default Pullup baselines
            "3": [12, 6, 6]  # Default Squat baselines
        }
        
        for feed in feeds:
            ex_id = feed.get('field1')
            if ex_id in max_stats:
                total = int(feed.get('field2') or 0)
                exp = int(feed.get('field3') or 0)
                ctl = int(feed.get('field4') or 0)
                
                # Find their historical absolute bests
                if total > max_stats[ex_id][0]: max_stats[ex_id][0] = total
                if exp > max_stats[ex_id][1]: max_stats[ex_id][1] = exp
                if ctl > max_stats[ex_id][2]: max_stats[ex_id][2] = ctl

        # Format the Payload string
        goal_payload = "GOALS"
        for ex_id in ["1", "2", "3"]:
            target_total = max_stats[ex_id][0] + 1  # General Overload: +1 Rep
            target_exp = max_stats[ex_id][1]        # Gentle Overload: Match best explosive
            target_ctl = max_stats[ex_id][2]        # Gentle Overload: Match best steady
            
            goal_payload += f",{target_total},{target_exp},{target_ctl}"
            
        goal_payload += "\n" # Add the hidden newline character so Arduino knows to stop reading
        
        # Transmit down the wire
        ser_conn.write(goal_payload.encode('utf-8'))
        print(f"[Goal Engine] Transmission Sent: {goal_payload.strip()}")

    except Exception as e:
        print(f"[Goal Engine] Error processing history: {e}")

def main():
    if not THINGSPEAK_API_KEY:
        print("CRITICAL ERROR: No API Key found. Check your .env file.")
        return

    print(f"Connecting to Base Station on {SERIAL_PORT}...")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
        
        # --- THE TRAFFIC LIGHT HANDSHAKE ---
        print("Waiting for Arduino to fully boot...")
        
        while True:
            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if line == "ARDUINO_READY":
                    print("[Hardware] Arduino is awake and listening!")
                    break # Break out of the waiting loop!
        
        # Now that we have absolute proof the Arduino is listening, send the goals!
        calculate_and_send_master_goals(ser)
        
        last_post_time = 0.0 

        while True:
            # --- PHASE 1: CATCH THE DATA ---
            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                
                # Ignore empty lines and decorative text from the wearable
                if not line or "---" in line or line == "NO_DATA":
                    continue
                
                # Let Python print the Arduino's confirmation messages to your screen!
                if line.startswith("[BASE STATION]"):
                    print(line)
                    continue
                    
                print(f"[UART Received] {line}")

                # Verify it is our 4-part CSV format (Name, Total, Exp, Ctl)
                parts = line.split(',')
                if len(parts) == 4:
                    upload_queue.append(parts) # Put the data in the waiting room
                    print(f"   -> Added to Queue. (Items waiting: {len(upload_queue)})")

            # --- PHASE 2: UPLOAD THE DATA ---
            current_time = time.time()
            
            # If there is data waiting AND 15.1 seconds have passed since the last upload
            if len(upload_queue) > 0 and (current_time - last_post_time) >= MIN_INTERVAL:
                
                # Pull the oldest set out of the waiting room
                payload_data = upload_queue.pop(0) 
                
                exercise_name = payload_data[0]
                total_reps = payload_data[1]
                explosive = payload_data[2]
                steady = payload_data[3]
                
                # Convert string name to ThingSpeak ID
                exercise_id = 0
                if exercise_name == "Pushup": exercise_id = 1
                elif exercise_name == "Pullup": exercise_id = 2
                elif exercise_name == "Squat": exercise_id = 3
                
                # Construct the ThingSpeak URL
                request_url = (f"{THINGSPEAK_URL}?api_key={THINGSPEAK_API_KEY}"
                               f"&field1={exercise_id}&field2={total_reps}"
                               f"&field3={explosive}&field4={steady}")
                
                print(f"\n[Cloud Sync] Uploading {exercise_name} (Field 1={exercise_id}, 2={total_reps}, 3={explosive}, 4={steady})")
                
                response = requests.get(request_url)
                
                if response.status_code == 200 and response.text != "0":
                    print(f"   -> Success! (ThingSpeak Entry: {response.text})")
                    
                    # RECALCULATE NEW GOALS AFTER A SUCCESSFUL UPLOAD
                    calculate_and_send_master_goals(ser)
                    
                else:
                    print(f"   -> Error: HTTP {response.status_code}. ThingSpeak rejected the data.")
                
                # Reset the clock to enforce the next 15-second wait
                last_post_time = time.time() 

    except KeyboardInterrupt:
        print("\nShutting down Base Station connection.")
        if 'ser' in locals() and ser.is_open:
            ser.close()
    except Exception as e:
        print(f"Hardware Error: {e}")

if __name__ == "__main__":
    main()