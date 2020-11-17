import os
import sys

# Insert test directories and this plugin's directory
TEST_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, TEST_DIR)
STUB_DIR = os.path.join(TEST_DIR, "stubs")
sys.path.insert(0, STUB_DIR)
SSD1306_DIR = os.path.realpath(os.path.join(TEST_DIR, '..'))
sys.path.insert(0, SSD1306_DIR)
# Load stubbed-out components for ssd1306
sys.modules['web'] = __import__('stub_web')
sys.modules['gv'] = __import__('stub_gv')
sys.modules['urls'] = __import__('stub_urls')
sys.modules['sip'] = __import__('stub_sip')
sys.modules['webpages'] = __import__('stub_webpages')
sys.modules['blinker'] = __import__('stub_blinker')
sys.modules['smbus'] = __import__('stub_smbus')

from ssd1306 import Screen

class Ssd1306CustomAssertions:
    def assertScreenBytes(self, expected_bytes, screen):
        if screen.bytes != expected_bytes:
            error_string = (
                "Expected Screen:\n"
                + Screen.bytes_to_string(expected_bytes)
                + "\nActual Screen:\n"
                + str(screen)
                + "\n"
                + ",\n".join(["bytearray({})".format(list(row)) for row in screen.bytes])
            )
            raise AssertionError(error_string)
