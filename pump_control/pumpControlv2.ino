/*

   Programa de control de una bomba hidraulica
   Monitorea la presion


   by Matias Vidal - matiasv@gmail.com - Nov 2016


   Controla que la presion de trabajo este entre los parametros establecidos
   En el caso que la presion salga de estos valores, se detiene el relay
   Reporta la presion detectada via i2C


  Thanks to: https://github.com/MikeOchtman/Pi_Arduino_I2C

  Interface Specification
    Data in a table thus:
      byte purpose
      0: command
      1: control
     2-5: Current Pressure (read-only)
     6-9: Current Water level (read only)
     10: Relay Control read/write
     11: ControlPump Status (read only)

     Control Pump Status:
        PUMP_OFF = 0,
        PUMP_STARTING = 1,
        PUMP_WORKING = 2,
        ALARM_UNDERPRESSURE = 10, // Relay OFF
        ALARM_OVERPRESSURE = 11 // Relay OFF

     Commands:
     Write with no command: Ignore
     Read with no command: Return slave address

     Command 0x81: read Pressure. Integer returned, (mbar)
     Command 0x82: read Water level, Integer returned - TODO!
     Command 0x0A: Write single byte - 0 PUMP_OFF - 1 RELAY_ON - overrides the pin detection - TODO!
     Command 0x0B: Write integer - Change Max Working Pressure (mbar)
     Command 0x0C: Write integer - Change Min Working Pressure (mbar)
     Command 0x0D: Write integer - Change Wait Time to reach pressure (Seconds)
     Command 0x90: read Relay Status
     Command 0x91: read ControlPlugin Status
     Command 0x92: Read Max Working Pressure (mbar)
     Command 0x93: Read Min Working Pressure (mbar)
     Command 0x94: Read Wait Time to reach pressure (Seconds)
*/
#include <Wire.h>
#define DEBUG 0


#define slaveAddress 9 // I2C Address

#define SENSOR_PIN  A7   // Potenciometro o transducer de presion
#define RELAY_PIN  13    // Relay
#define BUZZ_PIN 10   // Buzzer-Speaker
#define IN_PIN 12   // Digital PIN IN

// Sensor Specs - Asumes a Linear Ouput Transducer
#define SENSOR_MAX_PRESSURE 10342 // 150 PSI in Mbar
#define SENSOR_MAX_VOLTAGE 4.5 // V
#define SENSOR_VCC 5 // V


#define MAX_PRESSURE 3800 //  Presion Maxima (millibar)
#define MIN_PRESSURE 500 // Presion Minima (millibar)
#define MAX_WAIT_FOR_PRESSURE 20 // Tiempo Maximo para esperar que el sistema levante presion  (secs) - 20 secs  

#define rxFault 0x80
#define txFault 0x40
#define txRequest 0x20

#define  PUMP_OFF  0
#define  PUMP_STARTING  1
#define  PUMP_WORKING  2
#define  ALARM_UNDERPRESSURE  10 // Relay OFF
#define  ALARM_OVERPRESSURE  11 // Relay OFF


struct {
  byte volatile command;
  byte volatile control; // rxFault:txFault:0:0:0:0:0:0
  int volatile pressure;
  int volatile waterLevel; //For futureUse
  byte volatile relay;
  byte volatile pumpControlStatus;
  int volatile maxPressure;
  int volatile minPressure;
  int volatile waitTimeForPressure;
} commsTable;

byte volatile txTable[32];   // prepare data for sending over I2C
bool volatile dataReady = false; // flag to trigger a Serial printout after an I2C event
// use volatile for variables that will be used in interrupt service routines.
// "Volatile" instructs the compiler to get a fresh copy of the data rather than try to
// optimise temporary registers before using, as interrupts can change the value.





unsigned long lowPressureStart; // millisecs

int lastSensorData = 0 ;

int maxSensorValue = 0;
int minSensorValue = 0;


int inputState = 0;
int lastInputState = 0;


int getPressure(float val) {
  // Formula for a pressure transducer - Linear output
  int p = round(val * SENSOR_MAX_PRESSURE / (SENSOR_MAX_VOLTAGE * 1023 / SENSOR_VCC )) ;
  return p;
}

void setRelay(boolean st) {
  if (st && (commsTable.pumpControlStatus == PUMP_STARTING ) && (commsTable.pressure < maxSensorValue)) {
    // start the relay
    digitalWrite(RELAY_PIN, HIGH);
    commsTable.relay = 1 ;
  } else if (not st) {
    // stop the relay
    digitalWrite(RELAY_PIN, LOW);
    commsTable.relay = 0;
  }
}


//====================================================
/*
   i2cReceive:
   Parameters: integer, number of bytes in rx buffer
   Returns: none
   Function called by twi interrupt service when master sends
   information to the slave, or when master sets up a
   specific read request.
   Incoming data must be processed according to the
   Interface Specification decided upon.
   The first byte sent is a command byte, and this informs
   the slave how to react to the transmission.
   See the end of this document for the Interface Specification
   for this example. Typically, the MSB of "command" is used to
   signal 'read' or 'write' instructions.
*/
void i2cReceive(int byteCount) {
  // if byteCount is zero, the master only checked for presence
  // of the slave device, triggering this interrupt. No response necessary
  if (byteCount == 0) return;

  // our Interface Specification says commands in range 0x000-0x7F are
  // writes TO this slave, and expects nothing in return.
  // commands in range 0x80-0xFF are reads, requesting data FROM this device
  byte command = Wire.read();
  commsTable.command = command;
  if (command < 0x80) {
    i2cHandleRx(command);
  } else {
    i2cHandleTx(command);
  }
  dataReady = true;
}
/*
   i2cTransmit:
   Parameters: none
   Returns: none
   Next function is called by twi interrupt service when twi detects
   that the Master wants to get data back from the Slave.
   Refer to Interface Specification for details of what data must be sent.
   A transmit buffer (txTable) is populated with the data before sending.
*/
void i2cTransmit() {
  // byte *txIndex = (byte*)&txTable[0];
  byte numBytes = 0;
  int t = 0; // temporary variable used in switch occasionally below

  // check whether this request has a pending command.
  // if not, it was a read_byte() instruction so we should
  // return only the slave address. That is command 0.
  if ((commsTable.control & txRequest) == 0) {
    // this request did not come with a command, it is read_byte()
    commsTable.command = 0; // clear previous command
  }
  // clear the rxRequest bit; reset it for the next request
  commsTable.control &= ~txRequest;

  // If an invalid command is sent, we write nothing back. Master must
  // react to the crickets.
  switch (commsTable.command) {
    case 0x00: // send slaveAddress.
      txTable[0] = slaveAddress;
      numBytes = 1;
      break;
    case 0x81:  // send pressure
      t = int(getPressure(commsTable.pressure));
      txTable[1] = (byte)(t >> 8);
      txTable[0] = (byte)(t & 0xFF);
      numBytes = 2;
      break;
    case 0x82:  // send water level
      t = int(round(commsTable.waterLevel));
      txTable[1] = (byte)(t >> 8);
      txTable[0] = (byte)(t & 0xFF);
      numBytes = 2;
      break;
    case 0x90: // send Relay
      txTable[0] = commsTable.relay;
      numBytes = 1;
      break;
    case 0x91: // send pumpControl Status
      txTable[0] = commsTable.pumpControlStatus;
      numBytes = 1;
      break;
    case 0x92:
      t = commsTable.maxPressure;
      txTable[1] = (byte)(t >> 8);
      txTable[0] = (byte)(t & 0xFF);
      numBytes = 2;
      break;
    case 0x93:
      t = commsTable.minPressure;
      txTable[1] = (byte)(t >> 8);
      txTable[0] = (byte)(t & 0xFF);
      numBytes = 2;
      break;
    case 0x94:
      t = commsTable.waitTimeForPressure;
      txTable[1] = (byte)(t >> 8);
      txTable[0] = (byte)(t & 0xFF);
      numBytes = 2;
      break;
      // If an invalid command is sent, we write nothing back. Master must
      // react to the sound of crickets.
      commsTable.control |= txFault;
  }
  if (numBytes > 0) {
    Wire.write((byte *)&txTable, numBytes);
  }
}

/*
   i2cHandleRx:
   Parameters: byte, the first byte sent by the I2C master.
   returns: byte, number of bytes read, or 0xFF if error
   If the MSB of 'command' is 0, then master is sending only.
   Handle the data reception in this function.
*/
byte i2cHandleRx(byte command) {
  // If you are here, the I2C Master has sent data
  // using one of the SMBus write commands.
  byte result = 0;
  // returns the number of bytes read, or FF if unrecognised
  // command or mismatch between data expected and received
  int integer = 0;
  switch (command) {
    case 0x0A: // TODO - Relay control
      if (Wire.available() == 1) { // good write from Master
        //    commsTable.relay = Wire.read(); #TODO
        result = 1;
      } else {
        result = 0xFF;
      }
      break;
    case 0x0B: // Write integer - Change Max Working Pressure (mbar)
      if (Wire.available() == 2) { // good write from Master 2 bytes!
        unsigned char received = Wire.read();
        integer = received;
        received = Wire.read();
        integer |= (received << 8);
        commsTable.maxPressure = integer;
        result = 1;
      } else {
        result = 0xFF;
      }
      break;

    case 0x0C: // Write integer - Change Min Working Pressure (mbar)
      if (Wire.available() == 2) { // good write from Master 2 bytes!
        unsigned char received = Wire.read();
        integer = received;
        received = Wire.read();
        integer |= (received << 8);
        commsTable.minPressure = integer;
        result = 1;
      } else {
        result = 0xFF;
      }
      break;

    case 0x0D: // Write integer - Change Wait Time to reach pressure (seconds)
      if (Wire.available() == 2) { // good write from Master 2 bytes!
        unsigned char received = Wire.read();
        integer = received;
        received = Wire.read();
        integer |= (received << 8);
        commsTable.waitTimeForPressure = integer;
        result = 1;
      } else {
        result = 0xFF;
      }
      break;

    default:
      result = 0xFF;
  }

  if (result == 0xFF) commsTable.control |= rxFault;
  //  printCommsTable();
  return result;

}

/*
   i2cHandleTx:
   Parameters: byte, the first byte sent by master
   Returns: number of bytes received, or 0xFF if error
   Used to handle SMBus process calls
*/
byte i2cHandleTx(byte command) {
  // If you are here, the I2C Master has requested information

  // If there is anything we need to do before the interrupt
  // for the read takes place, this is where to do it.
  // Examples are handling process calls. Process calls do not work
  // correctly in SMBus implementation of python on linux,
  // but it may work on better implementations.

  // signal to i2cTransmit() that a pending command is ready
  commsTable.control |= txRequest;
  return 0;

}
void printTxTable() {
  Serial.println("Transmit Table");
  for (byte i = 0; i < 32; i++) {
    Serial.print("  ");
    Serial.print(i);
    Serial.print(": ");
    Serial.println(txTable[i]);
  }
  Serial.println();
}
void printCommsTable() {
  String builder = "";
  builder = "commsTable contents:";
  Serial.println(builder);
  builder = "  command: ";
  builder += String(commsTable.command, HEX);
  Serial.println(builder);
  builder = "  control: ";
  builder += String(commsTable.control, HEX);
  Serial.println(builder);
  builder = "  pressure: ";
  builder += getPressure(commsTable.pressure);
  builder += "mBAR";
  Serial.println(builder);
  builder = "  Water Level: ";
  builder += commsTable.waterLevel;
  builder += " mts";
  Serial.println(builder);
  builder = "  Relay: ";
  builder += commsTable.relay;
  Serial.println(builder);
  builder = "  PumpControl Status: ";
  switch (commsTable.pumpControlStatus) {
    case ALARM_UNDERPRESSURE: builder += "ALARM_UNDERPRESSURE"; break;
    case ALARM_OVERPRESSURE: builder += "ALARM_OVERPRESSURE"; break;
    case PUMP_OFF: builder += "PUMP_OFF"; break;
    case PUMP_WORKING: builder += "PUMP_WORKING"; break;
    case PUMP_STARTING: builder += "PUMP_STARTING"; break;
  }
  Serial.println(builder);
  builder = "  Max Working Pressure: ";
  builder += commsTable.maxPressure;
  Serial.println(builder);
  builder = "  Min Working Pressure: ";
  builder += commsTable.minPressure;
  Serial.println(builder);
  builder = "  Max Waiting time for Pressure: ";
  builder += commsTable.waitTimeForPressure;
  Serial.println(builder);

  Serial.println();
}

void setup() {
  lowPressureStart = 0 ;
  lastSensorData = 0 ;
  // calculate Operating threshold


  if (DEBUG == 1) {
    Serial.begin(9600);
    while (!Serial) {};
  }
  pinMode(RELAY_PIN, OUTPUT);  // declare the relayPin as an OUTPUT
  digitalWrite(RELAY_PIN, LOW);
  pinMode(BUZZ_PIN, OUTPUT);
  pinMode(IN_PIN, INPUT) ;
  // initialize i2c as slave
  Wire.begin(slaveAddress);
  // define callbacks for i2c communication
  Wire.onReceive(i2cReceive);  // interrupt handler for incoming messages
  Wire.onRequest(i2cTransmit);  // interrupt handler for when data is wanted
  if (DEBUG == 1) {
    Serial.println("Ready!");
    Serial.print("MAX Sensor Read: ");
    Serial.println(maxSensorValue);
    Serial.print("MIN Sensor Read: ");
    Serial.println(minSensorValue);
  }
  commsTable.waterLevel = 1; // TODO
  commsTable.maxPressure = MAX_PRESSURE ;
  commsTable.minPressure = MIN_PRESSURE ;
  commsTable.waitTimeForPressure = MAX_WAIT_FOR_PRESSURE;

  if (DEBUG == 1) {
    printCommsTable();
    printTxTable();
    delay(20);
  }
}


void loop() {
  maxSensorValue = (commsTable.maxPressure * SENSOR_MAX_VOLTAGE / SENSOR_MAX_PRESSURE) * 1023 / SENSOR_VCC ;
  minSensorValue = (commsTable.minPressure * SENSOR_MAX_VOLTAGE / SENSOR_MAX_PRESSURE) * 1023 / SENSOR_VCC ;
  unsigned long waitTimeForPressure = (unsigned long) commsTable.waitTimeForPressure * 1000 ;
  unsigned long enlapsed = 0;
  commsTable.pressure = analogRead(SENSOR_PIN);
  inputState = digitalRead(IN_PIN);




  if (inputState == LOW) {
    commsTable.pumpControlStatus = PUMP_OFF;
  } else if ( commsTable.pressure > maxSensorValue ) {
    commsTable.pumpControlStatus = ALARM_OVERPRESSURE;
  } else if ( lastInputState == LOW )  {
    commsTable.pumpControlStatus = PUMP_STARTING ;
    lowPressureStart = millis();
  } else if (commsTable.pumpControlStatus == PUMP_STARTING ) {
    enlapsed = millis() - lowPressureStart;
    if ((enlapsed > waitTimeForPressure) && (commsTable.pressure < minSensorValue )) {
      commsTable.pumpControlStatus = ALARM_UNDERPRESSURE  ;
    } else if (commsTable.pressure > minSensorValue ) {
      commsTable.pumpControlStatus = PUMP_WORKING ;
    }
  } else if ((commsTable.pumpControlStatus == PUMP_WORKING ) && (commsTable.pressure < minSensorValue )) {
    commsTable.pumpControlStatus = PUMP_STARTING ;
    lowPressureStart = millis();
  }

  switch (commsTable.pumpControlStatus) {
    case PUMP_WORKING: setRelay(HIGH); break;
    case PUMP_STARTING: setRelay(HIGH); break;
    default: setRelay(LOW) ; break;
  }
  lastSensorData = commsTable.pressure ;
  lastInputState = inputState ;


  switch (commsTable.pumpControlStatus) {
    case ALARM_UNDERPRESSURE: tone( BUZZ_PIN, 1000, 30); break;
    case ALARM_OVERPRESSURE: tone( BUZZ_PIN, 3000, 70); break;
  }
  if (DEBUG == 1) {
    if (dataReady) {
      printCommsTable();
      Serial.print("Enlapsed: ");
      Serial.println(enlapsed);
      dataReady = false;
    }
    if (commsTable.control > 0) {
      printTxTable();
      commsTable.control = 0;
    }
  }

  delay(100);                  // stop the program for some time
}

