
from app import app, db
from models import MarketAlarmLog
from weather_alerts import weather_alert_system
import logging

# Configure logger to print to stdout
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('weather_alerts')
logger.setLevel(logging.DEBUG)

def check_logs():
    print("\n=== Recent Market Alarm Logs ===")
    with app.app_context():
        logs = MarketAlarmLog.query.order_by(MarketAlarmLog.created_at.desc()).limit(10).all()
        if not logs:
            print("No logs found.")
        for log in logs:
            print(f"[{log.created_at}] MARKET: {log.market.name if log.market else 'Unknown'} | TYPE: {log.alert_type} | TITLE: {log.alert_title}")

def debug_alert_check():
    print("\n=== Running Manual Alert Check ===")
    # Force run check
    with app.app_context():
        # Temporarily override deduplication to see if that's the blocker?
        # actually, let's just see what it returns first.
        result = weather_alert_system.check_all_markets_with_all_conditions(hours=24)
        print(f"\nResult: {result}")
        
        # Check specific market logic?
        # We can introspect weather_alert_system logic by adding debug prints if needed, 
        # but let's trust the logger first. 

if __name__ == "__main__":
    check_logs()
    debug_alert_check()
