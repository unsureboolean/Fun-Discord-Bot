import unittest
import sys
import os
sys.path.append('./src')

class TestDatabaseModule(unittest.TestCase):
    def setUp(self):
        from database import Database
        self.db = Database(':memory:')  # Use in-memory database for testing
    
    def test_server_data(self):
        # Test server data storage and retrieval
        self.db.update_server_persona('test_guild_1', 'homer_simpson')
        server_data = self.db.get_server_data('test_guild_1', 'general_brasch')
        self.assertEqual(server_data['persona'], 'homer_simpson')
    
    def test_message_storage(self):
        # Test message storage and retrieval
        self.db.store_message('test_guild_1', 'test_channel_1', 'user', 'test_user', 'Hello world')
        self.db.store_message('test_guild_1', 'test_channel_1', 'assistant', None, 'Hi there')
        messages = self.db.get_message_history('test_guild_1', 'test_channel_1', 10)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['content'], 'Hello world')
        self.assertEqual(messages[1]['content'], 'Hi there')
    
    def tearDown(self):
        self.db.close()

class TestRateLimitingModule(unittest.TestCase):
    def test_rate_limiting(self):
        from rate_limiting import RateLimitType, rate_limiter
        
        user_id = 'test_user_1'
        guild_id = 'test_guild_1'
        
        # Should not be rate limited initially
        is_limited, wait_time, limit_info = rate_limiter.is_rate_limited(RateLimitType.MESSAGE, user_id, guild_id)
        self.assertFalse(is_limited)
        
        # Add multiple requests
        for i in range(15):  # Default limit is 10 per 60 seconds
            rate_limiter.add_request(RateLimitType.MESSAGE, user_id, guild_id)
        
        # Should be rate limited now
        is_limited, wait_time, limit_info = rate_limiter.is_rate_limited(RateLimitType.MESSAGE, user_id, guild_id)
        self.assertTrue(is_limited)

class TestLoggerModule(unittest.TestCase):
    def setUp(self):
        # Create test directory
        os.makedirs('test_logs', exist_ok=True)
    
    def test_logger_creation(self):
        from logger import BotLogger
        logger = BotLogger(log_dir='test_logs')
        
        # Test logging functions
        logger.info('Test info message')
        logger.warning('Test warning message')
        logger.error('Test error message')
        logger.log_command('test_command', 'test_user', 'test_guild', 'test_channel', True)
        logger.log_api_call('test_api', {'param': 'value'}, True)
        
        # Check if log files were created
        self.assertTrue(os.path.exists('test_logs/bot.log'))
        self.assertTrue(os.path.exists('test_logs/error.log'))
    
    def tearDown(self):
        # Clean up test files
        if os.path.exists('test_logs'):
            for file in os.listdir('test_logs'):
                os.remove(os.path.join('test_logs', file))
            os.rmdir('test_logs')

if __name__ == '__main__':
    unittest.main()
