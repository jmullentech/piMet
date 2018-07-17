import smbus
import time
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Initialize Google API with scope and credentials from JSON
scope = ' '.join(['https://www.googleapis.com/auth/drive'])
credentials = ServiceAccountCredentials.from_json_keyfile_name('PATH_TO_API_JSON.json', scope)
gc = gspread.authorize(credentials)
worksheet = gc.open_by_url("https://docs.google.com/spreadsheets/URL_TO_SPREADSHEET").sheet1

# Interval in seconds between measurements.
observationFreq = 15

# Altitude of station in meters
# Must be accurate for conversions below
alt = 72

def main():

	# Get I2C bus
	bus = smbus.SMBus(1)

	# Initalizing console
	print 'Logging data every {} seconds.'.format(observationFreq)
	print 'Press Ctrl-C to quit.'

	# Start main loop
	while True:
		if credentials is None or credentials.invalid:
			credentials.refresh(httplib2.Http())
			print("Credentials expired, refreshing...")

		# BMP280 address, 0x77(118)
		# Read data back from 0x88(136), 24 bytes
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
		#		0xA0(00)	Stand_by time = 1000 ms
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
		cTemp = (var1 + var2) / 5120.0
		fTemp = cTemp * 1.8 + 32

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
		pressure = (p + (var1 + var2 + (dig_P7)) / 16.0) / 100

		# Will expand on this, quick and dirty hack but works for now
		mslp = (pressure + (alt / 9.2)) * 0.02953

		# Create observation time/date STRING from datetime object
		# Fails if you try to parse direct with JSON
		obsdate = time.strftime("%m-%d-%Y")
		obstime = time.strftime("%H:%M:%S")

		# Output Temp/Press to console for verification
		print 'Temperature: {0:0.2f} F'.format(fTemp)
		print 'Pressure:    {0:0.2f} inHg'.format(mslp)

		# Append the data in the spreadsheet, including a timestamp
		worksheet.append_row((obsdate, obstime, fTemp, mslp))

		# Confirm no error
		# Wait 'n' seconds before taking next measurement
		print("Data block pushed to Google Sheets")
		time.sleep(observationFreq)

if __name__ == "__main__":
	main()