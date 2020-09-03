from core import  Reportar_Agente, Connection_Fail  #funciones para realizar la conexion

#Nos conectamos al topoico general AgentesSwarm
try:
    Agente = Reportar_Agente()
except OSError as e:
    Connection_Fail()

#Escuchamos comandos por parte de la aplicacion
while True:
    Agente.check_msg()