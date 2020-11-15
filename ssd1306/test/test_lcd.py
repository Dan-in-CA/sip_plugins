import sys
import os
import unittest
from unittest.mock import Mock, MagicMock, patch, call, ANY
# This will stub sip and pi-specific things out
import ssd1306_test_base
# Now that things have been stubbed out, ssd1306 may be imported
from ssd1306 import Lcd, Screen, JUSTIFY_LEFT, JUSTIFY_RIGHT, JUSTIFY_CENTER
import ssd1306

# Make sure the plugin thread stops right away
ssd1306.lcd_plugin.stop()

class LcdTestCase(unittest.TestCase):
    @classmethod
    def setUp(cls):
        with patch('ssd1306.smbus.SMBus', return_value=Mock()) as mocked_smbus,\
            patch('ssd1306.Screen', return_value=Mock()) as mocked_screen\
        :
            cls.mocked_smbus = mocked_smbus
            cls.mocked_smbus_instance = mocked_smbus.return_value
            cls.mocked_screen = mocked_screen
            cls.mocked_screen_instance = mocked_screen.return_value
            cls.lcd = Lcd()

    @classmethod
    def tearDown(cls):
        pass

    def test_is_powered(self):
        self.lcd._power_state = True
        self.assertTrue(self.lcd.is_powered())
        self.lcd._power_state = False
        self.assertFalse(self.lcd.is_powered())

class TestLcd___init__(LcdTestCase):
    def test_defaults(self):
        # Check the default lcd
        self.assertEqual(0x3c, self.lcd._hw_write_addr)
        self.mocked_smbus.assert_called_with(1)
        self.assertEqual(0, self.lcd._min_col_addr)
        self.assertEqual(127, self.lcd._max_col_addr)
        self.assertEqual(0, self.lcd._min_row_addr)
        self.assertEqual(7, self.lcd._max_row_addr)
        self.assertEqual(0, self.lcd._current_col)
        self.assertEqual(0, self.lcd._current_row)
        self.mocked_screen.assert_called_with(screen_pixel_width=128,
                                              screen_pixel_height=64)
        self.assertEqual(False, self.lcd._write_failure)
        self.assertEqual(False, self.lcd._power_state)
        self.assertEqual(True, self.lcd._enabled)

    def test_custom(self):
        with patch('ssd1306.smbus.SMBus', return_value=Mock()) as mocked_smbus,\
            patch('ssd1306.Screen', return_value=Mock()) as mocked_screen\
        :
            lcd = Lcd(
                i2c_hw_addr=0xfe,
                i2c_bus_number=100,
                screen_pixel_width=99,
                screen_pixel_height=12
            )
        self.assertEqual(0x7f, lcd._hw_write_addr)
        mocked_smbus.assert_called_with(100)
        self.assertEqual(0, lcd._min_col_addr)
        self.assertEqual(98, lcd._max_col_addr)
        self.assertEqual(0, lcd._min_row_addr)
        self.assertEqual(1, lcd._max_row_addr)
        self.assertEqual(0, lcd._current_col)
        self.assertEqual(0, lcd._current_row)
        mocked_screen.assert_called_with(screen_pixel_width=99,
                                         screen_pixel_height=12)
        self.assertEqual(False, lcd._write_failure)
        self.assertEqual(False, lcd._power_state)
        self.assertEqual(True, lcd._enabled)

class TestLcd_disable(LcdTestCase):
    def test_disable_when_enabled(self):
        self.lcd._bus.write_byte_data = MagicMock()
        self.assertTrue(self.lcd._enabled)
        self.lcd.disable()
        # Make sure Lcd is now disabled and off sequence was written to I2C
        self.assertFalse(self.lcd._enabled)
        self.lcd._bus.write_byte_data.assert_called_with(0x3c, Lcd.CONTROL_BYTE, Lcd.LCD_CONTROL_PWR_OFF)

    def test_disable_when_disabled(self):
        self.lcd._bus.write_byte_data = MagicMock()
        self.lcd._enabled = False
        self.lcd.disable()
        # Make sure no communication was made
        self.assertEqual(0, self.lcd._bus.call_count)

class TestLcd__set_screen_bytes(LcdTestCase):
    def test_nominal(self):
        self.lcd._screen.set_bytes = MagicMock(return_value=(123,321))
        self.lcd._current_row = 3
        self.lcd._current_col = 23
        b = [9,8,7,6,5,4,3,2,1]
        self.lcd._set_screen_bytes(b)
        self.lcd._screen.set_bytes.assert_called_with(
            b,
            cur_row=3,
            cur_col=23
        )
        self.assertEqual(123, self.lcd._current_row)
        self.assertEqual(321, self.lcd._current_col)

class TestLcd__write_control_byte(LcdTestCase):
    def test_enabled_passing(self):
        self.lcd._bus.write_byte_data = MagicMock()
        self.assertTrue(self.lcd._enabled)
        status = self.lcd._write_control_byte(92)
        self.assertTrue(status)
        self.lcd._bus.write_byte_data.assert_called_with(0x3c, Lcd.CONTROL_BYTE, 92)

    def test_enabled_failing(self):
        self.lcd._bus.write_byte_data = MagicMock(side_effect=Exception('bnota wis ehwehd'))
        self.assertTrue(self.lcd._enabled)
        status = self.lcd._write_control_byte(27)
        self.assertFalse(status)
        self.lcd._bus.write_byte_data.assert_called_with(0x3c, Lcd.CONTROL_BYTE, 27)

    def test_disabled(self):
        self.lcd._bus.write_byte_data = MagicMock()
        self.lcd._enabled = False
        status = self.lcd._write_control_byte(92)
        self.assertFalse(status)
        self.assertEqual(0, self.lcd._bus.write_byte_data.call_count)

    def test_disabled_forced(self):
        self.lcd._bus.write_byte_data = MagicMock()
        self.lcd._enabled = False
        status = self.lcd._write_control_byte(88, force=True)
        self.assertTrue(status)
        self.lcd._bus.write_byte_data.assert_called_with(0x3c, Lcd.CONTROL_BYTE, 88)

class TestLcd__write_data_byte(LcdTestCase):
    def test_enabled_passing(self):
        self.lcd._bus.write_byte_data = MagicMock()
        self.lcd._screen.set_bytes = MagicMock(return_value=(1,2))
        self.assertTrue(self.lcd._enabled)
        status = self.lcd._write_data_byte(99)
        self.assertTrue(status)
        self.lcd._bus.write_byte_data.assert_called_with(0x3c, Lcd.DATA_BYTE, 99)
        self.lcd._screen.set_bytes.assert_called_with([99], cur_row=0, cur_col=0)

    def test_enabled_failing(self):
        self.lcd._bus.write_byte_data = MagicMock(side_effect=Exception('bnota wis ehwehd'))
        self.lcd._screen.set_bytes = MagicMock(return_value=(1,2))
        self.assertTrue(self.lcd._enabled)
        status = self.lcd._write_data_byte(27)
        self.assertFalse(status)
        self.lcd._bus.write_byte_data.assert_called_with(0x3c, Lcd.DATA_BYTE, 27)
        self.assertEqual(0, self.lcd._screen.set_bytes.call_count)

    def test_disabled(self):
        self.lcd._bus.write_byte_data = MagicMock()
        self.lcd._screen.set_bytes = MagicMock(return_value=(1,2))
        self.lcd._enabled = False
        status = self.lcd._write_data_byte(111)
        self.assertFalse(status)
        self.assertEqual(0, self.lcd._bus.write_byte_data.call_count)
        self.assertEqual(0, self.lcd._screen.set_bytes.call_count)

class TestLcd__write_sequence(LcdTestCase):
    def test_enabled_non_data_bytearray(self):
        self.lcd._bus.write_i2c_block_data = MagicMock()
        self.assertTrue(self.lcd._enabled)
        status = self.lcd._write_sequence(223, bytearray([11,77,33,66,44,55]))
        self.assertTrue(status)
        self.lcd._bus.write_i2c_block_data.assert_called_with(0x3c, 223, [11,77,33,66,44,55])
        self.assertEqual(1, self.lcd._bus.write_i2c_block_data.call_count)

    def test_enabled_non_data_large_list(self):
        self.lcd._bus.write_i2c_block_data = MagicMock()
        self.assertTrue(self.lcd._enabled)
        b = [i for i in range(100)]
        status = self.lcd._write_control_sequence(b)
        self.assertTrue(status)
        self.lcd._bus.write_i2c_block_data.assert_has_calls([
            call(0x3c, Lcd.CONTROL_BYTE, [i for i in range(32)]),
            call(0x3c, Lcd.CONTROL_BYTE, [i for i in range(32, 64)]),
            call(0x3c, Lcd.CONTROL_BYTE, [i for i in range(64, 96)]),
            call(0x3c, Lcd.CONTROL_BYTE, [i for i in range(96, 100)])
        ])
        self.assertEqual(4, self.lcd._bus.write_i2c_block_data.call_count)

    def test_enabled_data_large_list(self):
        self.lcd._bus.write_i2c_block_data = MagicMock()
        self.lcd._screen.set_bytes = MagicMock(return_value=(1,2))
        self.assertTrue(self.lcd._enabled)
        b = [i for i in range(100)]
        status = self.lcd._write_data_sequence(b)
        self.assertTrue(status)
        self.lcd._bus.write_i2c_block_data.assert_has_calls([
            call(0x3c, Lcd.DATA_BYTE, [i for i in range(32)]),
            call(0x3c, Lcd.DATA_BYTE, [i for i in range(32, 64)]),
            call(0x3c, Lcd.DATA_BYTE, [i for i in range(64, 96)]),
            call(0x3c, Lcd.DATA_BYTE, [i for i in range(96, 100)])
        ])
        self.assertEqual(4, self.lcd._bus.write_i2c_block_data.call_count)
        self.lcd._screen.set_bytes.assert_has_calls([
            call([i for i in range(32)], cur_row=0, cur_col=0),
            call([i for i in range(32, 64)], cur_row=1, cur_col=2),
            call([i for i in range(64, 96)], cur_row=1, cur_col=2),
            call([i for i in range(96, 100)], cur_row=1, cur_col=2)
        ])
        self.assertEqual(4, self.lcd._screen.set_bytes.call_count)

    def test_failure(self):
        self.lcd._bus.write_i2c_block_data = MagicMock(side_effect=Exception())
        self.lcd._screen.set_bytes = MagicMock(return_value=(1,2))
        self.assertTrue(self.lcd._enabled)
        b = [i for i in range(100)]
        status = self.lcd._write_sequence(Lcd.DATA_BYTE, b)
        self.assertFalse(status)
        self.assertTrue(self.lcd._write_failure)

    def test_disabled(self):
        self.lcd._bus.write_i2c_block_data = MagicMock()
        self.lcd._screen.set_bytes = MagicMock(return_value=(1,2))
        self.lcd._enabled = False
        b = [i for i in range(100)]
        status = self.lcd._write_sequence(Lcd.DATA_BYTE, b)
        self.assertFalse(status)
        self.assertFalse(self.lcd._write_failure)
        self.assertEqual(0, self.lcd._bus.write_i2c_block_data.call_count)
        self.assertEqual(0, self.lcd._screen.set_bytes.call_count)

class TestLcd_write_initialization_sequence(LcdTestCase):
    def test_nominal(self):
        self.lcd._screen.set_bytes = MagicMock(return_value=(1,2))
        mocked_copy_screen = Mock()
        self.lcd._screen.copy = MagicMock(return_value=mocked_copy_screen)
        mocked_copy_screen.clear = MagicMock()
        self.lcd.clear = MagicMock()
        with patch('ssd1306.smbus.SMBus.write_byte_data'),\
            patch('ssd1306.smbus.SMBus.write_i2c_block_data')\
        :
            self.lcd.write_initialization_sequence()
        self.lcd._bus.write_i2c_block_data.assert_called_with(0x3c, Lcd.CONTROL_BYTE, ANY) # Initialization sequence
        self.lcd.clear.assert_called_with(force=True)
        # Powered on
        self.lcd._bus.write_byte_data.assert_called_with(0x3c, Lcd.CONTROL_BYTE, Lcd.LCD_CONTROL_PWR_ON)

class TestLcd_set_power(LcdTestCase):
    def test_set_power_on_success(self):
        self.assertFalse(self.lcd._power_state)
        with patch('ssd1306.Lcd._write_control_byte', return_value=True) as mocked_wcb:
            status = self.lcd.set_power(on=True)
        self.assertTrue(status)
        self.assertTrue(self.lcd._power_state)
        mocked_wcb.assert_called_with(Lcd.LCD_CONTROL_PWR_ON)

    def test_set_power_off_success(self):
        self.lcd._power_state = True
        with patch('ssd1306.Lcd._write_control_byte', return_value=True) as mocked_wcb:
            status = self.lcd.set_power(on=False)
        self.assertTrue(status)
        self.assertFalse(self.lcd._power_state)
        mocked_wcb.assert_called_with(Lcd.LCD_CONTROL_PWR_OFF)

    def test_failure(self):
        self.assertFalse(self.lcd._power_state)
        with patch('ssd1306.Lcd._write_control_byte', return_value=False) as mocked_wcb:
            status = self.lcd.set_power(on=True)
        self.assertFalse(status)
        self.assertFalse(self.lcd._power_state)

class TestLcd__force_power_off(LcdTestCase):
    def test_success(self):
        self.lcd._power_state = True
        with patch('ssd1306.Lcd._write_control_byte', return_value=True) as mocked_wcb:
            status = self.lcd._force_power_off()
        self.assertTrue(status)
        self.assertFalse(self.lcd._power_state)
        mocked_wcb.assert_called_with(Lcd.LCD_CONTROL_PWR_OFF, force=True)

    def test_failure(self):
        self.lcd._power_state = True
        with patch('ssd1306.Lcd._write_control_byte', return_value=False) as mocked_wcb:
            status = self.lcd._force_power_off()
        self.assertFalse(status)
        self.assertTrue(self.lcd._power_state)

class TestLcd_write_screen(LcdTestCase):
    def test_write_same_screen(self):
        mock_screen = Mock()
        mock_screen.row_start = 0
        mock_screen.row_end = 7
        mock_screen.col_start = 0
        mock_screen.col_end = 127
        mock_screen.bytes = [bytearray([i for i in range(128)]) for _ in range(8)]
        self.lcd._screen.bytes_block = MagicMock(return_value=[bytearray([i for i in range(128)]) for _ in range(8)])
        # Make sure that nothing is actually written - return False if that happens
        with patch('ssd1306.Lcd._write_control_sequence', return_value=False), \
            patch('ssd1306.Lcd._write_data_sequence', return_value=False)\
        :
            status = self.lcd.write_screen(mock_screen)
        self.assertTrue(status)
        self.lcd._screen.bytes_block.assert_called_with(
            row_start=0, row_end=7, col_start=0, col_end=127
        )
    def test_write_some_rows_different(self):
        mock_screen = Mock()
        mock_screen.row_start = 0
        mock_screen.row_end = 7
        mock_screen.col_start = 0
        mock_screen.col_end = 127
        mock_screen.bytes = [bytearray([i for i in range(128)]) for _ in range(8)]
        mock_screen.bytes[1][0] = 1 # only 1 byte in row 1 will differ
        mock_screen.bytes[7][0] = 2 # only 1 byte in row 7 will differ
        self.lcd._screen.bytes_block = MagicMock(return_value=[bytearray([i for i in range(128)]) for _ in range(8)])
        # Make sure that nothing is actually written - return False if that happens
        with patch('ssd1306.Lcd._write_control_sequence', return_value=True) as mocked_wcs, \
            patch('ssd1306.Lcd._write_data_sequence', return_value=True) as mocked_wds\
        :
            status = self.lcd.write_screen(mock_screen)
        self.assertTrue(status)
        self.lcd._screen.bytes_block.assert_called_with(
            row_start=0, row_end=7, col_start=0, col_end=127
        )
        # Pointer should have been set for row 1 then row 7
        mocked_wcs.assert_has_calls([
            call([0xB1, 0x10, 0x00]),
            call([0xB7, 0x10, 0x00])
        ])
        # Write 128 data bytes for 1 and 7
        expected_write1 = bytearray([i for i in range(128)])
        expected_write1[0] = 1
        expected_write2 = bytearray([i for i in range(128)])
        expected_write2[0] = 2
        mocked_wds.assert_has_calls([
            call(expected_write1),
            call(expected_write2)
        ])
    def test_write_same_screen_forced(self):
        mock_screen = Mock()
        mock_screen.row_start = 0
        mock_screen.row_end = 7
        mock_screen.col_start = 0
        mock_screen.col_end = 127
        mock_screen.bytes = [bytearray([i for i in range(128)]) for _ in range(8)]
        self.lcd._screen.bytes_block = MagicMock(return_value=[bytearray([i for i in range(128)]) for _ in range(8)])
        # Make sure that nothing is actually written - return False if that happens
        with patch('ssd1306.Lcd._write_control_sequence', return_value=True) as mocked_wcs, \
            patch('ssd1306.Lcd._write_data_sequence', return_value=True) as mocked_wds\
        :
            status = self.lcd.write_screen(mock_screen, force=True)
        self.assertTrue(status)
        self.lcd._screen.bytes_block.assert_called_with(
            row_start=0, row_end=7, col_start=0, col_end=127
        )
        # Pointer should have been set for each row
        mocked_wcs.assert_has_calls([
            call([0xB0, 0x10, 0x00]),
            call([0xB1, 0x10, 0x00]),
            call([0xB2, 0x10, 0x00]),
            call([0xB3, 0x10, 0x00]),
            call([0xB4, 0x10, 0x00]),
            call([0xB5, 0x10, 0x00]),
            call([0xB6, 0x10, 0x00]),
            call([0xB7, 0x10, 0x00])],
            any_order=False
        )
        # Write 128 data bytes for all rows
        expected_write = bytearray([i for i in range(128)])
        mocked_wds.assert_has_calls([
            call(expected_write),
            call(expected_write),
            call(expected_write),
            call(expected_write),
            call(expected_write),
            call(expected_write),
            call(expected_write)
        ])
    def test_set_pointer_failed(self):
        mock_screen = Mock()
        mock_screen.row_start = 0
        mock_screen.row_end = 7
        mock_screen.col_start = 0
        mock_screen.col_end = 127
        mock_screen.bytes = [bytearray([i for i in range(128)]) for _ in range(8)]
        self.lcd._screen.bytes_block = MagicMock(return_value=[bytearray([i for i in range(128)]) for _ in range(8)])
        # Make sure that nothing is actually written - return False if that happens
        with patch('ssd1306.Lcd._write_control_sequence', return_value=False) as mocked_wcs, \
            patch('ssd1306.Lcd._write_data_sequence', return_value=True) as mocked_wds\
        :
            status = self.lcd.write_screen(mock_screen, force=True)
        self.assertFalse(status)
    def test_write_data_failed(self):
        mock_screen = Mock()
        mock_screen.row_start = 0
        mock_screen.row_end = 7
        mock_screen.col_start = 0
        mock_screen.col_end = 127
        mock_screen.bytes = [bytearray([i for i in range(128)]) for _ in range(8)]
        self.lcd._screen.bytes_block = MagicMock(return_value=[bytearray([i for i in range(128)]) for _ in range(8)])
        # Make sure that nothing is actually written - return False if that happens
        with patch('ssd1306.Lcd._write_control_sequence', return_value=True) as mocked_wcs, \
            patch('ssd1306.Lcd._write_data_sequence', return_value=False) as mocked_wds\
        :
            status = self.lcd.write_screen(mock_screen, force=True)
        self.assertFalse(status)




