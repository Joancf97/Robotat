# -*- coding: utf-8 -*-
"""
Created on Mon Jun 22 17:14:23 2020

@author: jose Andres Castaneda Forno
"""
###################################################### Librerias importadas #####################################################
import tkinter as tk            
from tkinter import ttk         #Mejos estilo visual de los objetos
from PIL import ImageTk,Image   #Trabajar las imagenes
import os                       #Manejo de archivos del sistema -> Carga de archivos al servidor
import shutil
from tkinter import filedialog
import threading                #Poder implemetar multithreading en la aplicacion  
import cv2                      #Procesamiento de video
import paho.mqtt.client as mqtt #Comunicacion con los agentes
import time
import json                     #Envio de paquetes como objeto
import numpy as np              #Analiss del rendimiento del sistema
from timeit import default_timer as timer
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  #Barra de navegaicon en las graficas
from matplotlib.figure import  Figure 



########################################################### Variables ###########################################################
#Estilos de letra
LARGE_FONT  = ("Verdana", 12)  
NORM_FONT   = ("Verdana", 10)
SAMALL_FONT = ("Verdana", 8)

#Configuracion de datos a guardar durante la simulacion 
SaveData   = False       #Guardamos el historial de datos
SaveGraphs = False       #Generamos las graficas de cada agente de forma individual

#Configuracion para crear la red de comunicacion 
topicoGlobal     = False #Crear un topico general de comunicacion con todos los agentes (Todos tienen la informacion  de todos)
TopicoIndividual = False #Crear un topico individual de comunicacion con los agentes (informacion individual  a cada agente)

'''
Diccionario con la informacion de todos los agentes activos del sistema, dentro de este diccionario se ingresara un 
array por cada agente reportado a la aplicacion, dentro del  cual se encuentra la informacion (objeto) de cada agene 
ver funcion -> nuevoAgente()
'''
#Informacion de los agentes del sistema
DataAgentes = {}    
#Clase con la estructura de la informacion de cada agente   
class Agente():       
    def __init__(self):
        self.X = 0
        self.Y = 0
        self.Angulo = 0
        self.ID = 0
        
#Controladores disponibles 
controladoresDisponibles = []               #Listado para guardar el nombre de los controladores disponibles
dirr = 'recursos/Controladores'             #Direccion de la carpeta donde se encuentran los controladores
dirServer = 'C:/wamp64/www/Bootloader'      #Direccion de la carpeta del servidor (A la cual se realizaran la peticion los agentes)
   
#Almacenamos las coordenadas de las esquinas de la mesa para realizar el analisis de OpenCV
Esquinas = []

#cliente servidor MQTT
client           = ''                 #Cliente para realizar la conexion a MQTT
broker           = "192.168.1.9"      #Direccion del servidor (Local)
topicoGeneral    = "AgentesSwarm"     #Topico general por el cual la aplicacion envia COMANDOS a los agentes
topicoAsistencia = "AgentesReporteID" #Topico al cual los agentes reportaran su ID al cocnectarce a la aplicacion
idAgentesConectados       = []        #Se almacena el ID de todos los agentes conectados a la red                                                  id = [id1,id2..]
topicosGenerales          = []        #Se almacenan todos los topicos creados en la red                                                             t = [tp1,tp2..]    
dataAgentesATopico        = {}        #Se define que informacion de que agentes seenviara en cada topico                                            d[topico] = [agente3,agente2..]
agentesSubscritosEnTopico = {}        #Se almacena que agentes se encuentran subscritos a cada topico (Verificar que la red se creo correctamente)  x[topico] = [agent1, agente2..]
topicosCreadosPorAgentes  = {}        #Para verificar que los agentes se subscribieron correctamente a los topicos indicatos                       y[topico] = [agent1, agente2..]
topicosIguales            = True      #Banderas para validar que todos los topicos se hayan creado exitosamente por parte de los agentes        
idsPorTopicoIguales       = True      #Bandera para validar si cada topico tiene a los agentes indicados subscritos a dicho topico
redCreadaExitosamente     = True      #Bandera para validar que la red de comunicacion se creo exitosamente

#Datos de la conexion de red (La cual se envia a los agentes)
ssid     = 'CLARO1_1B478E'
password = '387O5hxabM'

#Control de thread implementadas en la app
threads                = []       #Listado de las funciones que se trabajaran como threads -> Ingresar las funciones en inicioThreads()
threadsIniciadas       = []       #Listado de las threads ya iniciadas de las funciones definidas
banInalizarSimulacion  = True     #Bandera para iniciar y terminar el proceso en cada una de las threads
threadsIniciadas       = False    #Bandera para indicar si la comunicacion ya fue iniciada en algun momento en el uso de la aplicacion

#Evaluar el rendimiento del sistema
datosEnviadosEnPrueba     = {}      #Diccionario para almacenar la cantidad de datos enviados por cada thread en en el tiempo definido
tiempoDePrueba            = 6       #Tiempo en  el cual se evaluara el rendimiento del sistema
evaluandoRendimiento      = False   #Bandera para indicar cuando se esta evaluando el sistema 
tiempoInicioThread        = 0       #Tiempo en el que se inica a evaluar el rendimiento en el envio de datos
segundoActual             = 0                   

############################################################ Funciones auxiliares ###############################################
#Funcion para mostrar un mensaje de alerta que recive como parametro en la pantalla 
def pupopmsg(msg):
    popup = tk.Tk()                                                
    popup.wm_title("Mensaje")
    label = ttk.Label(popup, text = msg, font=NORM_FONT)         
    label.pack(side="top", fill="x", pady=10, padx=10)
    B1 = ttk.Button(popup, text="Ok", command = popup.destroy)
    B1.pack()
    popup.mainloop()

'''
Llamada en: Evento on_closing de la ventana principal
Esta funcion se encarga de cerrar la sesion actual de aplicaicion y terminar las threads (en caso se esten ejecutando).
Notifica a los agentes que la sesion ha temrinado para que estos reguresen a su configuracion inicial para la  siguiente simulacion
'''
def on_closing():
    global client
    global topicosGenerales
    
    client.publish(topicoGeneral, "Cerrar")          #Notificamos a los agentes fin de sesion
    if(banInalizarSimulacion and threadsIniciadas):  #En caso existan threads en ejecucion las terminamos
        finalizarSimulacion()
    client.disconnect()                            #Terminamos la cocmunicacion y nos desconectamos del servidor 
    client.loop_stop()                             
    app.destroy()
    
'''
Funcion para conectarnos al servidor MQTT, subscribirnos al topicos donde los agentes se reportaran al conectarce al 
la aplicacion e inicial el loop de comunicacion. Aqui se define el  callback del cliente al  momento en que llegue 
un mensaje a los topicos a los que la apliaccion  esta subscrita.
-> calback: En base al topico del  mensaje se ejecutan diferentes funciones
            - Registrar a los agenes en la aplicacion .
            - Verificar si la red de comunicacion  fue creada de forma  exitosa por los agentes.
'''
def conexionMosquitto():
    global client, broker
    
    def on_message(client, userdata, msg):
        if(msg.topic == topicoAsistencia):             #Un agente se esta repostando 
            nuevoAgente(msg.payload.decode('utf-8'))   #Enviamos el ID de dicho agente para la configuracion inicial
        else:      
            #Publicacion del ID de un agente en la red creada (Verificamos que la red se cree correctamente)  
            reporteDeTopicosCreados(msg)

    #Creamos una instancia de un cliente de mqtt con el nombre deseado, realizamos las subscripciones e iniciamos loop comunicacion
    client = mqtt.Client("Aplicacion")  
    client.connect(broker) 
    client.subscribe(topicoAsistencia) 
    client.on_message = on_message
    client.loop_start()
    return   

'''
Funcion para instanciar un objeto de la clase Agente() cuando un agente se report a la aplicacion. En este objeto unico 
(identiificado por si ID) se almacenaran los valores de la pose de dicho agente durante la simulacion. Cada instancia es 
almacenada dentro del diccionario DataAgentes para llevar registro de todos los agentes reportados
'''
def nuevoAgente(agente_id):
    global idAgentesConectados
    global DataAgentes
        
    print("Agente : " + agente_id + " reportado")
    if(not agente_id in idAgentesConectados):   #Verificamos que el agente no se haya reportado ya antes
        idAgentesConectados.append(agente_id)   #Almacenamos el identificador del agente
        agente = Agente()                       #Instanciamos un nuevo objeto para este agente
        agente.ID = agente_id
        agente.X = 60
        agente.Y = 40
        agente.Angulo = 20
        DataAgentes[agente_id] = agente         #Almacenamos el nuevo objeto en el  diccionario
        

'''
Funcion para verificar que la red disenada por el usuario se creo correctamente. Los agentes reportaran su ID en los topicos
respectivos (Segun el diseno de red del usuario), por medio  de esta funcion se verifica que todos los agentes esten subscritos 
a sus respectivos topicos.
'''
def reporteDeTopicosCreados(msg):
    global topicosIguales, idsPorTopicoIguales                                 #Bandera para verificar creacion exitosa de la red
    global topicosGenerales                                                    #Todos los topicos disenados por el usuario
    global agentesSubscritosEnTopico                                           #Los agentes que estan subscritos a cada topico 

    topicosIguales      = True                                                 #Condicion inicial para validar la correcta creacion de la red                                     
    idsPorTopicoIguales = True
    
    #Datos de la  publicacion
    topico    = msg.topic                                                      
    id_agente = msg.payload.decode('utf-8')
    if(topico in topicosCreadosPorAgentes):                                    #topico ya existe, adjuntamos agente al topico
        topicosCreadosPorAgentes[topico].append(id_agente)                     
    else:                                                                      #topico no existe, creamos topico e ingresamos agente
        topicosCreadosPorAgentes[topico] = [id_agente]
    
    #Verificamos si ya estan creados todos los topicos disenados por el usuario 
    for topico in topicosGenerales: 
        if ((not topico in topicosCreadosPorAgentes) or (len(topicosCreadosPorAgentes)) != len(topicosGenerales)):
            topicosIguales = False                                             #Topicos Creados OK
    
    #Si todos los topicos estan creados, validamos que todos los agentes se encuenten subscritos a los topicos indicados
    if(topicosIguales):
        for topico in agentesSubscritosEnTopico:                               #Recorremos todos los arrays de los topicos creados Ej: A[topico] = [Id1, Id3, Id5..]
            for agente_en_topico in agentesSubscritosEnTopico[topico]: 
                #Verificamos que todos los agentes que estan  subscritos a ese topico seanlos mismos que el usuario definio al disenar la red
                if(not agente_en_topico in topicosCreadosPorAgentes[topico]):  
                    idsPorTopicoIguales = False                                #Agentes subscritos a topicos OK
                    
    #La red se creo exitosamente cuando todos los topicos esten creados y todos los agentes esten subscritos a sus respectivos topicos
    redCreadaExitosamente = topicosIguales and idsPorTopicoIguales
    if(redCreadaExitosamente):
        pupopmsg("Controlador Cargado Con Exito A Los Agentes! \n\n Red De Comunicación Creada Exitosamente!")
    
    
#Obtenemos el nombre de todos los controladores almacenados en la carpeta de controladores
def buscarcontroladoresDisponibles():
    for c in os.listdir(dirr):
        controladoresDisponibles.append(c)
        
#Funcion para mostrar en el menu principal 
def controladoresMenu(menu):
    global controladoresDisponibles
    #Recorremos el arreglo de controladores disponibles y los mostramos en  el menu
    for controlador in controladoresDisponibles:
        menu.add_command(label=controlador, command=lambda: cargarControladorAlServidor(controlador)) 

#Funcion para que el usuario seleccione un nuevo controlados y este se pueda agregar a la carpeta de controladores
def cargarNuevoControlador(): 
    global dirr 
       
    tk.filename = filedialog.askopenfilename(initialdir="C:/Users/", title="Selecciona un controlador")  #Mostramos el explorador de windows   
    try:
        shutil.copy(tk.filename,dirr)        #Realizamos una copia del archivo seleccionado, dentro de la carpeta de controladores disponibles
        pupopmsg("Controlador guardado con exito")
    except:
        pupopmsg("No se selecciono ningun controlador")
    buscarcontroladoresDisponibles()     #Actualizamos los controladores mostrados en el menu


'''
Llamada:   Al seleccionar un controlador desde la aplicacion
Parametro: Nombre del controlador selecciondo 
Funcion para cargar el controlador seleccionado al servidor WAMP y enviar comando a los agentes para que descarguen dicho archivo
'''
def cargarControladorAlServidor(control):
    global dirr, dirServer 
    global client
    global topicosGenerales
    
    #Cargamos nuevo controlador al servidor
    if(os.listdir(dirServer) != []):                                #Verificamos si la carpeta Bootloader del servidor esta vacia
        os.remove(dirServer+"/MainServidor.py")                     #Si ya existe un controlador cargado lo eliminamos 
    shutil.copy(dirr+'/'+control,dirServer)                         #Realizamos una copia del archivo del controlador seleccionado en el servidor  
    os.rename(dirServer+'/'+control, dirServer+"/MainServidor.py")  #Le cambiamos el nombre para que los microcontroladores puedan encontrar el archivo
    #Nos subscribimos a todos los topicos creados para verificar la creacion correcta de la red
    for topico in topicosGenerales:
        print('Subscrito topico:' + topico)
        client.subscribe(topico)
    
    #Enviamos comando a los agentes que descarguen el nuevo controlador del servidor
    client.publish(topicoGeneral, "ArchivoServidor") 
    pupopmsg("Controlador Cargado con exito al servidor")

#Cargar el archivo del algoritmo  swarm 
def CargarAlgoritmoSwarm():    
    #Mostramos el explorador de windows para que el usuario seleccione un algoritmo nuevo
    tk.filename = filedialog.askopenfilename(initialdir="C:/Users/", title="Selecciona el algoritmo swarm")

#Funcion para calibrar los limites de trabajo de la  mesa
def calibracionMesa():
    cap = cv2.VideoCapture(0)
    _,frame = cap.read()
    #Esquinas = cv2.selectROI(frame)

'''
Por medio de esta funcion se reinician a su estado inicial a los agentes. De esta forma los agentes se vuelven a notificar 
a la apliacion de forma automatica. y reiniciamos el  registro de agentes en  la aplicacion. Menu: 1. Conectar Agentes"
'''
def conectarAgentes():
    global DataAgentes
    global idAgentesConectados
    
    DataAgentes = {}                        #Reiniciamos registros de los agentes
    idAgentesConectados = []
    client.publish(topicoGeneral, "Cerrar") #Enviamos comandos


'''
Funcion para crear e iniciar las threads de comunicacion, una por cada topico creado en  la red,
 los parametros enviados son  el nombre del topico y el ID de los agentes de los cuales se enviara la informacion por el topico
'''
def Comunicacion():  
    global threadsIniciadas
    global dataAgentesATopico
    global topicosGenerales
    
    for topico in topicosGenerales:      
        t = threading.Thread(target=threadComunicacionTopico, args=[topico, dataAgentesATopico[topico]])  #Inicializamos una thread para cada topico 
        t.start()                                                                                         #Iniciamos la thread para que inicie a trabajar 
        threadsIniciadas.append(t)                                                                        #Agragamos dicha thread a la lista de threads inicializadas 

'''
Por cada uno de los topiicos creados se crea una nueva thread, por medio de la cual la  aplicacion se estara comunicando 
con los agentes, esta funcion es "creada" n cantidad de veces (n = numero de topicos en la red) y recibe como  parametro 
el nombre del topico al  cual tiene que  publicar la informacion y la informacion  que debe publicar en dicho topico.
-> Cada thread se ejecuta mientras la simulacion este activa, si el usuario termina la simulacion las threads terminan.
Los datos enviados se actualian por medio del analisis de vision de computadora
'''
def  threadComunicacionTopico(topico, Data_envio):
    global banInalizarSimulacion 
    global client
    global DataAgentes
    global evaluandoRendimiento, tiempoInicioThread
    global datosEnviadosEnPrueba

    if(evaluandoRendimiento):                            #Si evaluamos el rendimiento del sistema inicializamos las 
        cont = 0                                         #variables para realizar el analisis de datos
        datosEnviadosEnPrueba[topico] = {}
    
    while banInalizarSimulacion:                         #Mientras la simulacion este activa, enviamos datos 
        payload = []                                     #Paquete completo  de datos a enviar
        for agente in Data_envio: 
            data = {"X":0, "Y":0, "Angulo":0, "ID":0}
            data["ID"] = DataAgentes[agente].ID
            data["X"] = DataAgentes[agente].X
            data["Y"] = DataAgentes[agente].Y
            data["Angulo"] = DataAgentes[agente].Angulo
            payload.append(data)                        #Se adjunta la informacion de todos los agentes a enviar por el topico 
        
        if(evaluandoRendimiento):
            cont += 1                                               #Incrementamos la cantidad de datos enviados en este segundo   
            segundo = int(timer() - tiempoInicioThread)             #Segundo actual
            if (segundo in np.arange(tiempoDePrueba)):              #Cada segundo guardamos los datos y reiniciamos el contador
                if(len(datosEnviadosEnPrueba[topico]) <= segundo):
                    datosEnviadosEnPrueba[topico][segundo] = cont   
                    cont = 0
            else:
                evaluandoRendimiento = False                        #Cuando el  tiempo de prueba esta cumplido dejamos de ejecutar las threads
        else:
            client.publish(topico, json.dumps(payload)) #Realizamos La publicacion de la informacion como un bjeto json en el topico
        time.sleep(0.087987)
    return    
 

#Funciones adicionales a ejecutar de form organizada con la thread de comunicacion *Todavia no  estan organizadas*
def function():    
    while banInalizarSimulacion:
        print("..")
    return
        
def function2():
    while banInalizarSimulacion:
        print("..")
    return
        
def function3():
    while banInalizarSimulacion:
        print("..")
    return

'''
Cuando el usuario inicia la simulacion desde la aplicaicon, por medio de esta funcion se inicial las threads de trabajo, 
las cuales se estaran ejecutando de forma paralela, pero oorganizada con las threads de comunicacion
'''  
def inicioThreads():
    global threads, threadsIniciadas, banInalizarSimulacion 
    global topicoGeneral
    global threadsIniciadas
    
    threadsIniciadas     = True               #Se ha iniciado un proceso de comunicacion
    banInalizarSimulacion  = True               #Bandera para terminar las threadas
    threads = []                              #Inicializamos las varibles de registro 
    threadsIniciadas = []
    
    #Nos desubscribimos a los topicos luego de haber verificado que  la red se creo correctamente
    for topico in topicosGenerales:
        client.unsubscribe(topico)
    
    if(not evaluandoRendimiento):                  #Mandamos comando para que los agentes inicien la sesion, unicamente si -
        client.publish(topicoGeneral , "Iniciar")  #no estamos evaluando el rendimiento del sistema
        
    #Ingresar aqui el nombre de las funciones a trabajar, por cada funcion se empelara una thread diferente                     
    threads = [] #[function,function2,function3]                 
    for thread in threads:                                  
        t = threading.Thread(target=thread)   #Inicializamos una thread para cada funcion 
        t.setDaemon(True)
        t.start()                             #Iniciamos la thread para que inicie a trabajar 
        threadsIniciadas.append(t)            #Agragamos dicha thread a la lista de threads inicializadas 
    Comunicacion()                            #Iniciamos threas para comunicacion con los topicos de forma individual

'''   
Cuando el usuario finaliza la  simulacion, se terminan todas las treads en ejecucion y se notifica a los agentes que
la simulacion ya termino, Idealmente esta funcion tiene que ser ejecutada antes de cerrar para dejar de ejecutar las threads. 
'''
def finalizarSimulacion():
    global banInalizarSimulacion
    global threadsIniciadas
    global evaluandoRendimiento
    
    banInalizarSimulacion = False               #Bandera para terminar las threadas
    client.publish(topicoGeneral , "Terminar")
    for t in threadsIniciadas:    
        t.join()                           #Terminamos las threads 
    pupopmsg("Procesos terminados correctamente ")  
        
    


#Enviamos la configuracion de red definida por el usuario a de los agentes
def modificacionDeConexionWifi():
    modRed = tk.Toplevel()          
    modRed.geometry("300x120")      
    modRed.title("Configuracion de red")
    modRed.n = tk.StringVar()            #Variables para cada entrada de texto
    modRed.p = tk.StringVar()

    ttk.Label( modRed, text="SSID: ").grid(row=0, column=0,  padx=10, pady=10)   
    ttk.Label( modRed, text="Password: ").grid(row=0, column=1, pady=10)  
    ttk.Entry(modRed, textvariable=modRed.n).grid(row=1, column=0, padx=10)
    ttk.Entry(modRed, textvariable=modRed.p).grid(row=1, column=1)
    ttk.Button(modRed, text="Save", command = lambda: (verificacionDeDatosRed())).grid(row=2, sticky=tk.S, pady=20, padx=15, columnspan=2)  #cerramos la ventana
    modRed.columnconfigure(1, weight=1) 
    
    #Funcion para verificar si el usuario modifico los parametros de red para la siguiente conexion 
    def verificacionDeDatosRed():
        global ssid                          #Referenciamos uso a las variables globales de
        global password
        
        ssid = modRed.n.get()                #Obtenemos los datos de la nueva red ingresado por el usuario
        password = modRed.p.get()
        if(ssid != '' and  password != ''):  #Validamos el ingreso de datos
            modRed.destroy()
            pupopmsg("Datos Guardados con  exito")
        else:
            pupopmsg("Datos ingresado Incorrectamente")

'''
Esta funcion permite evaluar el rendimiento del sistema en cuanto a la cantidad de paquetes de informacion enviados por cada thread
(canal) de comunicacion
'''
def evaluarRendimientoRed():
    global evaluandoRendimiento
    global tiempoInicioThread
    global banInalizarSimulacion
    
    
    tiempoInicioThread = timer()    #Iniciamos el tiempo de evaluacion 
    evaluandoRendimiento = True     #Activamos el  modo  de evaluacion de rendimiento
    inicioThreads()
    while evaluandoRendimiento:     #cuando el tiempo se cumpla, las threads cambiaran el estado de la bandera evaluandoRendimiento a false
        pass
    mostrarRendimientoEnvioDatos()  #Procedemos a cerrar las threads 
    finalizarSimulacion()           #Mostramos la ventana de resultados al usuario
    

        
        


############################################################### Ventana Principal ################################################### 
#Ventana principal de la apliaccion, aqui se muestran las dos imagenes principales, al igual que el menu principal. 
class swarmRobotics(tk.Tk):
    global DataAgentes
    
    def __init__(self, *args, **kargs):
        tk.Tk.__init__(self, *args, *kargs)
        tk.Tk.iconbitmap(self, default="recursos/Imagenes/logoUVG.ico")     
        tk.Tk.wm_title(self,"UVG - ROBOTARIUM")
         
        #Creamos el menu principal
        menubar = tk.Menu(self)   #Objeto menu
        #Robotarium 
        Robotarium = tk.Menu(menubar, tearoff = 0) 
        Robotarium.add_command(label="1. Conectar Agentes", command= lambda: conectarAgentes())                              #Cnectamos a los agentes a la aplicacion
        Robotarium.add_command(label = "2. Calibrar Mesa", command=lambda: imagenProcesadaCombobox())                        #Abrimos ventana par calibrar la mesa               
        Robotarium.add_command(label = "3. Guardar información", command=lambda: confGuardarDatos())                         #Configurar que datos se desean guardar durante la simulacion
        Robotarium.add_command(label = "4. Configuración de red de conexión", command=lambda: configurarRedDeComunicacion()) #Configurar la red de comunicacion
        Robotarium.add_separator() 
        Controldores = tk.Menu(Robotarium, tearoff = 0)
        Controldores.add_command(label="Cargar Nuevo..", command=lambda: cargarNuevoControlador())           
        controladoresMenu(Controldores)                                                                                      #Creamos una opcion por cada controlador
        Robotarium.add_cascade(label="5. Cargar Controlador", menu=Controldores)                                             #Mostramos los controladores disponibles en  el menu
        Robotarium.add_command(label = "6. Iniciar simulacion",  command= lambda: inicioThreads())                                  #Iniciamos la simulacion,  inicia comunicacion y threads de procesamiento de datos                                 
        Robotarium.add_command(label="7. Tabla de datos",  command=lambda: tablaDeDatos())                                   #Mostramos la tadla de datos de los agentes
        Robotarium.add_command(label="8. Finalizar simulacion",  command=lambda: finalizarSimulacion())                      #Terminamos la simulacion, finaliza comunicacion y threads de procesamiento de datos 
        menubar.add_cascade(label="Robotat", menu=Robotarium)                                              
                
        #Cargar archivo
        LoadFile = tk.Menu(menubar, tearoff = 0)
        LoadFile.add_command(label="Cargar Algoritmo Swarm", command= lambda: CargarAlgoritmoSwarm())                        #Cargamos el algoritmoswarm  a la aplicacion
        menubar.add_cascade(label="Cargar Archivo", menu=LoadFile)
        
        #Configuraciones Extras
        Configuracion = tk.Menu(menubar, tearoff = 0)
        Configuracion.add_command(label = "Diseñar red comunicación",  command= lambda: disenarRedDeComunicacion())          #Disenamos una red mas compleja que la propuesta (Default)
        Configuracion.add_command(label="Restablecer Swarmdb", command= lambda: print('No disponible..'))              
        Configuracion.add_command(label="Configuracion Wifi agentes", command= lambda: modificacionDeConexionWifi())
        Configuracion.add_command(label="Configuracion De Camara", command= lambda: print('No disponible..'))  
        Configuracion.add_command(label="Evaluar Rendimiento de la red", command= lambda: evaluarRendimientoRed())
        menubar.add_cascade(label="Configuracion", menu=Configuracion)
        #Creamos el menu
        tk.Tk.config(self, menu = menubar)        
        
        #-----------------Imagen principal tomada de la camara de la plataforma--------------
        ttk.Label(self, font=LARGE_FONT, anchor="center", text="Imagen Natural").grid(row=0, column=0)
        panel = None
        panel = tk.Label()
        panel.grid(row=1, column=0, padx=20, pady=10)
        
        camara = cv2.VideoCapture(0)
        _,frame = camara.read()
        frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        frame = Image.fromarray(frame)
        frame = ImageTk.PhotoImage(frame)
        panel.configure(image=frame)
        panel.image=frame
        
        #-------------------------Segunda imagen -> Imagen procesada---------------------------
        ttk.Label(self, font=LARGE_FONT, anchor="center", text="Imagen Procesada").grid(row=0, column=1)
        panel2 = None
        panel2 = tk.Label()
        panel2.grid(row=1, column=1, padx=20, pady=10, columnspan=2)
        panel2.configure(image=frame)
        panel2.image=frame  
        
         #Funcion para mostrar en el bombox todos los agentes que se pueden enfocar como imagen procesada
        def imagenProcesadaCombobox():
            agentes = []                                 #Array para guardar el ID de cada agente
            for agente in DataAgentes: 
                print(agente)
                agentes.append("ID - " + str(DataAgentes[agente].ID)) #Obtenemos el ID de todos los agentes reportados para mostrarlo
            Grafica_actual = ttk.Combobox(self, values=agentes)
            Grafica_actual.grid(row=0, column=2)
            calibracionMesa()
        


############################################################### Ventanas auxiliares ################################################### 
'''
Ventana auxiliar para configurar la red de comunicacion de los agentes, por este medio se crean los topicos y la informacion que se tiene que
enviar por cada uno de los topicos disenados por el  usuario.
'''
def disenarRedDeComunicacion(): 
    global client, topicoGeneral      #Conexion MQTT al canal general
    global topicosGenerales           #Registro de topicos creados por el usuario                           
    global agentesSubscritosEnTopico  #Listado de agentes subscritos por topico                                          
    global dataAgentesATopico         #Listado de informacion a mandar la informacion por cada topico
    
    CnfRed = tk.Toplevel()              
    CnfRed.geometry("1000x300")           
    CnfRed.title("Diseño de la red de comunicación")      
    ttk.Button(CnfRed, text="Nuevo Grupo", command= lambda: creacionDeNuevoTopico()).grid(column=0, row=0, sticky=tk.S, pady=10, padx=15)                #Funcion para crear un nuevo topico en la red
    ttk.Button(CnfRed, text="Actualizar lista", command=lambda: actualizarTablaTopicos()).grid(column=1, row=0, sticky=tk.S, pady=10, padx=15)           #Actualizamos los valores de la tabla de topicos creados
    ttk.Button(CnfRed, text="Publicar Diseño", command= lambda: publicarDiseño()).grid(column=2, row=0, sticky=tk.S, pady=10, padx=15)                   #Publicamos el diseno en  el topico general para que los agentes creen la red
    
    ttk.Label( CnfRed, width=19,font=LARGE_FONT, anchor="center", text="Nombre del grupo", background="white").grid(column=0, row=1) 
    ttk.Label( CnfRed, width=40,font=LARGE_FONT, anchor="center",  text="Agentes subscritos en el  grupo", background="white").grid(column=1, row=1) 
    ttk.Label( CnfRed, width=40,font=LARGE_FONT, anchor="center",  text="Información disponible por el grupo", background="white").grid(column=2, row=1) 
    CnfRed.columnconfigure(1, weight=1) 
    
    #Se actualiza la tabla visual de topicos, mostrando los topicos creados hasta el mosmento
    def actualizarTablaTopicos():
        i = 1
        for topico in topicosGenerales:
            i += 1
            ttk.Label( CnfRed, width=15,font=NORM_FONT, anchor="center", text=topico).grid(column=0, row=i) 
            ttk.Label( CnfRed, width=40,font=NORM_FONT, anchor="center", text=agentesSubscritosEnTopico[topico]).grid(column=1, row=i) 
            ttk.Label( CnfRed, width=40,font=NORM_FONT, anchor="center", text=dataAgentesATopico[topico]).grid(column=2, row=i) 
            
    #Se envia el comando para que los agentes verifique a que topicos se deben subscribit
    def publicarDiseño():
        client.publish(topicoGeneral, "Com.App")                               #Comando indicando  que el siguente paquete sera la configuracion de los topicos 
        client.publish(topicoGeneral, json.dumps(agentesSubscritosEnTopico))   #Enviamos la cocnfiguracion de topicos disenada 
        CnfRed.destroy()
        
        
'''
Ventana para crear un nuevo topico en la red de comunicacion, indicando el nombre del tipoco los agentes que estaran subscritos a esta 
y los datos de los agentes que se enviaran por dicho topico, se valida que la informacion ingresada sea vali
'''      
def creacionDeNuevoTopico():     
    global idAgentesConectados         #Listado de ID's de los agentes conectados
    global topicosGenerales            #Todos los topicos creados                           
    global agentesSubscritosEnTopico   #Listado de agentes subscritos por topico                                          
    global dataAgentesATopico          #Listado de agentes a mandar la informacion por topico
    
    CrearTopico = tk.Toplevel()         
    CrearTopico.geometry("490x180")
    CrearTopico.title("Nuevo Topico")    
    CrearTopico.topico = tk.StringVar() #Variables ingresadas por el usuario 
    CrearTopico.subscritos = tk.StringVar()
    CrearTopico.data = tk.StringVar()
    
    #Componentes de la vista
    ttk.Label( CrearTopico, width=25,font=LARGE_FONT,  text="Nombre del Grupo (Topico): ").grid(column=0, row=0, pady=5, padx=10) 
    ttk.Label( CrearTopico, width=70,font=SAMALL_FONT, text="**Ingrese los id's de los agentes separados por una coma y sin espacios**").grid(column=0, row=1, columnspan=2, pady=5, padx=10) 
    ttk.Label( CrearTopico, width=25,font=LARGE_FONT,  text="Agentes subscritos: ").grid(column=0, row=2, pady=5, padx=10) 
    ttk.Label( CrearTopico, width=25,font=LARGE_FONT,  text="Data a enviar por topico: ").grid(column=0, row=3, pady=5, padx=10) 
    ttk.Entry(CrearTopico, width=30, textvariable=CrearTopico.topico).grid(column=1, row=0, pady=5, padx=10) 
    ttk.Entry(CrearTopico, width=30, textvariable=CrearTopico.subscritos).grid(column=1, row=2, pady=5, padx=10) 
    ttk.Entry(CrearTopico, width=30, textvariable=CrearTopico.data).grid(column=1, row=3, pady=5, padx=10) 
    ttk.Button(CrearTopico, text="OK", command=lambda: validacionYRegistroDeTopico()).grid(column=0, row=4, columnspan=2, pady=15)       #Antes de crear el  topico se verifica que los datos sean validos
    CrearTopico.columnconfigure(1, weight=1) 
    
    #Se validan los datos del nuevo topico a crear y de ser correctos se creael topico y almacenan los datos
    def validacionYRegistroDeTopico():
        global idAgentesConectados        #Listado de ID's de los agentes conectados
        global topicosGenerales           #Topicos creados                           
        global agentesSubscritosEnTopico  #Listado de agentes subscritos por topico                                          
        global dataAgentesATopico         #Listado de agentes a mandar la informacion por topico
        
        nombre_topico = ""                #Nombre del topico que se  desea registrar 
        subs_topico   = []                #Id de los agentes que se desean subscribir al nuevo topico 
        data_topico   = []                #Id de los agentes de los que se enviara la informacion por el nuevo  topico
        topico_registrado = True
        if CrearTopico.topico.get().strip() and CrearTopico.subscritos.get().strip() and CrearTopico.data.get().strip():  #Verificamos si todos los datos estan ingresados
            nombre_topico = CrearTopico.topico.get()
            subs_topico   = CrearTopico.subscritos.get().split(",")
            data_topico   = CrearTopico.data.get().split(",")
            #Verificamos que el topico no exista ya
            if(nombre_topico in topicosGenerales):  
                topico_registrado = False
                pupopmsg("Topico ya existente")
            #Verificamos que los agentes ingresados en topico esten registrads en la aplicacion 
            for subcriptor in subs_topico:
                if(not subcriptor in idAgentesConectados):
                    topico_registrado = False
                    pupopmsg("El agente "+subcriptor+" no esta conectado - Subscriptores")
            for subcriptor in data_topico:
                if(not subcriptor in idAgentesConectados):
                    topico_registrado = False
                    pupopmsg("El agente "+subcriptor+" no esta conectado - Data")
        else:
            pupopmsg("Ingrese todo los datos")
        
        #Si todos los datos fueron ingresados correctamente, se crea el topico y se guarda la estructura de este en la aplicacion
        if(topico_registrado):
            #Guardamos la informacion solicitada por el usuario
            topicosGenerales.append(nombre_topico)                             #Se guarda registro del nuevo  topico
            agentesSubscritosEnTopico[nombre_topico] = subs_topico             #Se guarda registro de los agentes que se  tienen que subscribir a ese topico 
            dataAgentesATopico[nombre_topico]        = data_topico             #Se guarda registro de los agentes de los cuales se enviara la informacion en el topico
            CrearTopico.destroy()
            pupopmsg("Topico Creado Correctamente")

                         
'''
En esta ventana el usuario puede configurar que informacion desea guardar, dicha informacion sera generada en el momento que se termine la simulacion 
Se puede guardar el historial de datos de la simulacion y generar las graficas de pose de cada agente
''' 
def confGuardarDatos(): 
    global SaveData                 #Referenciamos uso a las variables globales
    global SaveGraphs
    
    CnfRun = tk.Toplevel()          
    CnfRun.geometry("210x130")      
    CnfRun.title("Guardar datos")      
    OP1 = tk.StringVar()            #Variables para cada Checkbutton
    OP2 = tk.StringVar()
    SaveData = OP1.get()            #Obtenemos el valor de cada Checkbutton
    SaveGraphs = OP2.get()

    OpSaveData = ttk.Checkbutton(CnfRun, text="Guardar Historial De Pose", variable= OP1)               #Checkbuttons
    OpGenerateGraphs = ttk.Checkbutton(CnfRun, text="Genear Gráficas De Posicion", variable= OP2)
    OpSaveData.grid(row=0, sticky=tk.W, pady=10, padx=15)                                               #Posicion the Checkbutton 
    OpGenerateGraphs.grid(row=1, sticky=tk.E, pady=10, padx=15)
    ttk.Button(CnfRun, text="Guardar", command=CnfRun.destroy).grid(row=2, sticky=tk.S, pady=10, padx=15)  #cerramos la ventana
    CnfRun.columnconfigure(1, weight=1) 


'''
En esta ventana el usuario puede seleccionar con que tipode configuracion de red desea trabajar, puede seleccionar entre:
        - Grupo General: La informacion de todos los agentes le llegan a todos los agentes.
        - Comunicacion individual: la informacion de cada agente unicamente le llega a cada agente.
        - Crear configuracion adicional: El usuario puede crear su propia configuracion de red mas compleja.
'''
def configurarRedDeComunicacion():
    global topicoGlobal
    global topicoIndividual
    
    cnfRedCom = tk.Toplevel()          #mostramos hasta arriva (z index)
    cnfRedCom.geometry("210x180")      #Geometria de la  pantalla
    cnfRedCom.title("Guardar datos")      
    OP1 = tk.StringVar()               #Variables para cada Checkbutton
    OP2 = tk.StringVar()
    topicoGlobal = OP1.get()          #Obtenemos el valor de cada Checkbutton
    topicoIndividual = OP2.get()

    OpSaveData = ttk.Checkbutton(cnfRedCom, text="Grupo General", variable= OP1)                        #Checkbuttons - Opciones
    OpGenerateGraphs = ttk.Checkbutton(cnfRedCom, text="Comunicacion individual", variable= OP2)
    OpSaveData.grid(row=0, sticky=tk.W, pady=10, padx=15)                                               
    OpGenerateGraphs.grid(row=1, sticky=tk.E, pady=10, padx=15)
    ttk.Button(cnfRedCom, text="Crear configuracion adicional", command= lambda:disenarRedDeComunicacion()).grid(row=2, sticky=tk.S, pady=10, padx=15)  #cerramos la ventana
    ttk.Button(cnfRedCom, text="Guardar", command=cnfRedCom.destroy).grid(row=3, sticky=tk.S, pady=10, padx=15)  #cerramos la ventana
    cnfRedCom.columnconfigure(1, weight=1) 

'''
Ventana donde  se muestra la tabla de datos donde se despliega la informacion de cada uno de los agentes de una forma mas amigable para el usuario
'''
class tablaDeDatos(tk.Tk):  
    global DataAgentes
    
    def __init__(self, *args, **kargs):
        tk.Tk.__init__(self, *args, *kargs)
        tk.Tk.iconbitmap(self, default="recursos/Imagenes/logoUVG.ico")  
        self.geometry("1365x90")                     
        self.title("Tabla de Datos")   
        
        #Mostramos los headers para  la tabla
        Headers = ['ID','Pos X','Pos Y','θ']          
        for i in range(4):                           
                ttk.Label(self, width=6, font=LARGE_FONT, anchor="center", text=Headers[i], background="black", foreground="white" ).grid(row=i+1, column=0, sticky=(tk.W + tk.S + tk.N + tk.E))  

        total_rows = len(DataAgentes)       #Cantidad de agentes a mostrar la  informacion (cantidad de agentes conectados)
        def Llenar_Tabla():                #Creamos los labesl para mostrar la informacion de cada uno de los agentes
            #Ingresamos los datos de los agentes al grid
            for i in range(total_rows):  
                e = ttk.Label(self,  width=11,font=SAMALL_FONT, anchor="center", text=DataAgentes[i].ID, background="white")
                e.grid(row=1, column=i+2, sticky=(tk.W + tk.S + tk.N + tk.E))
                e = ttk.Label(self, width=11,font=SAMALL_FONT, anchor="center", text=DataAgentes[i].X, background="white" )
                e.grid(row=2, column=i+2, sticky=(tk.W + tk.S + tk.N + tk.E)) 
                e = ttk.Label(self, width=11,font=SAMALL_FONT, anchor="center", text=DataAgentes[i].Y, background="white")
                e.grid(row=3, column=i+2, sticky=(tk.W + tk.S + tk.N + tk.E)) 
                e = ttk.Label(self, width=11,font=SAMALL_FONT, anchor="center", text=DataAgentes[i].Angulo, background="white" )
                e.grid(row=4, column=i+2, sticky=(tk.W + tk.S + tk.N + tk.E))   
        Llenar_Tabla()
'''      
Ventana para mostrar el rendimiento de del sistema enfocado en el envio de datos por cada topico configurado por el usuario.
'''
def mostrarRendimientoEnvioDatos():
    global datosEnviadosEnPrueba
    global evaluandoRendimiento
    
    rendEnvio = tk.Toplevel()           #mostramos hasta arriva (z index)
    rendEnvio.geometry("1350x600")      #Geometria de la  pantalla
    rendEnvio.title("Rendimiento del envio de datos")
    tk.Scrollbar(rendEnvio)
    
    ttk.Label(rendEnvio, width=20,font=LARGE_FONT,  text="Thread del topico", background="white", anchor="center").grid(column=0, row=0) 
    ttk.Label(rendEnvio, width=20,font=LARGE_FONT,  text="Historial", background="white", anchor="center").grid(column=1, row=0)  
    ttk.Label(rendEnvio, width=15,font=LARGE_FONT,  text="Envios/s Max", background="white", anchor="center").grid(column=2, row=0) 
    ttk.Label(rendEnvio, width=15,font=LARGE_FONT,  text="Envios/s Prom", background="white", anchor="center").grid(column=3, row=0)
    ttk.Label(rendEnvio, width=15,font=LARGE_FONT,  text="Envios/s Min", background="white", anchor="center").grid(column=4, row=0)  
    ttk.Label(rendEnvio, width=50,font=LARGE_FONT,  text="Gráfica", background="white", anchor="center").grid(column=5, row=0) 

    #Recorremos los datos obtenidos de la etapa de evaluacion del rendimiento para mostrarle los datos al usuario
    i = 0
    for topico in datosEnviadosEnPrueba:
        i += 1
        Datos = []
        ttk.Label(rendEnvio, width=20,font=LARGE_FONT, text=topico, anchor="center").grid(column=0, row=i, pady=5) 
        for dato in datosEnviadosEnPrueba[topico]:
                Datos.append(datosEnviadosEnPrueba[topico][dato])
        ttk.Label(rendEnvio, width=20,font=LARGE_FONT, text=Datos, anchor="center").grid(column=1, row=i, pady=5)
        ttk.Label(rendEnvio, width=15,font=LARGE_FONT, text=str(np.amax(Datos)), anchor="center").grid(column=2, row=i) 
        ttk.Label(rendEnvio, width=15,font=LARGE_FONT, text=str(int(np.average(Datos))), anchor="center").grid(column=3, row=i) 
        ttk.Label(rendEnvio, width=15,font=LARGE_FONT, text=str(np.amin(Datos)), anchor="center").grid(column=4, row=i)
        #Graficas para poder observar el comportamiento 
        fig = Figure(figsize=(5,1), dpi=100)
        t = np.arange(0, len(Datos), 1)
        fig.add_subplot(111).plot(t, Datos)
        canvas = FigureCanvasTkAgg(fig, master =rendEnvio)
        canvas.draw()
        canvas.get_tk_widget().grid(column=5, row=i, pady=1) 

        
    
    

            
#================================ SET UP ======================================
buscarcontroladoresDisponibles() #Obtener los controladores disponibles en la carpeta de controladores
conexionMosquitto()              #Conexión al servidor MQTT


#================================="LOOP"=======================================
if __name__ == "__main__":
    app = swarmRobotics()                        #Ventana principal
    app.geometry("1365x540") 
    app.protocol("WM_DELETE_WINDOW", on_closing) #Evento que se dispara al cerrar la ventana de la app 
    app.mainloop()                               #Iniciamos la sesion en  la aplicacion 