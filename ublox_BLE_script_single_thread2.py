#!/usr/bin/python
# Right now, the message loop waits until ALL characteristics have been told to send notifcations
# (via UUBTGRW events).
# the code could be structured to send out notifications as soon as ANY of the characteristics have been
# set up on the smart phone.  But it needs changes. This is because if I do it this way now, I begin
# sending UBTGSN commands, and some in-coming events get swallowed in the WriteRead function, because it's 
# only looking for OK or ERROR.
# it would therefore be necessary to detect asynchronous events being received in WriteRead, and to
# inject them into the message loop.
import sys,os, serial, os, time, io, re
#import _thread as thread
#import threading
import binascii, codecs
import calendar # for creating timestamps, etc.

#globals
COMPORT=9
transactionglobal = 1
theport = serial.Serial()
regex = re.compile (r'.*CHA:\d\d,\d+')
RunBGthread : True
conn_handle = -1 # connection handle dished out by +UUBTACLC and needed by SN
mfg_name_handle = -1
Temp1Handle = None
Temp2Handle = None
RefrigerantHandle = None
Pressure1Handle = None
Pressure2Handle = None
VacuumHandle = None
DataBufferHandle = None
HaltOnError = True
AsyncEvents = []
RTCDateHandle = None    # 2018-12-03 New characteristic
ScaleMassHandle = None  # 2018-12-03 New characteristic
SmartPhoneACLHandle = None
IshallSayZeesOnlyOnce = False

def main():
    # test for operating system name
    if (os.name == "nt"):
        comport = "COM" + str(COMPORT)
    else:
        comport = "/dev/ttyS" + str(COMPORT-1)


    # get the serial port open
    theport.port = comport
    theport.baudrate = 115200
    theport.timeout = 3
    theport.open()
    # wait a bit otherwise the buffer won't be accurate
    time.sleep (0.25)
    theport.flush()
    # time.sleep (1.01)
    # theport.write (b"+++")
    # time.sleep (1.1)
    # theport.flushInput() 

    if not (NinaVersionOK("4.0.1-153")):
        print ("Nina version is not recent enough")
        exit()
    #WriteRead ("AT+UFACTORY")
    WriteRead ("AT+UBTCM=2")
    WriteRead ("AT+UBTDM=3")
    WriteRead ("AT+UBTPM=2")
    print ("DEBUG: Setting up central + peripheral mode:")
    WriteRead ("AT+UBTLE=3")                    # 2 is peripheral, 3 is dual-mode
    # print ("DEBUG: Setting number of permissible conntions to 3:")
    WriteRead ("AT+UBTCFG=2,3")                 # 1st param=1 mean "max BLE links", 2nd param = num of links
    WriteRead ("AT+UDSC=0,0")                   # turn off SPS server to increase GATT characteristics capability
    WriteRead ("AT+UBTLECFG=26,1")              # fiddle with MTU size - as above.
    WriteRead ("AT+UBTLN=""REFCOperipheralserver""")
    WriteRead ("AT+UBTLEDIS=REFCO_Ltd,CLA,6.12,1")
    WriteRead ("AT&W")                          # reset 1
    WriteRead ("AT+CPWROFF")                    # reset 2
    #
    # Most of the following few lines can be set with the UBTLEDIS command,
    # and doing so below seems to create a duplicate service, at least on BLE Scanner on Android...
    #
    # # set up device information service
    # WriteRead ("AT+UBTGSER=180A")               # service (180A = Device Info)
    # WriteRead ("AT+UBTGCHA=2A23,10,1,1")        # characteristic System ID
    # WriteRead ("AT+UBTGCHA=2A24,10,1,1")        # characteristic Model Number String
    # WriteRead ("AT+UBTGCHA=2A25,10,1,1")        # characteristic Serial Number String
    # #WriteRead ("AT+UBTGCHA=2A26,10,1,1")        # characteristic Firmware Revision String
    # #WriteRead ("AT+UBTGCHA=2A27,10,1,1")        # characteristic Hardware Revision String
    # mfg_name_handle  = \
    # WriteRead ("AT+UBTGCHA=2A29,10,1,1")        # characteristic Manufacturer Name String
    # print ("handle of manufacturer name string is  : " + str(mfg_name_handle))

    

    RefcoService()

    BatteryService()

    #Here we want to connect with a smartphone or an other ble device
    print ('Please connect smart-phone to REFCOperipheralserver')
    MessageLoop()
   





def WriteRead(stringIn):
    global transactionglobal, Temp1Handle, Temp2Handle
    global AsyncEvents
    debugplease = True
    returnvalue=""
    answer =""
    if debugplease:
        print()
        print ("Transaction " + str(transactionglobal))
        print ("OUT: " + stringIn)
    transactionglobal = transactionglobal+1
    #stringIn = stringIn + "\r"
    theport.write(stringIn.encode() + b'\r')
    # read output from NINA until OK or ERROR
    while ((answer != "OK") and (answer != "ERROR")):
        answer = theport.readline().rstrip().decode()
        if debugplease: print ("IN:  " + answer)
        if (answer != "OK" and answer != "ERROR"): returnvalue = answer

        if answer[0:3] == "+UU":
            # we've got an event popped up that's nothing to do with the current message
            AsyncEvents.append(answer)
            print("DEBUG:")
            print  ("DEBUG: Parking this event for later: ", answer)
            print ("DEBUG:")

        if (HaltOnError):
            if (answer.upper() == "ERROR"):
                exit()

        # if this is defining a characteristic, grab the handle for later use
        if (regex.match (answer)):
            returnvalue = int(answer.split(':')[1].split(',')[0])
    
    # special case: wait for "+STARTUP" afterwards if the command was CPWROFF
    if (stringIn.upper() == "AT+CPWROFF"):
        while (answer.upper() != "+STARTUP"):
            try:
                answer = theport.readline().rstrip().decode()
                if debugplease:  print ("IN: " + answer)
            finally:
                pass

    return returnvalue






def MessageLoop():
    global AsyncEvents,SmartPhoneACLHandle, IshallSayZeesOnlyOnce
    timeout = False
    global theport
    SendNotifications = False
    message=""
    ConnectionCounter = 1
    UUBTGRW_list = [] # list of handles of characteristics that have had the request from the connected device

    theport.timeout = 1
    while (1):
        # if connected, send notifications to show something changing
        if SendNotifications and len(UUBTGRW_list) > 0:
            #print ("Send notifications {0}".format(ConnectionCounter))
            #print ("List of handles is ", UUBTGRW_list)
            ConnectionCounter = ConnectionCounter + 1
            # refrigerant name
            if RefrigerantHandle in UUBTGRW_list :
                print ("R410A")
                dastring = "AT+UBTGSN={2},{0},{1}".format(RefrigerantHandle,  str(codecs.encode(bytearray("R410A", "ascii"), "hex"), "ascii"), SmartPhoneACLHandle)
                WriteRead (dastring)
            # temperature 1
            if Temp1Handle in UUBTGRW_list:
                TemperatureString = "{0} C".format (-40 + ConnectionCounter % 100)
                print ("Temp1 = {0}".format (TemperatureString))
                dastring = "AT+UBTGSN={2},{0},{1}".format(Temp1Handle,  str(codecs.encode(bytearray(TemperatureString, "ascii"), "hex"), "ascii"), SmartPhoneACLHandle)
                WriteRead (dastring)
            # temperature 2
            if Temp2Handle in UUBTGRW_list:
                TemperatureString = "{0} C".format (-40 + (ConnectionCounter+20) % 100)
                print ("Temp2 = {0}".format (TemperatureString))
                dastring = "AT+UBTGSN={2},{0},{1}".format(Temp2Handle,  str(codecs.encode(bytearray(TemperatureString, "ascii"), "hex"), "ascii"),SmartPhoneACLHandle)
                WriteRead (dastring)
            if Pressure1Handle in UUBTGRW_list:
                PressureString = "{0} BAR".format (-1 + ConnectionCounter % 12)
                print ("Pressure 1 = " + PressureString)
                dastring = "AT+UBTGSN={2},{0},{1}".format(Pressure1Handle,  str(codecs.encode(bytearray(PressureString, "ascii"), "hex"), "ascii"),SmartPhoneACLHandle)
                WriteRead (dastring)
            if Pressure2Handle in UUBTGRW_list:
                PressureString = "{0} BAR".format (-1 + ConnectionCounter % 32)
                print ("Pressure 2 = " + PressureString)
                dastring = "AT+UBTGSN={2},{0},{1}".format(Pressure2Handle,  str(codecs.encode(bytearray(PressureString, "ascii"), "hex"), "ascii"),SmartPhoneACLHandle)
                WriteRead (dastring)
            if VacuumHandle in UUBTGRW_list:
                #VacuumString = "{0} MICRON".format ((ConnectionCounter % 51) * 2000)
                a = ramp(75000,   10000,  0, 10, 240, ConnectionCounter)
                b = ramp(10000,   50,  10, 240-10-1, 240, ConnectionCounter)
                VacuumString = "{:08.2f} MICRON".format(max(a,b))
                print ("Vacuum = " + VacuumString)
                dastring = "AT+UBTGSN={2},{0},{1}".format(VacuumHandle,  str(codecs.encode(bytearray(VacuumString, "ascii"), "hex"), "ascii"),SmartPhoneACLHandle)
                WriteRead (dastring)
            if RTCDateHandle in UUBTGRW_list:
                RTCDateString = "DD-MM-YYYY"
                print ("RTCDate = " + RTCDateString)
                dastring = "AT+UBTGSN={2},{0},{1}".format(RTCDateHandle,  str(codecs.encode(bytearray(RTCDateString, "ascii"), "hex"), "ascii"),SmartPhoneACLHandle)
                WriteRead (dastring)
            if ScaleMassHandle in UUBTGRW_list:
                ScaleMassString = "75.5 KG"
                print ("Scale Mass = " + ScaleMassString)
                dastring = "AT+UBTGSN={2},{0},{1}".format(ScaleMassHandle,  str(codecs.encode(bytearray(ScaleMassString, "ascii"), "hex"), "ascii"),SmartPhoneACLHandle)
                WriteRead (dastring)
            if DataBufferHandle in UUBTGRW_list:
                if IshallSayZeesOnlyOnce != True:
                    with open ("logfile.csv") as fp:
                        randomcounter = 0
                        for line in fp:
                            line = "I am twenty-one bytes"
                            randomcounter = randomcounter + 1
                            print ("It's " + line.strip())
                            dastring = "AT+UBTGSN={2},{0},{1}".format(DataBufferHandle,  str(codecs.encode(bytearray(line.strip(), "ascii"), "hex"), "ascii"),SmartPhoneACLHandle)
                            WriteRead (dastring)
                            time.sleep (0.05)
                    IshallSayZeesOnlyOnce = True

            print ("")

        if len(AsyncEvents) == 0:
            message = theport.readline().rstrip().decode()
        else:
            message = AsyncEvents.pop(0)
            print ("Processing async event : ", message)

        # print dots whilst timing out
        if ( len (message) == 0):
            #if (not timeout):
                #print()
            timeout = True
            sys.stdout.write ('.')
            sys.stdout.flush()
            continue

        # newline if we've been printing dots
        if (timeout):
            print()
            timeout = False


        print ('IN:  ' + message)

        # Connection notification event
        if (message[0:9] == '+UUBTACLC'):
            print ('ACL connection completed')
            # if (not SendNotifications):
            #     SendNotifications = True
            #     time.sleep(1)
            # 2018-12-10  Now that we've set things up for multiple connections (UBTLE=3), we will get back handles that aren't 0
            # for the connection.  So now we need to keep the handle, and refer to it when sending notifications.
            SmartPhoneACLHandle =  message.split(":")[1].split(",")[0]
            print ("DEBUG: the handle for the ACL is ", SmartPhoneACLHandle)
            continue

        # Write request
        if (message[0:8] == '+UUBTGRW'):
            # e.g. +UUBTGRW:0,33,0100,1
            _,b,c,_ = message.split (",")
            b = int(b)-1 # the minus one is because we get two handles when creating characteristics, and this is the upper handle
            if c == '0100':
                if not b in UUBTGRW_list:
                    UUBTGRW_list.append (b)
                    print ("The list of handles for notifications is now ", UUBTGRW_list)

            if c == '0000':
                if b in UUBTGRW_list:
                    UUBTGRW_list = UUBTGRW_list.remove (b)

            if len (UUBTGRW_list) > 0:
                print ("Now sending notifications")
                if (not SendNotifications):
                    SendNotifications = True
                    #time.sleep(1)
            else:
                print ("No longer sending notifications")
                SendNotifications = False
            continue

        # Read request
        if (message[0:8] == '+UUBTGRR'):
            # print ('request to read')
            # ReadRequest(message)
            # if (not SendNotifications):
            #     SendNotifications = True
            #     time.sleep(1)
            continue

        # Disconenction notification event
        if (message[0:9] == '+UUBTACLD'):
            print ('ACL disconnected')
            # don't send notifications when not connected!
            SendNotifications = False
            continue






def BatteryService():
    # setup  battery service
    print ("Battery Service set-up: BEGIN")
    WriteRead ("AT+UBTGSER=180F")                                           # Battery Service
    WriteRead ("AT+UBTGCHA=2A19,10,1,1")                                    # Battery Level
    print ("Battery Service set-up: END")




def RefcoService():
    global Temp1Handle, Temp2Handle, Pressure1Handle, Pressure2Handle, RefrigerantHandle, VacuumHandle, RTCDateHandle, ScaleMassHandle, DataBufferHandle
    #setup device data service  # use UUID without connecting line
    WriteRead ("AT+UBTGSER=b0897c037fdd42a499abef47e3fe574f")
    #WriteRead ("AT+UBTGCHA=34832c10687d4eedb17f8b14f5ce70ea,12,1,1")        # Device State
    #WriteRead ("AT+UBTGCHA=854abe1146474a598fd2062278a6b691,12,1,1")        # Device Alarms
    #WriteRead ("AT+UBTGCHA=efa28478f59f431b832c89df618f4de2,12,1,1")        # Reader Time Period
    #WriteRead ("AT+UBTGCHA=5136a9ae032d4f16a9462a062abf6b85,12,1,1")        # Number of Connected Devices
    #WriteRead ("AT+UBTGCHA=7e6613f156fe46719c01f6605d5643f5,12,1,1")        # Transmitter Power (error in GATT definition confusing TX Power with RSSI)
    #WriteRead ("AT+UBTGCHA=775bf19859854a7596e32001ca1eba83,12,1,1")        # URL
    RefrigerantHandle = \
    WriteRead ("AT+UBTGCHA=a76f5dc0ba6648a5b5db193f77bf9cdb,12,1,1,{0},0,20".format(StrToByteArray("R410A")))        # Refrigerant Name
    #WriteRead ("AT+UBTGCHA=2a840c865ad742d6b0d0733ff134c215,12,1,1")        # Device Temperature Unit
    #WriteRead ("AT+UBTGCHA=3967993db8f84cacbddf65c38e452592,12,1,1")        # Device Pressure Unit
    #WriteRead ("AT+UBTGCHA=c124f471567d40e89d7a761dd2731fa7,12,1,1")        # Device Vacuum Unit
    #WriteRead ("AT+UBTGCHA=979916f01fcd4bb89f79947cc0537f4d,12,1,1")        # Device Weight Unit
    #WriteRead ("AT+UBTGCHA=e780891363cb46b79898faa82dd4308f,12,1,1")        # Device Rotational Speed Unit
    #WriteRead ("AT+UBTGCHA=0af20aa48de1424da2dfc908b7f27b96,12,1,1")        # Device Valve Status
    Temp1Handle = \
    WriteRead ("AT+UBTGCHA=dd5ef8d7f96a42d4ba4cf4028a7232f5,12,1,1,{0},0,20".format( StrToByteArray("0 C")))         # Device Temperature 1 Value
    Temp2Handle = \
    WriteRead ("AT+UBTGCHA=d4246dc425a040e0b34f45655882aa05,12,1,1,{0},0,20".format(StrToByteArray("10 C")))        # Device Temperature 2 Value
    Pressure1Handle = \
    WriteRead ("AT+UBTGCHA=a4ac522539734fb987e5e8d86ff0a528,12,1,1,{0},0,20".format(StrToByteArray("-10 BAR")))      # Device Pressure 1 Value
    Pressure2Handle = \
    WriteRead ("AT+UBTGCHA=87395d5d16774d6daa5a8242614c09d6,12,1,1,{0},0,20".format(StrToByteArray("20 BAR")))       # Device Pressure 2 Value
    VacuumHandle = \
    WriteRead ("AT+UBTGCHA=ef6111aec3ed4925af6e2f4c7183774b,12,1,1,{0},0,20".format(StrToByteArray("200 MICRON")))       # Device Vacuum pressure 1
    # WriteRead ("AT+UBTGCHA=ef6111aec3ed4925af6e2f4c7183774b,12,1,1")        # Device Vacuum Value
    # #WriteRead ("AT+UBTGCHA=95ab2f3ccc0640d0a23741c3a9f0ac40,12,1,1")        # Device Weight Value
    # #WriteRead ("AT+UBTGCHA=c31201094d5e4d4b848de80ad27aa91e,12,1,1")        # Device Rotatational Speed Value
    # #WriteRead ("AT+UBTGCHA=bcbacc6c2c394d40ae3fc158c7216ec8,12,1,1")        # Device Set Value
    # WriteRead ("AT+UBTGCHA=619b13b76fb1492a98a24fdfb85970c7,12,1,1")        # Device Date
    # WriteRead ("AT+UBTGCHA=271cb57aa96c44e382eddb9443591c27,12,1,1")        # Device Time

    RTCDateHandle = \
    WriteRead ("AT+UBTGCHA=11c175e560984c7984e85f27b2c65aba,12,1,1,{0},0,20".format(StrToByteArray("DD.MM.YYYY")))       # RTC Date

    ScaleMassHandle = \
    WriteRead ("AT+UBTGCHA=cd0ba6a0c1ce418883c2d7489afc7d2c,12,1,1,{0},0,20".format(StrToByteArray("0 KG")))       # Scale reading (Mass)

    DataBufferHandle = \
    WriteRead ("AT+UBTGCHA=cd0ba6a0c1ce418883c2d7489afc7d2d,12,1,1,{0},0,160".format(StrToByteArray("0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF")))       # Data Buffer





def ReadRequest (StringIn):
    global RefrigerantHandle, Temp1Handle, Temp2Handle, Pressure1Handle, Pressure2Handle, VacuumHandle, RTCDateHandle, ScaleMassHandle, DataBufferHandle
    print ("Read Request service routine")
    print ("Message from Nina BLE: ""{0}""".format(StringIn))
    
    handle = StringIn.split(",")[1]
    if ( handle == str(RefrigerantHandle)):
        # dastring = "AT+UBTGRR={0},{1}".format(RefrigerantHandle,  str(codecs.encode(bytearray("R410A", "ascii"), "hex"), "ascii"))
        dastring = "AT+UBTGRR={0},{1}".format("0",  str(codecs.encode(bytearray("R410A", "ascii"), "hex"), "ascii"))
        WriteRead (dastring)
        return

    if (handle == str(Temp1Handle)):
        # currently send a random string based on the time in seconds since epoch
        TemperatureString = "{0} deg C".format (-40 + calendar.timegm(time.gmtime()) % 100)
        # dastring = "AT+UBTGRR={0},{1}".format(Temp1Handle,  str(codecs.encode(bytearray(TemperatureString, "ascii"), "hex"), "ascii"))
        dastring = "AT+UBTGRR={0},{1}".format("0",  str(codecs.encode(bytearray(TemperatureString, "ascii"), "hex"), "ascii"))
        WriteRead (dastring)
        return

    if (handle == str(Temp2Handle)):
        # currently send a random string based on the time in seconds since epoch
        TemperatureString = "{0} deg C".format (-40 + calendar.timegm(time.gmtime()) % 100)
        # dastring = "AT+UBTGRR={0},{1}".format(Temp2Handle,  str(codecs.encode(bytearray(TemperatureString, "ascii"), "hex"), "ascii"))
        dastring = "AT+UBTGRR={0},{1}".format("0",  str(codecs.encode(bytearray(TemperatureString, "ascii"), "hex"), "ascii"))
        WriteRead (dastring)
        return
    # return


# convert a string to a hex "byte array" of the type used by uBlox AT commands.
def StrToByteArray (InString):
    return str(codecs.encode(bytearray(InString, "ascii"), "hex"), "ascii")


def NinaVersionOK (min_version_string):
    min_version = [int(x) for x in re.split("[-.]", min_version_string)]
    actual_version_string = WriteRead ("AT+GMR")
    actual_version = [int(x) for x in re.split("[-.]", actual_version_string[1:-1])]
    print ("DEBUG: actual version string is ", actual_version)
    # major version
    if (actual_version[0] > min_version[0]): return True
    if (actual_version[0] < min_version[0]): return False

    # major versions match.  Test next level
    # minor version
    if (actual_version[1] > min_version[1]): return True
    if (actual_version[1] < min_version[1]): return False

    # minor versions match. Test next level
    if (actual_version[2] > min_version[2]): return True
    if (actual_version[2] < min_version[2]): return False

    # minor-minor versions match.  Test the dash revision
    #if (actual_version[3] > min_version[3]): return True
    if (actual_version[3] < min_version[3]): return False

    return True

 


def ramp(startval, endval, delay, ramptime, period, t):
    # wrap time if it's > period
    t = t % period
    if (t < delay):
        return 0.0
    if (t > delay + ramptime):
        return 0.0

 
    return (endval - startval) * (t-delay) / ramptime + startval






# execute main() function
main()



# str(codecs.encode(b"Hello", "hex"), "ascii")
