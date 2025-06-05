import os
import requests
import time
import json
import logging
from datetime import datetime
import urllib3
from dotenv import load_dotenv

# load_dotenv()

# Disable SSL warnings since we're bypassing SSL verification for the government website
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log'),
        logging.StreamHandler()
    ]
)

class StatusMonitor:
    def __init__(self, telegram_bot_token, telegram_chat_id, target_queue_id=24):
        self.url = "https://rezerwacje.duw.pl/status_kolejek/query.php?status"
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.telegram_api_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
        self.target_queue_id = target_queue_id
        
    def fetch_status(self):
        """Fetch status from the API"""
        try:
            # Disable SSL verification for this specific government website
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive', 
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }
            response = requests.get(self.url, timeout=10, verify=False, headers=headers)
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching status: {e}")
            return None
    
    def check_conditions(self, data):
        """
        Check if there are tickets available for queue ID 2 in Wrocław
        Returns tuple: (condition_met: bool, message: str)
        """
        if not data:
            return False, ""
        
        try:
            # Navigate to result -> Wrocław array
            if 'result' not in data or 'Wrocław' not in data['result']:
                logging.warning("Expected structure not found in API response")
                return False, ""
            
            wroclaw_queues = data['result']['Wrocław']
            
            # Find queue with target ID
            target_queue = None
            for queue in wroclaw_queues:
                if queue.get('id') == self.target_queue_id:
                    target_queue = queue
                    break
            
            if not target_queue:
                logging.warning(f"Queue with ID {self.target_queue_id} not found in Wrocław")
                return False, ""
            
            # Check if ticket_count > 0
            ticket_count = target_queue.get('ticket_count', 0)
            queue_name = target_queue.get('name', 'Unknown Queue')
            
            if ticket_count > 0:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message = f"🎫 Currently there are {ticket_count} tickets available for '{queue_name}' at {current_time}"
                return True, message
            else:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message = f"🎫 Currently there are {ticket_count} tickets available for '{queue_name}' at {current_time}"
                return True, message
            
            # Log current status for debugging
            logging.info(f"Queue ID {self.target_queue_id} ('{queue_name}'): {ticket_count} tickets available")
            return False, ""
            
        except Exception as e:
            logging.error(f"Error checking conditions: {e}")
            return False, ""
    
    def send_telegram_message(self, message):
        """Send message to Telegram"""
        try:
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(self.telegram_api_url, data=payload, timeout=10)
            response.raise_for_status()
            logging.info("Message sent to Telegram successfully")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending Telegram message: {e}")
            return False
    
    def run_check(self):
        """Run a single check"""
        logging.info("Starting status check...")
        
        # Fetch data
        data = self.fetch_status()
        if data is None:
            logging.warning("No data received")
            return
        
        # Log the received data (for debugging)
        logging.info(f"Received data: {json.dumps(data)[:200]}...")
        
        # Check conditions
        condition_met, alert_message = self.check_conditions(data)
        
        if condition_met:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            full_message = f"🚨 <b>Status Alert</b> 🚨\n\n{alert_message}\n\n<i>Time: {timestamp}</i>"
            
            if self.send_telegram_message(full_message):
                logging.info(f"Alert sent: {alert_message}")
            else:
                logging.error("Failed to send alert")
        else:
            logging.info("No alert conditions met")
    
    def run_monitor(self, interval_minutes=5):
        """Run continuous monitoring"""
        logging.info(f"Starting continuous monitoring (every {interval_minutes} minutes)")
        
        while True:
            try:
                self.run_check()
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                logging.info("Monitoring stopped by user")
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

def main():
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')  # Get from @BotFather
    print(f"Bot token loaded: {'Yes' if TELEGRAM_BOT_TOKEN else 'No'}")
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')     # Your Telegram chat ID
    print(f"TELEGRAM_CHAT_ID loaded: {'Yes' if TELEGRAM_CHAT_ID else 'No'}")
    
    # Validate configuration
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or TELEGRAM_CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("❌ Please configure your Telegram bot token and chat ID first!")
        print("\nSteps to set up:")
        print("1. Create a bot with @BotFather on Telegram")
        print("2. Get your chat ID by messaging @userinfobot")
        print("3. Replace the placeholders in this script")
        return
    
    # Create and run monitor
    monitor = StatusMonitor(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    
    # Test the connection first
    test_message = "✅ Status monitor started successfully!"
    if monitor.send_telegram_message(test_message):
        print("✅ Telegram connection test successful!")
        monitor.run_monitor(interval_minutes=5)
    else:
        print("❌ Telegram connection test failed. Check your configuration.")

if __name__ == "__main__":
    main()