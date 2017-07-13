import pprint
import serial
import time
import re
import configparser
import argparse
import sys
from pyudev import Context, Monitor, MonitorObserver

#define JeeDevice class
class JeeDevice:
	port = ''
	shortId = ''
	nodeId = ''
	group = ''
	freq = ''
	
	def description(self):
		desc = '{0}\t{1}\t{2}\t{3}\t{4}'.format(self.port, self.shortId, self.nodeId, self.group, self.freq)
		return desc
	
	def desc(self):
		return 'A i{0} g{1} {2} MHz q1'.format(self.nodeId, self.group, self.freq)

		
		
profuse = False				#for debug reporting
remoteDevice = JeeDevice()	#remote node for testing packets over radio
currentDevice = JeeDevice()	#device currently being tested

def vprint(message, level):
	if profuse:
		print(message)

def configArgParser():
	parser = argparse.ArgumentParser()
	parser.add_argument('-c', '--conf', help='specified configuration file')
	parser.add_argument('-v', '--verbosity', help='increases the verbosity of output', action='store_true')
	return parser

def setConfiguration():
	configurationFile = 'tester.conf'		#default configuration file
	
	parser = configArgParser()
	args = parser.parse_args()
	if args.conf:
		print('configuration set')
		configurationFile = args.conf
	
	print('using configuration file ', configurationFile)
	
	if args.verbosity:
		global profuse
		profuse = True
		print('verbose output selected')
		

	Config=configparser.ConfigParser()
	#print(Config)
	try:
		with open(configurationFile) as f:
			Config.readfp(f)
	except IOError:
		print('specified config file not found: {0}'.format(configurationFile))
		sys.exit(1)
		

	
	section='JeelinkRemote'						#Jeelink remote settings
	dict1 = {}
	options = Config.options(section)
	for option in options:
		dict1[option] = Config.get(section, option)
		
	global remoteDevice
	remoteDevice.nodeId = dict1['nodeid']
	remoteDevice.group = dict1['group']
	remoteDevice.freq = dict1['frequency']
	print('REMOTE DEVICE:', remoteDevice.desc())

def openSerialInterface(device):
	
	ser = serial.Serial(
		port=device.device_node,
		baudrate=57600,
		parity=serial.PARITY_NONE,
		stopbits=serial.STOPBITS_ONE,
		timeout=1)
	
	deviceConfig = consumePreamble(device, ser)
	regex = r'(^A i(\d+) g(\d+) @ (\d+) MHz q(\d+))'
	match = re.search(regex, deviceConfig)
	
	global currentDevice
	currentDevice.shortId = device['ID_SERIAL_SHORT']
	currentDevice.port = device.device_node
	currentDevice.nodeId = match.group(2)
	currentDevice.group = match.group(3)
	currentDevice.freq = match.group(4)
	
	print('New device with ID {1} found on {0} with configuration {2}'.format(currentDevice.port, currentDevice.shortId, currentDevice.desc()))
	
	return ser
	
def consumePreamble(device, ser):
	count = 0
	regex = r'(^A i(\d+) g(\d+) @ (\d+) MHz q(\d+))'	#matches last line of preamble e.g. A i1 g208 @ 868 MHz q1
	
	while True:
		count = count + 1
		line=ser.readline().strip().decode('utf-8')
		vprint(line, 1)
		if re.search(regex,line):
			match = re.search(regex,line)
			vprint ('{0}'.format(line),1)
			return line
		elif count >= 50:
			'device config not found'
			
def blinkLED(device, ser):
	timeout = 0.1
	
	print('blinking LED...')
	for i in range(5):
		ser.write(b'1l')
		time.sleep(timeout)
		ser.read(ser.inWaiting())
		ser.write(b'0l')
		time.sleep(timeout)
		ser.read(ser.inWaiting())
		
def packetTest(device, ser):
	print('testing packets..')
	timeout = 0.1
	numpacks = 5
	regex = r'(OK)'
	
	#set up the device so it has the same group and ensure id's are different
	if remoteDevice.group != currentDevice.group:
		print('Groups don\'t match')
	if remoteDevice.freq != currentDevice.freq:
		print('Frequencies don\'t match')
	if remoteDevice.nodeId == currentDevice.nodeId:
		print('node Id clash')

	oks = 0
	for x in range(numpacks):
		ser.write(b'0t')
		time.sleep(timeout)
		response = ser.read(ser.inWaiting()).decode('utf-8')
		if re.search(regex, response):
			oks = oks +1
			vprint (' '.join(response.split()),1)
		time.sleep(timeout)
	if oks == numpacks:
		print('PASSED ({0}/{1})'.format(oks,numpacks))
	else:
		print('FAILED ({0}/{1}) consider using -v for more info'.format(oks,numpacks))

def device_event(action, device):
	if action == 'add':
		ser = openSerialInterface(device)
		blinkLED(device, ser)
		packetTest(device, ser)
		ser.close()

def main():
	setConfiguration()	#configure testing environment variables
	context = Context()
	monitor = Monitor.from_netlink(context)
	monitor.filter_by(subsystem='tty')
	observer = MonitorObserver(monitor, device_event)
	observer.start()
	
	while True:
		n = input("Jeelink Tester v 1.0 type 'stop' to end\n")
		if n == 'stop':
			observer.stop()
			break

if __name__ == "__main__":
	main()
