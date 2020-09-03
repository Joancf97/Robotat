import ustruct as struct
import os, socket, time, machine              
from boot import url_server, ip_server_mqtt   #Variables de conexion 
import btree                                  #Acceso a la base de datos
from json import loads                        #Convertir de objeto json a diccionario

#Bandera para verificar cuando nos envian el diseño de la red
diseño_red  = False

#Extraemos los topicos a los que el  agente se subscribira
f = open("swarmdb", "r+b")                         #Abrimos el archivo
db = btree.open(f)                                 #Abrimos la base de datos
topicos_subscrito = db[b"topSubs"].decode('utf-8') #Obtenemos los topicos a subscribirnos
db.close()                                         #!!IMPORTANTE -> Cerramos base de datos  
f.close()                                          #!!IMPORTANTE -> Cerramos el archivo

#================================================================================================
#                                   Boorloader -> Servidor
#================================================================================================
'''
Se abre un socket, por medio del cual se realiza un request al servidor con la direccion el archivo. Si el request fue exitoso, 
se crea un nuevo archivo llamado ArchivoServidor.py, en el cual se escribe todo el contenido del archivo solicitado del servidor. 
Luego se procede a cambiar el nombre de los archivos y reiniciar el microcontrolador para unitizar el nuevo main (Controlador).
'''
def Request_Archivo_Servidor():
    #La respuesta del request se lee de 100 en 100 bytes (var data) y se van acumulando en la variable DataTotal.
    #Luego se realiza un split para separar el contenido del request del archivo solicitado
    #--> Formato respuesta solicitud 
         #Headers de la respuesta 
         #Connection: close     <-Punto de referencia para el split
         #Archivo solicitado    <-Informacion almacenada en la avriable DataArchivo
    DataTotal = ''              #Lectura total del request                                                      
    DataArchivo = ''            #Lectura parcial del request
    _, _, host, path = url_server.split('/', 3)                                     #Obtenemos el dominio y ruta del archivo
    addr = socket.getaddrinfo(host, 80)[0][-1]
    s = socket.socket()                                                             #Abrimos socket para request
    s.connect(addr)
    s.send(bytes('GET /%s HTTP/1.0\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))    #Enviamos request
    while True:                                                                     #si la peticion es efectiva leemos el archivos cada 100 bytes 
        data = s.recv(100)
        if data:
            #print(str(data, 'utf8'), end='')                                        #Debug del request
            DataTotal += str(data, 'utf8')                                          #Acumulamos toda la informacion leida
        else:
            break
    s.close()                                                                      
    DataArchivo = DataTotal.split("Connection: close")                              #Separamos el request del archivo (En caso exitoso)
    if(len(DataArchivo) == 2):                                                      #Verificamos si el request fue exitoso
        f = open('ArchivoServidor.py','w')
        f.write(DataArchivo[1])                                                     #Escribimos la informacion del controlador en el archivo
        f.close()
        if (not copia_main_existe()):
            os.rename('main.py','Swarm.py')                                         #Guardamos copia del main original
        os.rename('ArchivoServidor.py','main.py')                                   #main.py para que sea el nuevo archivo principal
        machine.reset()                                                             #reiniciamos -> trabajar con el controlador (main.py)

#================================================================================================
#                                        Comunicacion -> MQTT
#================================================================================================
mqtt_server =  ip_server_mqtt              #Variables para la conexion al servidor MQTT             
client_id = "Amarillo"
topico_asistencia = "AgentesReporteID"     #Topicopara reportar el ID al inicio 
topico_general = 'AgentesSwarm'            #Topico por donde obtendremos los comando de la  aplicacion

#Funcion para conectarnos al topico general para reportarnos a la aplicacion
def Reportar_Agente():
    global client_id, mqtt_server
    client = MQTTClient(client_id, mqtt_server, 1883)
    client.set_callback(msj_callback)
    client.connect()                                
    client.subscribe(topico_general)              #Subscripcion al topico General
    client.publish(topico_asistencia, client_id)  #Reportamos nuestro ID a la app    
    print('Conectado a %s MQTT broker, id %s reportado' % (mqtt_server, client_id))
    return client                                 #Regresamos el objeto de la conexion MQTT - unicamente se utiliza en el main.py original

#Nos conectamos a cada uno de los topicos indicados por el usuario  al momento de disenar la red
def Robotat():
    global client_id, mqtt_server, topicos_subscrito
    client = MQTTClient(client_id, mqtt_server, 1883)
    client.set_callback(msj_callback)
    client.connect()
    topicos_a_subscribir = topicos_subscrito.split(",")   #Obtenemos todos los topicos a los que nos tenemos que subscribirnos
    for topico in topicos_a_subscribir:                   #Nos subscribimos a dichos topicos
        client.subscribe(topico)                  
        print("Agente conectado al topico " + topico) 
    return client                                 #Regresamos el objeto de la conexion MQTT - unicamente se utiliza en el controlador descargado

#Callback al momento de obtenerun mensaje. No se utiliza por el momento
def msj_callback(topic, msg):
    return  

#Cuando falla el intento de conexion al broker se reinicia el microcontroladro para volver a intenera el proceso nuevamente
def Connection_Fail(): 
    #Se notifica por hardware al usuario
    time.sleep(1)
    time.sleep(1)
    time.sleep(1)
    print('Failed to connect to MQTT broker. Reconnecting...')
    machine.reset()                            #Reiniciamos el microcontrolador

#Verificamos si ya wxiste la copia del main original, el cual se llama Swarm.py
def copia_main_existe():
    for archivo in os.listdir():               #Reestablecemos los archivos en caso sea necesario
        if('Swarm.py' == archivo):
            return True 
    return False 

#======================================Case para  la conexion a MQTT ======================================
#Codigo obtenido de la libreria de micropython para implementar MQTT
#https://github.com/micropython/micropython-lib/blob/master/umqtt.simple/umqtt/simple.py
class MQTTException(Exception):
    pass
class MQTTClient:
    def __init__(self, client_id, server, port=0, user=None, password=None, keepalive=0,
                 ssl=False, ssl_params={}):
        if port == 0:
            port = 8883 if ssl else 1883
        self.client_id = client_id
        self.sock = None
        self.server = server
        self.port = port
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.pid = 0
        self.cb = None
        self.user = user
        self.pswd = password
        self.keepalive = keepalive
        self.lw_topic = None
        self.lw_msg = None
        self.lw_qos = 0
        self.lw_retain = False
        self.payload = {}            #Payload de informacion enviada por la aplicacion 
        self.Sesion = False          #Estado de la sesion (true cuandose inicia la simulacion en la aplicacion)

    def _send_str(self, s):
        self.sock.write(struct.pack("!H", len(s)))
        self.sock.write(s)

    def _recv_len(self):
        n = 0
        sh = 0
        while 1:
            b = self.sock.read(1)[0]
            n |= (b & 0x7f) << sh
            if not b & 0x80:
                return n
            sh += 7

    def set_callback(self, f):
        self.cb = f

    def set_last_will(self, topic, msg, retain=False, qos=0):
        assert 0 <= qos <= 2
        assert topic
        self.lw_topic = topic
        self.lw_msg = msg
        self.lw_qos = qos
        self.lw_retain = retain

    def connect(self, clean_session=True):
        self.sock = socket.socket()
        addr = socket.getaddrinfo(self.server, self.port)[0][-1]
        self.sock.connect(addr)
        if self.ssl:
            import ussl
            self.sock = ussl.wrap_socket(self.sock, **self.ssl_params)
        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")

        sz = 10 + 2 + len(self.client_id)
        msg[6] = clean_session << 1
        if self.user is not None:
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0
        if self.keepalive:
            assert self.keepalive < 65536
            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF
        if self.lw_topic:
            sz += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
            msg[6] |= 0x4 | (self.lw_qos & 0x1) << 3 | (self.lw_qos & 0x2) << 3
            msg[6] |= self.lw_retain << 5

        i = 1
        while sz > 0x7f:
            premsg[i] = (sz & 0x7f) | 0x80
            sz >>= 7
            i += 1
        premsg[i] = sz

        self.sock.write(premsg, i + 2)
        self.sock.write(msg)
        #print(hex(len(msg)), hexlify(msg, ":"))
        self._send_str(self.client_id)
        if self.lw_topic:
            self._send_str(self.lw_topic)
            self._send_str(self.lw_msg)
        if self.user is not None:
            self._send_str(self.user)
            self._send_str(self.pswd)
        resp = self.sock.read(4)
        assert resp[0] == 0x20 and resp[1] == 0x02
        if resp[3] != 0:
            raise MQTTException(resp[3])
        return resp[2] & 1

    def disconnect(self):
        self.sock.write(b"\xe0\0")
        self.sock.close()

    def ping(self):
        self.sock.write(b"\xc0\0")

    def publish(self, topic, msg, retain=False, qos=0):
        pkt = bytearray(b"\x30\0\0\0")
        pkt[0] |= qos << 1 | retain
        sz = 2 + len(topic) + len(msg)
        if qos > 0:
            sz += 2
        assert sz < 2097152
        i = 1
        while sz > 0x7f:
            pkt[i] = (sz & 0x7f) | 0x80
            sz >>= 7
            i += 1
        pkt[i] = sz
        #print(hex(len(pkt)), hexlify(pkt, ":"))
        self.sock.write(pkt, i + 1)
        self._send_str(topic)
        if qos > 0:
            self.pid += 1
            pid = self.pid
            struct.pack_into("!H", pkt, 0, pid)
            self.sock.write(pkt, 2)
        self.sock.write(msg)
        if qos == 1:
            while 1:
                op = self.wait_msg()
                if op == 0x40:
                    sz = self.sock.read(1)
                    assert sz == b"\x02"
                    rcv_pid = self.sock.read(2)
                    rcv_pid = rcv_pid[0] << 8 | rcv_pid[1]
                    if pid == rcv_pid:
                        return
        elif qos == 2:
            assert 0

    def subscribe(self, topic, qos=0):
        assert self.cb is not None, "Subscribe callback is not set"
        pkt = bytearray(b"\x82\0\0\0")
        self.pid += 1
        struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, self.pid)
        #print(hex(len(pkt)), hexlify(pkt, ":"))
        self.sock.write(pkt)
        self._send_str(topic)
        self.sock.write(qos.to_bytes(1, "little"))
        while 1:
            op = self.wait_msg()
            if op == 0x90:
                resp = self.sock.read(4)
                #print(resp)
                assert resp[1] == pkt[2] and resp[2] == pkt[3]
                if resp[3] == 0x80:
                    raise MQTTException(resp[3])
                return

    # Wait for a single incoming MQTT message and process it. Subscribed messages are delivered to a callback previously set by .set_callback() method. Other (internal) MQTT messages processed internally.
    def wait_msg(self):
        res = self.sock.read(1)
        self.sock.setblocking(True)
        if res is None:
            return None
        if res == b"":
            raise OSError(-1)
        if res == b"\xd0":  # PINGRESP
            sz = self.sock.read(1)[0]
            assert sz == 0
            return None
        op = res[0]
        if op & 0xf0 != 0x30:
            return op
        sz = self._recv_len()
        topic_len = self.sock.read(2)
        topic_len = (topic_len[0] << 8) | topic_len[1]
        topic = self.sock.read(topic_len)
        sz -= topic_len + 2
        if op & 6:
            pid = self.sock.read(2)
            pid = pid[0] << 8 | pid[1]
            sz -= 2
        msg = self.sock.read(sz)
        if (topic == b'AgentesSwarm'):                    #Comandos enviados por la aplicacion los procesamos internamente
            self.Comunicacion_Canal_General(msg.decode('utf-8')) 
        else:                                             #Resto de comunicacion (datos) se envian al controlador del usuario
            self.payload = loads(msg.decode('utf-8'))     #Obtenemos la data enviada por el topico
            self.cb(topic, msg)
        if op & 6 == 2:
            pkt = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", pkt, 2, pid)
            self.sock.write(pkt)
        elif op & 6 == 4:
            assert 0

    # Checks whether a pending message from server is available. If not, returns immediately with None. Otherwise, does the same processing as wait_msg.
    def check_msg(self):
        self.sock.setblocking(False)
        return self.wait_msg()

    #Por medio de esta funcion se procesan los comandos enviados al canal general -> AgentesSwarm
    def Comunicacion_Canal_General(self, mensaje):
        global diseño_red 
        global topicos_subscrito

        if(mensaje == "Com.App"):            #El proximo mensaje es el diseño de la red
            diseño_red = True
        elif(mensaje == "ArchivoServidor"):  #Ya esta disponible el controlador en el servidor   
            Request_Archivo_Servidor()
        elif(mensaje == "Iniciar"):          #Inicio un ciclo de la simulacion iniciamos la sesion 
            self.Sesion = True    
        elif(mensaje == "Terminar"):         #Termino un ciclo de la simulacion terminamos la sesion
            self.Sesion = False
        elif(mensaje == "Cerrar"):           #Ya se cerro la aplicacion,  regresamos el  micro a su archivos/configuracion inicial
            self.Cerrar_sesion()
        else:                                         
            if(diseño_red):                  #Informacion, configuracion de red  
                diseño_red = False 
                topicos_subscrito = "AgentesSwarm"
                config_red = loads(mensaje)   
                #Verificamos en cada topico si aparece nuestro ID, si si nos tenemos que subscribir a dicho topico luego
                for topico in config_red:    
                    if (client_id in config_red[topico]):
                        topicos_subscrito += "," + topico       #Agregamos cada topico en el que aparecemos 
                f = open("swarmdb", "r+b")                      #Abrimos el archivo
                db = btree.open(f)                              #Abrimos la base de datos
                db[b"topSubs"] = str.encode(topicos_subscrito)  #Guardamos los topicos en la base de datos 
                db.close()                                      #!!IMPORTANTE -> Cerramos base de datos  
                f.close()                                       #!!IMPORTANTE -> Cerramos el archivo
                print(topicos_subscrito.split(","))

    def Cerrar_sesion(self):
            f = open("swarmdb", "r+b")                 #Abrimos el archivo
            db = btree.open(f)                         #Abrimos la base de datos
            db[b"topSubs"] = b"AgentesSwarm"           #Configuracion inicial de topicos
            db.close()                                 #!!IMPORTANTE -> Cerramos base de datos  
            f.close()                                  #!!IMPORTANTE -> Cerramos el archivo
            if(copia_main_existe()):                   #Reestablecemos los archivos en caso sea necesario
                self.Sesion = False                    #TErminamos la sesion  en el controlador
                os.remove('main.py')
                os.rename('Swarm.py','main.py')
            machine.reset()           