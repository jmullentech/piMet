import smbus
import time
import datetime
import gspread
import httplib2
from oauth2client.service_account import ServiceAccountCredentials

class piMet:
		
	def __init__(self):

		# Initialize Google API with scope and credentials from JSON
		self.scope = ' '.join(['https://www.googleapis.com/auth/drive'])
		self.credentials = ServiceAccountCredentials.from_json_keyfile_name('PATH_TO_API_JSON.json', self.scope)
		self.gc = gspread.authorize(self.credentials)
		self.worksheet = self.gc.open_by_url("https://docs.google.com/spreadsheets/URL_TO_SPREADSHEET").sheet1

		# Required for auth method
		self.http = httplib2.Http()
		self.http = self.credentials.authorize(self.http)

		# Interval in seconds between measurements.
		self.observationFreq = 15

		# Altitude of station in meters
		# Must be accurate for conversions below
		self.alt = 72

	def renegCreds(self):
		if self.credentials.access_token_expired or self.credentials.access_token is None:
			print("Credentials expired, refreshing...")
			self.credentials.refresh(http)
			self.gc.login()
			print("Refresh SUCCESSFUL!")

	def calcs(self):

		# Get I2C bus
		bus = smbus.SMBus(1)
		b1 = bus.read_i2c_block_data(0x77, 0x88, 24)

		# Convert the data
		# Temp coefficents
		dig_T1 = b1[1] * 256 + b1[0]
		dig_T2 = b1[3] * 256 + b1[2]
		if dig_T2 > 32767 :
		    dig_T2 -= 65536
		dig_T3 = b1[5] * 256 + b1[4]
		if dig_T3 > 32767 :
		    dig_T3 -= 65536

		# Pressure coefficents
		dig_P1 = b1[7] * 256 + b1[6]
		dig_P2 = b1[9] * 256 + b1[8]
		if dig_P2 > 32767 :
		    dig_P2 -= 65536
		dig_P3 = b1[11] * 256 + b1[10]
		if dig_P3 > 32767 :
		    dig_P3 -= 65536
		dig_P4 = b1[13] * 256 + b1[12]
		if dig_P4 > 32767 :
		    dig_P4 -= 65536
		dig_P5 = b1[15] * 256 + b1[14]
		if dig_P5 > 32767 :
		    dig_P5 -= 65536
		dig_P6 = b1[17] * 256 + b1[16]
		if dig_P6 > 32767 :
		    dig_P6 -= 65536
		dig_P7 = b1[19] * 256 + b1[18]
		if dig_P7 > 32767 :
		    dig_P7 -= 65536
		dig_P8 = b1[21] * 256 + b1[20]
		if dig_P8 > 32767 :
		    dig_P8 -= 65536
		dig_P9 = b1[23] * 256 + b1[22]
		if dig_P9 > 32767 :
		    dig_P9 -= 65536

		# BMP280 address, 0x77(118)
		# Select Control measurement register, 0xF4(244)
		#		0x27(39)	Pressure and Temperature Oversampling rate = 1
		#					Normal mode
		bus.write_byte_data(0x77, 0xF4, 0x27)
		# BMP280 address, 0x77(118)
		# Select Configuration register, 0xF5(245)
		#		0xA0(00)	Stand_by time = 100 ms
		bus.write_byte_data(0x77, 0xF5, 0xA0)
		
		time.sleep(0.1)

		# BMP280 address, 0x77(118)
		# Read data back from 0xF7(247), 8 bytes
		# Pressure MSB, Pressure LSB, Pressure xLSB, Temperature MSB, Temperature LSB
		# Temperature xLSB, Humidity MSB, Humidity LSB
		data = bus.read_i2c_block_data(0x77, 0xF7, 8)

		# Convert pressure and temperature data to 19-bits
		adc_p = ((data[0] * 65536) + (data[1] * 256) + (data[2] & 0xF0)) / 16
		adc_t = ((data[3] * 65536) + (data[4] * 256) + (data[5] & 0xF0)) / 16

		# Temperature offset calculations
		var1 = ((adc_t) / 16384.0 - (dig_T1) / 1024.0) * (dig_T2)
		var2 = (((adc_t) / 131072.0 - (dig_T1) / 8192.0) * ((adc_t)/131072.0 - (dig_T1)/8192.0)) * (dig_T3)
		t_fine = (var1 + var2)
		self.cTemp = (var1 + var2) / 5120.0
		self.fTemp = self.cTemp * 1.8 + 32

		# Pressure offset calculations
		var1 = (t_fine / 2.0) - 64000.0
		var2 = var1 * var1 * (dig_P6) / 32768.0
		var2 = var2 + var1 * (dig_P5) * 2.0
		var2 = (var2 / 4.0) + ((dig_P4) * 65536.0)
		var1 = ((dig_P3) * var1 * var1 / 524288.0 + ( dig_P2) * var1) / 524288.0
		var1 = (1.0 + var1 / 32768.0) * (dig_P1)
		p = 1048576.0 - adc_p
		p = (p - (var2 / 4096.0)) * 6250.0 / var1
		var1 = (dig_P9) * p * p / 2147483648.0
		var2 = p * (dig_P8) / 32768.0
		self.pressure = (p + (var1 + var2 + (dig_P7)) / 16.0) / 100

		# Adjust station pressure to MSLP
		self.mslp = (self.pressure + (self.alt / 9.2)) * 0.02953

		# Create observation time/date STRING from datetime object
		# Fails if you try to parse direct with JSON
		self.obsdate = time.strftime("%m-%d-%Y")
		self.obstime = time.strftime("%H:%M:%S")

	def output(self):
		# Output to console for verification
		print 'Time: {}'.format(self.obstime)
		print 'Temperature: {0:0.2f} F'.format(self.fTemp)
		print 'Pressure:    {0:0.2f} inHg'.format(self.mslp)

		# Append the data in the spreadsheet, including a timestamp
		self.worksheet.append_row((self.obsdate, self.obstime, self.fTemp, self.mslp))

		# Wait n seconds before taking next measurement
		print("Data block pushed to Google Sheets")
		time.sleep(self.observationFreq)

	def runall(self):
		while True:
			runall.calcs()
			runall.output()
			runall.renegCreds()

# Run it all
runall = piMet()
runall.runall()