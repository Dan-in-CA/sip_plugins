import sys
import os
import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open, ANY
from time import sleep
# This will stub sip and pi-specific things out
from ssd1306_test_base import Ssd1306CustomAssertions
# Now that things have been stubbed out, ssd1306 may be imported
from ssd1306 import LcdPlugin, Screen
import ssd1306

# Make sure the plugin thread stops right away
ssd1306.lcd_plugin.stop()

class LcdPluginTestCase(unittest.TestCase):
    @classmethod
    def setUp(cls):
        with patch('ssd1306.Screen', return_value=Mock()):
            cls.lcd_plugin = LcdPlugin()

    @classmethod
    def tearDown(cls):
        pass

class TestLcdPlugin___init__(LcdPluginTestCase):
    def test_nominal(self):
        # Make sure all of the necessary data is created
        self.assertIn('_state_screen', self.lcd_plugin.__dict__)
        self.assertIn('_last_idle_state', self.lcd_plugin.__dict__)
        self.assertIn('_idle_entry_time', self.lcd_plugin.__dict__)
        self.assertIn('_idled', self.lcd_plugin.__dict__)
        self.assertIn('_lcd', self.lcd_plugin.__dict__)
        self.assertIn('_running', self.lcd_plugin.__dict__)
        self.assertIn('_idle_lock', self.lcd_plugin.__dict__)
        self.assertIn('_idle_timeout_seconds', self.lcd_plugin.__dict__)
        self.assertIn('_lcd_hw_address', self.lcd_plugin.__dict__)
        self.assertIn('_display_condition', self.lcd_plugin.__dict__)
        self.assertIn('_notify_display_sem', self.lcd_plugin.__dict__)
        self.assertIn('_notify_display_thread', self.lcd_plugin.__dict__)
        self.assertIn('_custom_display_lock', self.lcd_plugin.__dict__)
        self.assertIn('_custom_display_queue', self.lcd_plugin.__dict__)
        self.assertIn('_custom_screens', self.lcd_plugin.__dict__)
        self.assertIn('_custom_screens_stack', self.lcd_plugin.__dict__)

class TestLcdPlugin__reset_lcd_state(LcdPluginTestCase):
    def test_nominal(self):
        self.lcd_plugin._state_screen.clear = MagicMock()
        self.lcd_plugin._last_idle_state = u"something something"
        self.lcd_plugin._idle_entry_time = 123
        self.lcd_plugin._idled = True
        self.lcd_plugin._reset_lcd_state()
        self.assertEqual(1, self.lcd_plugin._state_screen.clear.call_count)
        self.assertEqual(u"", self.lcd_plugin._last_idle_state)
        self.assertEqual(None, self.lcd_plugin._idle_entry_time)
        self.assertFalse(self.lcd_plugin._idled)

class TestLcdPlugin_initialize(LcdPluginTestCase):
    def test_no_load_settings(self):
        self.assertEqual(None, self.lcd_plugin._lcd)
        with patch('ssd1306.Lcd', autospec=True):
            self.lcd_plugin.initialize(load_settings=False)
        self.assertNotEqual(None, self.lcd_plugin._lcd)
        self.assertEqual(1, self.lcd_plugin._lcd.write_initialization_sequence.call_count)

    def test_load_settings(self):
        with patch('ssd1306.Lcd', autospec=True), patch('ssd1306.LcdPlugin._load_settings') as mocked_load_settings:
            self.lcd_plugin.initialize(load_settings=True)
        self.assertEqual(1, mocked_load_settings.call_count)

class TestLcdPlugin__set_default_settings(LcdPluginTestCase):
    def test_nominal(self):
        self.lcd_plugin._idle_timeout_seconds = None
        self.lcd_plugin._lcd_hw_address = None
        self.lcd_plugin._set_default_settings()
        # Just make sure these are set to some integer
        self.assertIsInstance(self.lcd_plugin._idle_timeout_seconds, int)
        self.assertIsInstance(self.lcd_plugin._lcd_hw_address, int)

class TestLcdPlugin_load_from_dict(LcdPluginTestCase):
    def test_no_settings(self):
        self.lcd_plugin._lcd = Mock()
        self.lcd_plugin._lcd.set_power = MagicMock()
        self.lcd_plugin._idle_timeout_seconds = None
        self.lcd_plugin._lcd_hw_address = None
        with patch('ssd1306.Lcd', autospec=True):
            self.lcd_plugin.load_from_dict(None, allow_reinit=True)
        self.assertIsNone(self.lcd_plugin._idle_timeout_seconds)
        self.assertIsNone(self.lcd_plugin._lcd_hw_address)
        self.assertEqual(0, self.lcd_plugin._lcd.set_power.call_count)

    def test_empty_dict(self):
        self.lcd_plugin._lcd = Mock()
        self.lcd_plugin._lcd.set_power = MagicMock()
        self.lcd_plugin._idle_timeout_seconds = None
        self.lcd_plugin._lcd_hw_address = None
        with patch('ssd1306.Lcd', autospec=True):
            self.lcd_plugin.load_from_dict({}, allow_reinit=True)
        self.assertIsNone(self.lcd_plugin._idle_timeout_seconds)
        self.assertIsNone(self.lcd_plugin._lcd_hw_address)
        self.assertEqual(0, self.lcd_plugin._lcd.set_power.call_count)

    def test_set_all_allow_reinit(self):
        self.lcd_plugin._lcd = Mock()
        self.lcd_plugin._lcd.set_power = MagicMock()
        original_lcd = self.lcd_plugin._lcd
        self.lcd_plugin._idle_timeout_seconds = None
        self.lcd_plugin._lcd_hw_address = None
        with patch('ssd1306.Lcd', autospec=True):
            self.lcd_plugin.load_from_dict({
                u"idle_timeout": u"123",
                u"i2c_hw_address": u"FF"
            }, allow_reinit=True)
        self.assertEqual(123, self.lcd_plugin._idle_timeout_seconds)
        self.assertEqual(0xFF, self.lcd_plugin._lcd_hw_address)
        self.assertEqual(1, original_lcd.set_power.call_count)
        self.assertIsNot(original_lcd, self.lcd_plugin._lcd)

    def test_set_all_no_allow_reinit(self):
        self.lcd_plugin._lcd = Mock()
        self.lcd_plugin._lcd.set_power = MagicMock()
        self.lcd_plugin._idle_timeout_seconds = None
        self.lcd_plugin._lcd_hw_address = None
        with patch('ssd1306.Lcd', autospec=True):
            self.lcd_plugin.load_from_dict({
                u"idle_timeout": u"123",
                u"i2c_hw_address": u"FF"
            }, allow_reinit=False)
        self.assertEqual(123, self.lcd_plugin._idle_timeout_seconds)
        self.assertEqual(0xFF, self.lcd_plugin._lcd_hw_address)
        self.assertEqual(0, self.lcd_plugin._lcd.set_power.call_count)

class TestLcdPlugin__load_settings(LcdPluginTestCase):
    def test_load_empty(self):
        self.lcd_plugin._idle_timeout_seconds = None
        self.lcd_plugin._lcd_hw_address = None
        file_data = '{}'
        with patch('builtins.open', new_callable=mock_open, read_data=file_data):
            self.lcd_plugin._load_settings()
        # These should remain None
        self.assertIsNone(self.lcd_plugin._idle_timeout_seconds)
        self.assertIsNone(self.lcd_plugin._lcd_hw_address)

    def test_load_exception(self):
        self.lcd_plugin._idle_timeout_seconds = None
        self.lcd_plugin._lcd_hw_address = None
        with patch('builtins.open', side_effect=Exception()):
            self.lcd_plugin._load_settings()
        # Defaults should have been set
        self.assertIsNotNone(self.lcd_plugin._idle_timeout_seconds)
        self.assertIsNotNone(self.lcd_plugin._lcd_hw_address)

class TestLcdPlugin_save_settings(LcdPluginTestCase):
    def test_nominal(self):
        self.lcd_plugin._idle_timeout_seconds = 9292
        self.lcd_plugin._lcd_hw_address = 0x9a
        with patch('builtins.open', new_callable=mock_open),\
            patch('ssd1306.json.dump') as mocked_json_dump\
        :
            self.lcd_plugin.save_settings()
        mocked_json_dump.assert_called_with({
            u"idle_timeout": 9292,
            u"i2c_hw_address": "9a"
        }, ANY)

class TestLcdPlugin__get_time_string(LcdPluginTestCase):
    def test_24hr_time(self):
        mocked_nowt = Mock()
        mocked_nowt.tm_hour = 22
        mocked_nowt.tm_min = 42
        with patch('ssd1306.SipGlobals.get_now_time', return_value=mocked_nowt),\
            patch('ssd1306.SipGlobals.is_24hr_time_format', return_value=True)\
        :
            time_str = LcdPlugin._get_time_string()
        self.assertEqual(u"22:42", time_str)

    def test_12hr_time(self):
        mocked_nowt = Mock()
        mocked_nowt.tm_hour = 22
        mocked_nowt.tm_min = 42
        with patch('ssd1306.SipGlobals.get_now_time', return_value=mocked_nowt),\
            patch('ssd1306.SipGlobals.is_24hr_time_format', return_value=False)\
        :
            time_str = LcdPlugin._get_time_string()
        self.assertEqual(u"10:42 PM", time_str)

class TestLcdPlugin__time_to_string(LcdPluginTestCase):
    def test_less_than_hour(self):
        time_str = LcdPlugin._time_to_string(3599.99)
        self.assertEqual(u"59:59", time_str)
    def test_greater_than_hour(self):
        time_str = LcdPlugin._time_to_string(4000)
        self.assertEqual(u"01:06:40", time_str)

class TestLcdPlugin__wake_display(LcdPluginTestCase):
    def test_wake_from_idle(self):
        self.lcd_plugin._last_idle_state = None
        self.lcd_plugin._idled = True
        self.lcd_plugin._lcd = Mock()
        self.lcd_plugin._lcd.set_power = MagicMock()
        with patch('ssd1306.time.time', return_value=9393):
            self.lcd_plugin._wake_display()
        self.assertEqual(9393, self.lcd_plugin._idle_entry_time)
        self.lcd_plugin._lcd.set_power.assert_called_with(on=True)
        self.assertFalse(self.lcd_plugin._idled)
        self.assertEqual(u"", self.lcd_plugin._last_idle_state)

    def test_no_wake(self):
        self.lcd_plugin._last_idle_state = None
        self.lcd_plugin._idled = False
        self.lcd_plugin._lcd = Mock()
        self.lcd_plugin._lcd.set_power = MagicMock()
        with patch('ssd1306.time.time', return_value=9393):
            self.lcd_plugin._wake_display()
        self.assertEqual(9393, self.lcd_plugin._idle_entry_time)
        self.assertEqual(0, self.lcd_plugin._lcd.set_power.call_count)
        self.assertFalse(self.lcd_plugin._idled)
        self.assertIs(None, self.lcd_plugin._last_idle_state)

# To test the rest of the plugin, test it as a component
class TestLcdPluginComponent(unittest.TestCase, Ssd1306CustomAssertions):
    @classmethod
    def setUp(cls):
        cls.original_startup_delay = ssd1306.STARTUP_DELAY
        cls.original_normal_refresh_period = ssd1306.NORMAL_REFRESH_PERIOD
        ssd1306.STARTUP_DELAY = 0
        ssd1306.NORMAL_REFRESH_PERIOD = 0.1

    @classmethod
    def tearDown(cls):
        ssd1306.STARTUP_DELAY = cls.original_startup_delay
        ssd1306.NORMAL_REFRESH_PERIOD = cls.original_normal_refresh_period

    @patch('ssd1306.smbus.SMBus', autospec=True)
    def test_all(self, mocked_lcd):
        mocked_time = Mock()
        mocked_time.tm_hour = 13
        mocked_time.tm_min = 36
        with patch('ssd1306.SipGlobals.get_now_time', return_value=mocked_time),\
            patch('ssd1306.SipGlobals.get_now', return_value=9876),\
            patch('ssd1306.SipGlobals.is_24hr_time_format', return_value=False),\
            patch('ssd1306.SipGlobals.is_idle', return_value=True) as mocked_is_idle,\
            patch('ssd1306.SipGlobals.get_running_program', return_value=None),\
            patch('ssd1306.SipGlobals.is_enabled', return_value=True),\
            patch('ssd1306.SipGlobals.is_manual_mode_enabled', return_value=False),\
            patch('ssd1306.SipGlobals.is_rain_delay_set', return_value=False),\
            patch('ssd1306.SipGlobals.get_rain_delay_end_time', return_value=None),\
            patch('ssd1306.SipGlobals.get_water_level', return_value=99) as mocked_water_level,\
            patch('ssd1306.SipGlobals.get_running_stations', return_value=[]) as mocked_get_running_stations,\
            patch('ssd1306.SipGlobals.is_runonce_program_running', return_value=False),\
            patch('ssd1306.SipGlobals.is_manual_mode_program_running', return_value=False),\
            patch('ssd1306.Lcd.set_power') as mocked_lcd_set_power\
        :
            lcd_plugin = LcdPlugin()
            try:
                lcd_plugin.initialize(load_settings=False)
                lcd_plugin._idle_timeout_seconds = 0.5
                lcd_plugin.start()
                sleep(1) # 1 second is probably long enough to get things displayed
                # LCD Plugin thread should now be running with mocked I2C bus
                # Now displaying Idle, 99%, 1:36 PM
                expected_data =\
                    [
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 7, 7, 255, 255, 255, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 192, 192, 192, 192, 192, 0, 0, 0, 255, 255, 255, 0, 0, 0, 0, 0, 0, 7, 7, 7, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 192, 192, 192, 192, 192, 192, 192, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 254, 254, 254, 1, 1, 1, 1, 1, 1, 14, 14, 14, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 254, 254, 254, 113, 113, 113, 113, 113, 113, 113, 113, 113, 126, 126, 126, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 28, 28, 28, 31, 31, 31, 28, 28, 28, 0, 0, 0, 0, 0, 0, 3, 3, 3, 28, 28, 28, 28, 28, 28, 28, 28, 28, 31, 31, 31, 0, 0, 0, 0, 0, 0, 28, 28, 28, 31, 31, 31, 28, 28, 28, 0, 0, 0, 0, 0, 0, 3, 3, 3, 28, 28, 28, 28, 28, 28, 28, 28, 28, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 60, 60, 195, 195, 195, 195, 195, 195, 252, 252, 0, 0, 60, 60, 195, 195, 195, 195, 195, 195, 252, 252, 0, 0, 15, 15, 15, 15, 192, 192, 48, 48, 12, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 48, 48, 12, 12, 3, 3, 0, 0, 0, 0, 48, 48, 48, 48, 12, 12, 3, 3, 0, 0, 12, 12, 3, 3, 0, 0, 60, 60, 60, 60, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 12, 12, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 60, 60, 60, 60, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 51, 51, 207, 207, 3, 3, 0, 0, 240, 240, 204, 204, 195, 195, 195, 195, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 195, 195, 195, 195, 195, 195, 60, 60, 0, 0, 255, 255, 12, 12, 48, 48, 12, 12, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 63, 63, 48, 48, 0, 0, 0, 0, 0, 0, 15, 15, 15, 15, 0, 0, 0, 0, 0, 0, 12, 12, 48, 48, 48, 48, 48, 48, 15, 15, 0, 0, 15, 15, 48, 48, 48, 48, 48, 48, 15, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 63, 63, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 63, 63, 0, 0, 0, 0, 0, 0, 63, 63, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                    ]
                self.assertScreenBytes(expected_data, lcd_plugin._lcd._screen)
                # With idle timeout set as 0.5, the power should have been shut off
                mocked_lcd_set_power.assert_called_with(on=False)
                # Changing water level should turn the screen back on with next refresh
                mocked_water_level.return_value = 100
                sleep(0.25)
                mocked_lcd_set_power.assert_called_with(on=True)
                # Now displaying Idle, no water level, 1:36 PM
                expected_data =\
                    [
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 7, 7, 255, 255, 255, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 192, 192, 192, 192, 192, 0, 0, 0, 255, 255, 255, 0, 0, 0, 0, 0, 0, 7, 7, 7, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 192, 192, 192, 192, 192, 192, 192, 192, 192, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 254, 254, 254, 1, 1, 1, 1, 1, 1, 14, 14, 14, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 254, 254, 254, 113, 113, 113, 113, 113, 113, 113, 113, 113, 126, 126, 126, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 28, 28, 28, 31, 31, 31, 28, 28, 28, 0, 0, 0, 0, 0, 0, 3, 3, 3, 28, 28, 28, 28, 28, 28, 28, 28, 28, 31, 31, 31, 0, 0, 0, 0, 0, 0, 28, 28, 28, 31, 31, 31, 28, 28, 28, 0, 0, 0, 0, 0, 0, 3, 3, 3, 28, 28, 28, 28, 28, 28, 28, 28, 28, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 12, 12, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 60, 60, 60, 60, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 51, 51, 207, 207, 3, 3, 0, 0, 240, 240, 204, 204, 195, 195, 195, 195, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 195, 195, 195, 195, 195, 195, 60, 60, 0, 0, 255, 255, 12, 12, 48, 48, 12, 12, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 63, 63, 48, 48, 0, 0, 0, 0, 0, 0, 15, 15, 15, 15, 0, 0, 0, 0, 0, 0, 12, 12, 48, 48, 48, 48, 48, 48, 15, 15, 0, 0, 15, 15, 48, 48, 48, 48, 48, 48, 15, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 63, 63, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 63, 63, 0, 0, 0, 0, 0, 0, 63, 63, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                    ]
                self.assertScreenBytes(expected_data, lcd_plugin._lcd._screen)
                # Wait for display to go back to sleep
                sleep(1)
                mocked_lcd_set_power.assert_called_with(on=False)
                # External wake
                lcd_plugin.wake_signal()
                sleep(0.25)
                mocked_lcd_set_power.assert_called_with(on=True)
                # External sleep
                lcd_plugin.sleep_signal()
                sleep(0.25)
                mocked_lcd_set_power.assert_called_with(on=False)
                # External displays
                lcd_plugin.display_signal(
                    activator="my_plugin1",
                    screen_id="1",
                    txt="some text",
                    row_start=1,
                    col_end=120,
                    text_size=1,
                    justification="RIGHT",
                    append=False,
                    delay=None,
                    wake=True
                )
                lcd_plugin.display_signal(
                    activator="my_plugin1",
                    screen_id="1",
                    txt="Rock and roll!",
                    row_start=3,
                    text_size=1,
                    justification="CENTER",
                    append=True,
                    delay=None,
                    wake=True
                )
                sleep(0.25)
                # The above custom display should be shown
                expected_data =\
                    [
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 72, 84, 84, 84, 32, 0, 56, 68, 68, 68, 56, 0, 124, 4, 24, 4, 120, 0, 56, 84, 84, 84, 24, 0, 0, 0, 0, 0, 0, 0, 4, 63, 68, 64, 32, 0, 56, 84, 84, 84, 24, 0, 68, 40, 16, 40, 68, 0, 4, 63, 68, 64, 32, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 127, 9, 25, 41, 70, 0, 56, 68, 68, 68, 56, 0, 56, 68, 68, 68, 32, 0, 0, 127, 16, 40, 68, 0, 0, 0, 0, 0, 0, 0, 32, 84, 84, 84, 120, 0, 124, 8, 4, 4, 120, 0, 56, 68, 68, 72, 127, 0, 0, 0, 0, 0, 0, 0, 124, 8, 4, 4, 8, 0, 56, 68, 68, 68, 56, 0, 0, 65, 127, 64, 0, 0, 0, 65, 127, 64, 0, 0, 0, 0, 95, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                    ]
                my_plugin_1_screen = expected_data
                self.assertScreenBytes(expected_data, lcd_plugin._lcd._screen)
                # Another plugin comes in and displays something...
                lcd_plugin.display_signal(
                    activator="my_plugin2",
                    screen_id="1",
                    txt="ABCDEFG",
                    row_start=2,
                    text_size=2,
                    justification="LEFT",
                    append=True,
                    delay=None,
                    wake=True
                )
                lcd_plugin.display_signal(
                    activator="my_plugin2",
                    screen_id="2",
                    txt="ZYXWV",
                    row_start=4,
                    text_size=2,
                    justification="LEFT",
                    append=True,
                    delay=None,
                    wake=True
                )
                sleep(0.25)
                # Only ZYXWV should be shown
                expected_data = \
                    [
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([3, 3, 3, 3, 195, 195, 51, 51, 15, 15, 0, 0, 15, 15, 48, 48, 192, 192, 48, 48, 15, 15, 0, 0, 15, 15, 48, 48, 192, 192, 48, 48, 15, 15, 0, 0, 255, 255, 0, 0, 192, 192, 0, 0, 255, 255, 0, 0, 255, 255, 0, 0, 0, 0, 0, 0, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([60, 60, 51, 51, 48, 48, 48, 48, 48, 48, 0, 0, 0, 0, 0, 0, 63, 63, 0, 0, 0, 0, 0, 0, 60, 60, 3, 3, 0, 0, 3, 3, 60, 60, 0, 0, 63, 63, 12, 12, 3, 3, 12, 12, 63, 63, 0, 0, 3, 3, 12, 12, 48, 48, 12, 12, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                    ]
                self.assertScreenBytes(expected_data, lcd_plugin._lcd._screen)
                # Cancelling screen which is not displayed should have no effect
                lcd_plugin.display_signal(
                    activator="my_plugin2",
                    screen_id="1",
                    cancel=True
                )
                sleep(0.25)
                self.assertScreenBytes(expected_data, lcd_plugin._lcd._screen)
                # Cancelling this screen should show the screen from plugin1
                lcd_plugin.display_signal(
                    activator="my_plugin2",
                    screen_id="2",
                    cancel=True
                )
                sleep(0.25)
                self.assertScreenBytes(my_plugin_1_screen, lcd_plugin._lcd._screen)
                # Setup state before cancelling last custom display...
                mocked_is_idle.return_value = False
                mocked_get_running_stations.return_value = (True, 239, [303]) # station 303 is running for 239 seconds
                # Cancel last custom screen
                lcd_plugin.display_signal(
                    activator="my_plugin1",
                    screen_id="1",
                    cancel=True
                )
                sleep(0.25)
                # Station 303 to be running for 3 minutes, 59 sec
                expected_data =\
                    [
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 255, 255, 255, 255, 255, 31, 31, 31, 31, 31, 0, 0, 0, 0, 0, 224, 224, 224, 224, 224, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 224, 224, 224, 224, 224, 0, 0, 0, 0, 0, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 255, 255, 255, 255, 255, 31, 31, 31, 31, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 124, 124, 124, 124, 124, 131, 131, 131, 131, 131, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 0, 0, 0, 0, 0, 128, 128, 128, 128, 128, 124, 124, 124, 124, 124, 255, 255, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 124, 124, 124, 124, 124, 131, 131, 131, 131, 131, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15, 15, 15, 15, 15, 240, 240, 240, 240, 240, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 240, 240, 240, 240, 240, 15, 15, 15, 15, 15, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15, 15, 15, 15, 15, 240, 240, 240, 240, 240, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 62, 62, 62, 62, 62, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 63, 63, 63, 63, 63, 0, 0, 0, 0, 0, 63, 63, 63, 63, 63, 193, 193, 193, 193, 193, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 63, 63, 63, 63, 63, 0, 0, 0, 0, 0, 62, 62, 62, 62, 62, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 63, 63, 63, 63, 63, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 252, 252, 3, 3, 195, 195, 51, 51, 252, 252, 0, 0, 3, 3, 3, 3, 51, 51, 207, 207, 3, 3, 0, 0, 0, 0, 60, 60, 60, 60, 0, 0, 0, 0, 0, 0, 63, 63, 51, 51, 51, 51, 51, 51, 195, 195, 0, 0, 60, 60, 195, 195, 195, 195, 195, 195, 252, 252, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15, 15, 51, 51, 48, 48, 48, 48, 15, 15, 0, 0, 12, 12, 48, 48, 48, 48, 48, 48, 15, 15, 0, 0, 0, 0, 15, 15, 15, 15, 0, 0, 0, 0, 0, 0, 12, 12, 48, 48, 48, 48, 48, 48, 15, 15, 0, 0, 0, 0, 48, 48, 48, 48, 12, 12, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                    ]
                self.assertScreenBytes(expected_data, lcd_plugin._lcd._screen)
                # Plugin1 shows a screen for a limited amount of time
                lcd_plugin.display_signal(
                    activator="my_plugin1",
                    screen_id="1",
                    txt="876",
                    row_start=4,
                    col_end=120,
                    text_size=2,
                    justification="CENTER",
                    append=False,
                    delay=0.5,
                    wake=True
                )
                sleep(0.25)
                expected_data =\
                    [
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 60, 60, 195, 195, 195, 195, 195, 195, 60, 60, 0, 0, 3, 3, 3, 3, 195, 195, 51, 51, 15, 15, 0, 0, 240, 240, 204, 204, 195, 195, 195, 195, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15, 15, 48, 48, 48, 48, 48, 48, 15, 15, 0, 0, 0, 0, 63, 63, 0, 0, 0, 0, 0, 0, 0, 0, 15, 15, 48, 48, 48, 48, 48, 48, 15, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                    ]
                self.assertScreenBytes(expected_data, lcd_plugin._lcd._screen)
                # Update running time
                mocked_get_running_stations.return_value = (True, 237, [303]) # station 303 is running for 239 seconds
                sleep(1)
                # Normal display should be shown now
                expected_data =\
                    [
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 255, 255, 255, 255, 255, 31, 31, 31, 31, 31, 0, 0, 0, 0, 0, 224, 224, 224, 224, 224, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 224, 224, 224, 224, 224, 0, 0, 0, 0, 0, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 255, 255, 255, 255, 255, 31, 31, 31, 31, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 124, 124, 124, 124, 124, 131, 131, 131, 131, 131, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 0, 0, 0, 0, 0, 128, 128, 128, 128, 128, 124, 124, 124, 124, 124, 255, 255, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 124, 124, 124, 124, 124, 131, 131, 131, 131, 131, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15, 15, 15, 15, 15, 240, 240, 240, 240, 240, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 240, 240, 240, 240, 240, 15, 15, 15, 15, 15, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15, 15, 15, 15, 15, 240, 240, 240, 240, 240, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 62, 62, 62, 62, 62, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 63, 63, 63, 63, 63, 0, 0, 0, 0, 0, 63, 63, 63, 63, 63, 193, 193, 193, 193, 193, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 63, 63, 63, 63, 63, 0, 0, 0, 0, 0, 62, 62, 62, 62, 62, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 192, 63, 63, 63, 63, 63, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 252, 252, 3, 3, 195, 195, 51, 51, 252, 252, 0, 0, 3, 3, 3, 3, 51, 51, 207, 207, 3, 3, 0, 0, 0, 0, 60, 60, 60, 60, 0, 0, 0, 0, 0, 0, 63, 63, 51, 51, 51, 51, 51, 51, 195, 195, 0, 0, 3, 3, 3, 3, 195, 195, 51, 51, 15, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                        bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15, 15, 51, 51, 48, 48, 48, 48, 15, 15, 0, 0, 12, 12, 48, 48, 48, 48, 48, 48, 15, 15, 0, 0, 0, 0, 15, 15, 15, 15, 0, 0, 0, 0, 0, 0, 12, 12, 48, 48, 48, 48, 48, 48, 15, 15, 0, 0, 0, 0, 63, 63, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
                    ]
                self.assertScreenBytes(expected_data, lcd_plugin._lcd._screen)
            finally:
                lcd_plugin.stop()



