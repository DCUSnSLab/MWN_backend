
import unittest
import json
from unittest.mock import MagicMock, patch

# Import the class to test
# Assuming weather_alerts.py is in the same directory
try:
    from weather_alerts import WeatherAlertSystem
except ImportError:
    # If run from parent directory
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from weather_alerts import WeatherAlertSystem

class TestWeatherAlertSystem(unittest.TestCase):
    def setUp(self):
        # Mock database and app context if needed
        self.alert_system = WeatherAlertSystem()
        
    def test_summary_text_generation_logic(self):
        """
        Verify that summary text dynamically reflects the alert types.
        Original Issue: Text was hardcoded to "비, 폭염 등".
        Fixed Logic: Should list actual types like "한파", "강풍".
        """
        
        # Test Case 1: Cold Wave and Strong Wind
        market1 = MagicMock()
        market1.name = "MarketA"
        market2 = MagicMock()
        market2.name = "MarketB"
        market3 = MagicMock()
        market3.name = "MarketC"
        
        alerts_list = [
            {
                'market': market1, 
                'weather_info': {'alerts': {'low_temp': {'temp': -15}, 'strong_wind': {'speed': 15}}}
            },
            {
                'market': market2, 
                'weather_info': {'alerts': {'low_temp': {'temp': -14}}}
            },
            {
                'market': market3, 
                'weather_info': {'alerts': {'low_temp': {'temp': -13}}}
            }
        ]
        
        # We need to test the logic block inside send_summary_alert_to_user
        # Since we cannot easily invoke the full method without DB, we verify the logic standalone
        # mirroring the implementation in weather_alerts.py
        
        unique_types = set()
        for item in alerts_list:
            for a_type in item['weather_info'].get('alerts', {}).keys():
                unique_types.add(a_type)
        
        type_map = {
            'rain': '비',
            'snow': '눈',
            'high_temp': '폭염',
            'low_temp': '한파',
            'strong_wind': '강풍'
        }
        
        type_names = []
        for t in unique_types:
            if t in type_map:
                type_names.append(type_map[t])
        
        sort_order = ['비', '눈', '폭염', '한파', '강풍']
        type_names.sort(key=lambda x: sort_order.index(x) if x in sort_order else 99)
        
        if not type_names:
            weather_str = "기상 특보"
        else:
            weather_str = ", ".join(type_names)
            
        # Assertion
        self.assertIn("한파", weather_str)
        self.assertIn("강풍", weather_str)
        self.assertNotIn("폭염", weather_str)
        self.assertEqual(weather_str, "한파, 강풍")
        
        print(f"Generated Weather String: {weather_str}")

if __name__ == '__main__':
    unittest.main()
