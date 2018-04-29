'''
Copyright (C) 2012 Matthew Skolaut

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and 
associated documentation files (the "Software"), to deal in the Software without restriction, 
including without limitation the rights to use, copy, modify, merge, publish, distribute, 
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is 
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE 
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

import smbus
from time import *

# General i2c device class so that other devices can be added easily
class i2c_device:
	def __init__(self, addr, port):
		self.addr = addr
		self.bus = smbus.SMBus(port)

	def write(self, byte):
		self.bus.write_byte(self.addr, byte)

	def read(self):
		return self.bus.read_byte(self.addr)

	def read_nbytes_data(self, data, n): # For sequential reads > 1 byte
		return self.bus.read_i2c_block_data(self.addr, data, n)

		
		

class lcd:
	#initializes objects and lcd
	'''
	Reverse Codes:
	0: lower 4 bits of expander are commands bits
	1: top 4 bits of expander are commands bits AND P0-4 P1-5 P2-6 (Use for "LCD2004" board)
	2: top 4 bits of expander are commands bits AND P0-6 P1-5 P2-4
	3: "LCD2004" board where lower 4 are commands, but backlight is pin 3
	'''
	def __init__(self, addr, port, reverse=0, backlight_pin=-1, en_pin=-1, rw_pin=-1, rs_pin=-1, d4_pin=-1, d5_pin=-1, d6_pin=-1, d7_pin=-1):
		self.reverse = reverse
		self.lcd_device = i2c_device(addr, port)

		self.pins=[i for i in range(8)] # Initialize the list
		self.backlight=1<<7 # Initialize with backlight as on (Change self.backlight to 0 to turn off backlight pin)
		
		if d7_pin != -1: # Manually set pins, in case we have a different backpack pinout
			self.pins[0]=d4_pin
			self.pins[1]=d5_pin
			self.pins[2]=d6_pin
			self.pins[3]=d7_pin
			self.pins[4]=rs_pin
			self.pins[5]=rw_pin
			self.pins[6]=en_pin
			self.pins[7]=backlight_pin
		
		elif self.reverse==1: # 1: top 4 bits of expander are commands bits AND P0-4 P1-5 P2-6 (Use for "LCD2004" board)
			self.pins[0]=4	 	# D4 Pin
			self.pins[1]=5 		# D5 Pin
			self.pins[2]=6 		# D6 Pin
			self.pins[3]=7 		# D7 Pin
			self.pins[4]=0 		# RS Pin
			self.pins[5]=1 		# RW Pin
			self.pins[6]=2 		# EN Pin
			self.pins[7]=3 		# Backlight Pin
		
		elif self.reverse==2: # 2: top 4 bits of expander are commands bits AND P0-6 P1-5 P2-4
			self.pins[0]=4	 	# D4 Pin
			self.pins[1]=5 		# D5 Pin
			self.pins[2]=6 		# D6 Pin
			self.pins[3]=7 		# D7 Pin
			self.pins[4]=0 		# RS Pin
			self.pins[5]=1 		# RW Pin
			self.pins[6]=2 		# EN Pin
			self.pins[7]=3 		# Backlight Pin		
		
		else:
			# self.pins is already initialized to this, but broken out here for clarity
			self.pins[0]=0	 	# D4 Pin
			self.pins[1]=1 		# D5 Pin
			self.pins[2]=2 		# D6 Pin
			self.pins[3]=3 		# D7 Pin
			self.pins[4]=4 		# RS Pin
			self.pins[5]=5 		# RW Pin
			self.pins[6]=6 		# EN Pin
			self.pins[7]=7 		# Backlight Pin


		# This begins the actual initialization sequence
		self.lcd_device_write(0x03) # Prepare to switch to 4 bit mode
		self.lcd_strobe()
		sleep(0.0005)
		self.lcd_strobe()
		sleep(0.0005)
		self.lcd_strobe()
		sleep(0.0005)

		self.lcd_device_write(0x02) # Set 4 bit mode
		self.lcd_strobe()
		sleep(0.0005)


		# Initialize
		self.lcd_write(0x28) # Set 4 bit, 2 line mode (Multi-line)
		self.lcd_write(0x08) # Hide cursor, don't blink
		self.lcd_write(0x01) # Clear display, move cursor home
		self.lcd_write(0x06) # Move cursor right
		self.lcd_write(0x0C) # Turn on display
#		self.lcd_write(0x0F)


	# clocks EN to latch command
	def lcd_strobe(self):
		self.lcd_device_write(self.lastcomm | (1<<6), 1) # 1<<6 is the enable pin
		self.lcd_device_write(self.lastcomm,1) # Technically not needed, but included so we can read from the display

	# write a command to lcd
	def lcd_write(self, cmd):
		self.lcd_device_write((cmd >> 4)) # Write the first 4 bits (nibble) of the command
		self.lcd_strobe()
		self.lcd_device_write((cmd & 0x0F)) # Write the second nibble of the command
		self.lcd_strobe()
		self.lcd_device_write(0x0) # Technically not needed

	# write a character to lcd (or character rom)
	def lcd_write_char(self, charvalue):
		self.lcd_device_write(((1<<4) | (charvalue >> 4))) # Originally this was 0x40
		self.lcd_strobe()
		self.lcd_device_write(((1<<4) | (charvalue & 0x0F))) # Originally this was 0x40
		self.lcd_strobe()
		self.lcd_device_write(0x0)

	# put char function
	def lcd_putc(self, char):
		self.lcd_write_char(ord(char))


	# Do clunky bitshifting to account for strangely wired boards
	# I guarantee there is an easier way of doing this.
	def lcd_device_write(self, commvalue, isstrobe=0):
		tempcomm=commvalue | self.backlight
		outcomm=[0 for i in range(8)]
		
		for a in range(0,8):
			outcomm[self.pins[a]]=(tempcomm & 1)
			tempcomm=tempcomm>>1

		tempcomm=0
		a=7
		while (a >= 0):
			tempcomm=(tempcomm<<1)|outcomm[a]
			a=a-1;

		self.lcd_device.write(tempcomm)
		sleep(0.0005) # May be unnecessary, but including to guarantee we don't push data out too fast
		
		# Since we can't trust what we read from the display, we store the last
		# executed command in a property inside the object. This way strobe
		# can add the enable bit & resend it
		if isstrobe==0: # 
			self.lastcomm=commvalue

		
		
		
	# put string function
	def lcd_puts(self, string, line):
		if line == 1:
			self.lcd_write(0x80)
		if line == 2:
			self.lcd_write(0xC0)
		if line == 3:
			self.lcd_write(0x94)
		if line == 4:
			self.lcd_write(0xD4)

		for char in string:
			self.lcd_putc(char)

	# clear lcd and set to home
	def lcd_clear(self):
		self.lcd_write(0x1)
		sleep(0.005) # This command takes awhile.
		self.lcd_write(0x2)
		sleep(0.005) # This command takes awhile.

	# add custom characters (0 - 7)
	def lcd_load_custon_chars(self, fontdata):
		self.lcd_device.bus.write(0x40);
		for char in fontdata:
			for line in char:
				self.lcd_write_char(line)

