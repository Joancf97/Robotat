from machine import Pin
import time 
import json
from core import Robotat  

#Dictado que contendra la data de los agentes (diccionarios)
Agente = {}

#indicar que la flexibilidad de esta
def Actualizar(payload):
    for paquete in payload:
        Agente[paquete["ID"]] = {
                                "X": paquete["X"],
                                "Y": paquete["Y"],
                                "ID": paquete["ID"],
                                "Angulo": paquete["Angulo"]
                                }

#=======================================Codigo del controlador============================
# create an output pin on pin #0
p0 = Pin(2, Pin.OUT)
p0.value(1)

# set the value low then high
Swarm = Robotat()      #Objeto con la informacion de la comunicacion
print("Archivo servidor ejecutandoce..")
while True:
    Swarm.check_msg()
    Actualizar(Swarm.payload)
    if (Swarm.Sesion):
        #try:
        #    if(Agente[Swarm.client_id]["X"] == 30):
        #        Swarm.publish("Topico2", json.dumps([Agente[Swarm.client_id]]))
            print(Agente)
        #except:
        #    print("asd")