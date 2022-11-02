# Documentation for the SIP Node-RED extension  
The node-red extension is designed to integrate node red with SIP so that node-red flows can get (read) and set (write) SIP variables.
You can see a full list of accessible variables in the **[gv_reference.txt](https://github.com/Dan-in-CA/SIP/blob/P3-only/gv_reference.txt)** file with a description of each variable.  
  
## Node-RED messages  
The node-red extension enables two-way communication between node-red and SIP by using messages in JSON, a standard data interchange and file format.  
JSON provides a bridge between SIP's Python code and node-red's JavaScript code.
The extension uses HTTP GET and POST requests to receive and send data from and to SIP.  
  
- GET requests are sent from node-red to read data from SIP.  
- POST requests are used to change SIP settings and control SIP's operation.  
  
Using the two different request types eliminates the need for the message to indicate if it is being used to read or write data.  
Messages the extension uses are kept as simple and uniform as possible.  
  
SIP's data and configuration is stored in named variables. All of SIP's settings and control variables can be read by node-red and most of them can be changed (written).  
There are 2 basic types of data in SIP's variables:  
  
- Single value data including boolean values (on/off, true/false, 1/0)  
- List data, consisting of multiple values stored in an array or as bits in a byte (bit flags) 
  
In the next section you will see a series of example JSON messages that can be used to get status information or control SIP.  
  
### message format
Let's take a look at the general format of a message.  
A message is in the form of a JSON object. It is enclosed in curly braces, { and }.  
Inside the braces are one or more **name–value pairs** consisting of a **name (key)** in double quotes followed by a **colon :** then a **value** that can be a number, a string in double quotes, an array or a JSON object.  
For example, the message to read SIP's manual mode setting would be:  
**{"sd":"mm"}**  
where the name **"sd"** indicates a setting in SIP's **Settings Dictionary**  
and the value **"mm"** is the current **manual mode** setting.  
SIP will return 0 if not in manual mode or 1 if  manual mode is on.  

If you request the value of a SIP variable that is a list (array), SIP will return the entire array.  
you can request only one or just a few elements from a list such as station names **(gv.snames)** using a name–value pair with a value that is an array enclosed in double quotes:  
**{"gv":"snames", "station":"[1, 2, 3]"}**  
SIP will return an array of the name(s) corresponding to the station number(s) in the **"station"** pair.
Note that the name–value pairs are separated by a comma.  
Some name–value pairs in the example messages below are optional and the node-red extension will supply a default value if the pair is not included in the message. Also, a few of the commonly used key names have short alternate names such as **"station"** and **"sn"**.  
  
## Example messages  
### GET messages that read SIP settings and status:  
**Get gv and sd value(s):**  
**{"gv":"\<name\>"}**  
or  
**{"sd":"\<name\>"}**  
Read the current value of any of the 25 gv or 38 sd variables listed in the **[gv_reference.txt](https://github.com/Dan-in-CA/SIP/blob/P3-only/gv_reference.txt)** file. Replacing **\<name\>** with the name of the variable to be read.  
Returns a single value or an array depending on the variable.

**Get gv station values:**  
**{"gv":"\<name\>", "station":"[1, 3, 5]"}**  
or  
**{"gv":"\<name\>", "sn":"[1, 3, 5]"}**  

Returns a JSON object containing current value(s) for one or more stations from any of the 6 station related gv variables, indicated in the **gv_reference.txt** file by **[S]**.  

**Get list item(s) (counting from 1):**  
**{"gv":"\<name\>", "item":"[1, 2, 3]"}**  
A generic message to select one or more elements from a variable holding an array. **Item numbers** start from **1** Replacing **"\<name\>"** with the name of the variable.  

Returns a JSON object containing current value(s) for the specified element(s) of the variable

**Get list item(s) by index (counting from 0):**  
**{"gv":"\<name\>", "index":"[0, 1, 2]"}**  
A generic message to select one or more elements from a variable holding an array.
**Index numbers** start from **0** and are equal to item number - 1 Replacing **"\<name\>"** with the name of the variable.   

Returns a JSON object containing current value(s) for the specified element(s) of the variable  

**Get bits from a byte (bit flags):**  
**{"sd":"\<name\>", "bit":"[1, 4, 6, 13]"}**  
A message to get the setting(s) of one or more items stored as a bit in a byte (bit flags) indicated in the gv_refrence.txt file as **[0]** **[8]** or **[255]**. 

### POST messages that change settings and control SIP's operation: 

**Change an sd or gv setting:**  
**{"sd":"\<name\>", "val":x, "save":0}**  
or  
**{"gv":"\<name\>", "val":x}**  
**"sd"** refers to the SIP **Settings Dictionary** that holds SIP configuration settings.   
**"gv"** refers to SIP **Global Variables** that hold status information and control values.  
See the **[gv_reference.txt](https://github.com/Dan-in-CA/SIP/blob/P3-only/gv_reference.txt)** file in the SIP folder for a list that describes each of the sd and gv settings.  
Replace **"\<name\>"** with the name of the setting to be changed.  
**"val"** (required) is the new value the setting should have. It can be a number, a string in double quotes, an array in square brakets, or a JSON object in curly braces depending on the type of value to be changed. **Boolean values** should be **1** for **true** or **0** for **false**.  
**"save"** (optioinal) controls if the **"sd"** setting will be saved to a file (**sd.json**) in the SIP/data folder.  
If "save" is **0** (default) or if "save" is not used, the setting will only be changed in memory and will not survive a software re-start or system reboot.  
If "save is **1**, the **"sd"** setting will persist in the file.  
**"gv"** values are not saved to a file.

**Turn one or more stations on or off:**  
**{"sn":[3,5], "set":1, "req mm":1}**  
or  
**{"station":[3], "set":0, "req mm":1}**  
The required key **name** can be **"sn"** or **"station"**. Either will work.  
The **value** is an **array** of one or more station numbers seperated by commas.  
if **"set"** (required) is **1** the station(s) will be turned on. If **"set"** is **0** the station(s) will be turned off.  
**"req mm"** (optional) means **Require manual mode**. If it is **1** (default) or **"req mm"** is **not used**, SIP must be manual mode for this request to work.  
if **"req mm"** is **0**, stations will be turned on or off even if SIP is not in manual mode and other stations are running.  

**Set station related gv list values:**  
**{"gv":"\<name\>", "sn":{"1":[x,x,x],"2":[x,x,x]}}**    
A message to set one or more values in a station related **"gv"** list variable. Indicated by **[S]** in gv_reference.txt.  
Replace **"\<name\>"** with the name of the variable to change.  
The **value** of the **"sn"** pair is a **JSON object** contining one or more **name-value** pairs with the **name** a station number in double quotes and the **value** an array of values. The number and type of elements in the array depend on the length and type of list the variable holds.

**Set gv list item by item number:**  
**{"gv":"\<name\>", "item":{"1":x, "2":x} }**  
A generic message for setting one or more elements in a **gv**  list variable. Indicated by **[X]** in gv_reference.txt. **X** being a number or letter.  
Replace **"\<name\>"** with the name of the variable to change.  
The **value** of the **"item"** pair is a **JSON object** contining one or more **name-value** pairs with the **name** an item number in double quotes. The **value** depends on the type of elements in the array the variable holds.  
Item numbers are counted starting from 1.  

**Set gv list item by index:**  
**{"gv":"\<name\>", "index":{"0":x, "1":x} }**  
A generic message for setting one or more element in a **gv** list variable. Indicated by **[X]** in gv_reference.txt. **X** being a number or letter.  
Replace **"\<name\>"** with the name of the variable to change. The **value** of the **"index"** pair is a **JSON object** contining one or more **name-value** pairs with the **name** an index number in double quotes. The **value** depends on the type of elements in the array the variable holds.  
Index numbers are counted starting from 0.  

**Turn "sd" bits on or off in a byte (bit flags)**  
**{"sd":"\<name\>", "bit":{"1":1, "2":0, "3":1}}**  
The SIP Settings Dictionaary includes a few variables that store boolean values as bits in a byte (bit flags.). These are settings on the stations page that have check boxes as input. They are listed in gv_reterence.txt as: 
- ir (ignore rain)
- iw (ignore plugin adjustments and water level)
- mo (activate master)
- show (show the station in the SIP UI "enable")

Replace \<name\> with the name of the variable you want to change. The **"bit"** pair has a value that is a JSON dictionary containing **name-value** pairs where the **name** is a station number in double quotes and the **value** is **1** to enable the setting or **0** to disable. 

**Start a run once program.**  
**{"ro":`[[2, 10], [3,10], [5,5]]`, "preempt":1}**  
or  
**{"run once":`[[2, 10], [3,5], [5,5]]`, "preempt":1}**    
The required name can be **"ro"** or **"run once"**. Either will work.  
The **value** (required) is an array of 2 element sub-arrays (note the double **[[** and **]]** at the start and end). Each 2 element inner array contains a station number and the time in seconds for it to run.  
In the example shown above the first inner array **[2,10]** has station 2 running for 10 seconds  
**"preempt"** (optional) controls if a program that is already running will be ended (preempted) when the run once program starts.  
If **"preeempt"** is **1** (default) or if **"preempt"** is **not used**, any running program will be ended.  
If **"preempt"** is **0**, the run once program will be run allong with any already running program


