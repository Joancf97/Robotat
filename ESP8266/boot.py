import  os, machine, network, gc
import btree

#Parametros para la conexion de wifi y al servidor MQTT
url_server = ""   
ip_server_mqtt = ""
ssid = ""
password = ""

'''
Por medio de esta funcion se crea la base de datos, donde se almacenan los datos generales de los agentes y se almacena
con los valores predefinidos. Si la base de datos ya existe unicamente se cargan los datos necesarios para la conexion
y luego de llama a la funcion coneccionWIFI() a la cual le pasamos los parametros para conectarnos a la red Wifi
'''
def WIFI():
    global url_server, ip_server_mqtt, ssid, password
    
    if 'swarmdb' in os.listdir():                   #Verificamos si ya existe la base de datos
        f = open("swarmdb", "r+b")                  #Abrimos el archivo
        db = btree.open(f)                          #Abrimos la base de datos
        #Leemos los valores deseados y convertimos a string
        url_server        = db[b"urlserver"].decode('utf-8')               
        ip_server_mqtt    = db[b"ipserver"].decode('utf-8') 
        ssid              = db[b"ssid"].decode('utf-8') 
        password          = db[b"password"].decode('utf-8')
        db.close()                                  #!!IMPORTANTE -> Cerramos base de datos  
        f.close()                                   #!!IMPORTANTE -> Cerramos archivo 
    else:                             
        #Si no existe la base dedatos, creamos una e ingresamos los valores default                                 
        f = open("swarmdb", "w+b")                     #Creamos le archivo
        db = btree.open(f)                          #Creamos la base de datos
        #Ingresamos los valores a guardar como bytes  ->   db[KEY] = VALOR
        db[b"urlserver"] = b"http://192.168.1.9/Bootloader/MainServidor.py"
        db[b"ipserver"]  = b"192.168.1.9"
        db[b"ssid"]      = b"CLARO1_1B478E"
        db[b"password"]  = b"387O5hxabM"
        db[b"topSubs"]   = b"AgentesSwarm"
        #Extraemos los datos de la base de datos
        url_server        = db[b"urlserver"].decode('utf-8')    
        ip_server_mqtt    = db[b"ipserver"].decode('utf-8') 
        ssid              = db[b"ssid"].decode('utf-8') 
        password          = db[b"password"].decode('utf-8') 
        db.flush()                                  #Guardamos los datos
        db.close()                                  #!!IMPORTANTE -> Cerramos base de datos  
        f.close()                                   #!!IMPORTANTE -> Cerramos archivo  
    coneccionWIFI(ssid, password)                   #Nos conectamos a la red


'''
Realiza la coneccion a la red WIFI especificada, por medio de un objeto tipo station
Parametros: 
   SSDI: Red WLAN a conectar 
   password: Contraseña de la red'
'''
def coneccionWIFI(SSDI,Password):
    sta_if = network.WLAN(network.STA_IF)            # Creamos objeto tipo station
    ap_if = network.WLAN(network.AP_IF)              # Creamos AP
    #mac = sta_if.config('mac')                       # Obtenemos el MAC addrres (Futuros cambios)
    if (ap_if.active()):                             # Comprobamos que el modo AP este activado.
        ap_if.active(False)                          # Desactivamos modo AP 
    if not sta_if.isconnected():                     # Verificamos coneccion a la red WIFI
        print ("Conectando a la red WiFi 2.5GHz")
        sta_if.active(True)                          # Activamos el modo station.
        sta_if.connect(SSDI, Password)               # Conectamos a la red con los parametros indicados
        while not sta_if.isconnected():              # Esperams aquí hasta que se conecte.
                    pass 
WIFI()
gc.collect()                                         #Garbage collector  