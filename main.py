import timers
import spi
import gpio
import os
import fatfs
import streams

streams.serial()

_COMMAND_BAUDRATE = 250000  # Speed for command transfers (MUST be slow)
_DATA_BAUDRATE = 8000000  # Speed for data transfers (fast!)

SCI_MODE = 0x00
SCI_STATUS = 0x01
SCI_WRITE = 0x02
SCI_READ = 0x03
SCI_REG_CLOCKF = 0x03
SCI_WRAM = 0x06
SCI_WRAMADDR = 0x07
SCI_HDAT0 = 0x08
SCI_HDAT1 = 0x09
SCI_VOL = 0x0B

_VS1053_SCI_READ = 0x03
_VS1053_SCI_WRITE = 0x02

_VS1053_REG_MODE = 0x00
_VS1053_REG_STATUS = 0x01
_VS1053_REG_BASS = 0x02
_VS1053_REG_CLOCKF = 0x03
_VS1053_REG_DECODETIME = 0x04
_VS1053_REG_AUDATA = 0x05
_VS1053_REG_WRAM = 0x06
_VS1053_REG_WRAMADDR = 0x07
_VS1053_REG_HDAT0 = 0x08
_VS1053_REG_HDAT1 = 0x09
_VS1053_REG_VOLUME = 0x0B

_VS1053_MODE_SM_SDINEW = 0x0800
_VS1053_MODE_SM_RESET = 0x0004
_VS1053_MODE_SM_CANCEL = 0x0008
_VS1053_MODE_SM_LINE1 = 0x4000

SM_STREAM = 0x200
SM_RESET = 0x2000

fatfs.mount('0:', {"drv": SD0, "freq_khz": 20000, "bits": 1})
sleep(4000)
spiRESET = spi.Spi(D1)
spiData = spi.Spi(D7, clock=_DATA_BAUDRATE)
spiCMD = spi.Spi(D2, clock=_COMMAND_BAUDRATE)
#spiDREQ = spi.Spi(D0)
SD_CARD_PATH = '0:'
mp3_dir = SD_CARD_PATH + "mp3"

# Define GPIO pin numbers for DREQ and RESET
DREQ_PIN = D0  # Data request pin
pinMode(DREQ_PIN,INPUT_PULLUP)
#RESET_PIN = D1  # Reset pin
#pinMode(RESET_PIN, OUTPUT)

def printStatus():
    print("SCI_MODE: ", read_register(SCI_MODE))
    print("SCI_STATUS: ", read_register(SCI_STATUS))

def soft_reset_vs1053():
    printStatus()
    write_register(_VS1053_REG_MODE, _VS1053_MODE_SM_RESET)  # SM_RESET (bit 2)
    #print(digitalRead(DREQ_PIN))
    sleep(100)  # Allow some time for the reset to take effect
    printStatus()
    
def vs1053_init():
    """Initialize the VS1053 chip for MP3 playback"""
    #digitalWrite(RESET_PIN, LOW)
    print("DREQ is: ", digitalRead(DREQ_PIN))
    sleep(50) 
    write_register(_VS1053_REG_MODE, _VS1053_MODE_SM_SDINEW | _VS1053_MODE_SM_RESET, spiRESET)
    sleep(50)
    write_register(_VS1053_REG_CLOCKF, 0x6000, spiRESET)
    sleep(50)
    #digitalWrite(RESET_PIN, HIGH)
    print("DREQ is: ", digitalRead(DREQ_PIN))
    sleep(50)  # Wait for VS1053B to initialize
    #soft_reset_vs1053()
    
    while digitalRead(DREQ_PIN) == LOW:
        sleep(10)  # Wait until DREQ is high
    
    print("SCI_MODE: ", read_register(_VS1053_REG_MODE))
    print("SCI_STATUS: ", read_register(_VS1053_REG_STATUS))
    
    #write_register(SCI_MODE, 0x2B2)  # Set the mode to MP3 decoder mode
    while digitalRead(DREQ_PIN) == LOW:
        sleep(10)  # Wait until DREQ is high

    write_register(SCI_VOL, 0x0000)
    print("VS1053 Initialized")
    sleep(100)
    print("SCI_MODE: ", read_register(_VS1053_REG_MODE))
    print("SCI_STATUS: ", read_register(_VS1053_REG_STATUS))


# Function to set volume (0x00 for max volume, 0xFE for mute)
def set_volume(left, right):
    volume = (right << 8) | left
    write_register(0x0B, volume)

# Function to write a value to a VS1053B register
def write_register(register, value, spiPin=spiCMD):
    high_byte = (value >> 8) & 0xFF
    low_byte = value & 0xFF
    spiPin.select()
    spiPin.write(bytearray([SCI_WRITE, register&0xFF, high_byte, low_byte]))
    spiPin.unselect()

def read_register(register):
    read_opcode = 0x03
    spiCMD.select()
    spiCMD.write(bytearray([read_opcode, register]))
    response = spiCMD.read(2)
    spiCMD.unselect()
    high_byte = response[0]
    low_byte = response[1]
    return (high_byte << 8) | low_byte

# Function to send MP3 data to VS1053B
def send_mp3_data(register, data):
    """Send MP3 data to the VS1053B for playback."""
    while digitalRead(DREQ_PIN) == LOW:
        sleep(10)  # Wait until DREQ is high
    spiData.select()
    writeData = bytearray([register]) + data
    spiData.write(writeData)
    spiData.unselect()

#def hard_reset():
    #digitalWrite(RESET_PIN, LOW)
    #digitalWrite(RESET_PIN, HIGH)

def overload_dreq():
    while digitalRead(DREQ_PIN) == HIGH:
        write_register(_VS1053_REG_MODE, _VS1053_MODE_SM_RESET) # stream mode
    print("DREQ went LOW")
    
def get_dreq():
    c1 = 0
    while True:
        if digitalRead(DREQ_PIN) == HIGH:
            c1 += 1
            if c1%1000 == 0:
                print("DREQ still HIGH")
        else:
            print("DREQ went LOW", c1)
            sleep(100)

# Function to play an MP3 file
def play_mp3(filename):
    counter = 0
    mp3_file = os.open(filename, 'rb+')
    while True:
        # Wait for DREQ to go high, indicating VS1053B is ready for more data
        while digitalRead(DREQ_PIN) == LOW:
            print("DREQ LOW")
            sleep(10)
        
        data = mp3_file.read(128)
        counter += 128
        if not data:
            print("EOF ", counter, " bytes read")
            break  # End of file
        send_mp3_data(SCI_WRITE,data)
        
    print("Playback finished")
    print("HDAT: ", read_register(SCI_HDAT0))
    print("HDAT1: ", read_register(SCI_HDAT1))

def ensure_mp3_directory_exists():
    if not os.exists((mp3_dir)) and not (os.getcwd() == "0:/mp3"):
        os.mkdir(mp3_dir)
        print("made directory")
    if not (os.getcwd() == "0:/mp3"):
        os.chdir(mp3_dir)
    print("Directory: ", os.listdir(os.getcwd()))
    
def check_if_file_exists(filename):
    if os.path.exists(filename):
        print("path exists")
        file_instance = os.open(filename, 'rb+')
        print("file instance created")
        print("Size of example: ", file_instance.size())
    else:
        print("File example does not exist.")

def sine_test(n,seconds):
    """Play a sine wave for the specified number of seconds. Useful to
    test the VS1053 is working.
    """
    print("sine test start")
    soft_reset_vs1053()
    mode = read_register(_VS1053_REG_MODE)
    print("mode is: ", mode)
    mode |= 0x0020
    #mode = _VS1053_MODE_SM_SDINEW | _VS1053_MODE_SM_LINE1
    print("mode is: ", mode)
    write_register(_VS1053_REG_MODE, mode)
    while digitalRead(DREQ_PIN) == LOW:
        sleep(10)  # Wait until DREQ is high
    try:
        spiCMD.select()
        #spiCMD.configure(baudrate=_DATA_BAUDRATE)
        spiCMD.write(bytearray([0x53, 0xEF, 0x6E, n, 0x00, 0x00, 0x00, 0x00]))
        spiCMD.unselect()
    except Exception as e:
        print(e)
    sleep(seconds)
    try:
        spiCMD.select()
        #spiCMD.configure(baudrate=_DATA_BAUDRATE)
        spiCMD.write(bytearray([0x45, 0x78, 0x69, 0x74, 0x00, 0x00, 0x00, 0x00]))
        spiCMD.unselect()
    except Exception as e:
        print(e)
    print("sine test finished")
#thread(overload_dreq)
#thread(get_dreq)
#'''
while True:
    try:
        sleep(3000)
        ensure_mp3_directory_exists()
        check_if_file_exists("0:example.mp3")
        #vs1053_init()
        sine_test(0x44,2000)
        #play_mp3('0:example.mp3')
        print("played mp3")
        sleep(2000)
        #overload_dreq()
    except Exception as e:
        print(e)
        sleep(5000)
#'''