import asyncio
import os
import json
import time
import multiprocessing
import sys
import subprocess
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import date


fileSites = "sites.txt"
fileCommand = "command.txt"
fileOut = "results.txt"
pattern = ""
inPool = 20
timeout = 0
filter = True
alertOnly = False
spiderLevel = 0

totalSitiosInicial = 0
totalSitiosSpidering = 0

def main():
   
#   print ('Number of arguments:', len(sys.argv), 'arguments.')
#   print ('Argument List:', str(sys.argv))
   global fileSites
   global fileCommand
   global fileOut
   global pattern
   global inPool
   global alertOnly
   global filter
   global totalSitiosInicial
   global totalSitiosSpidering
   for i in range(1, len(sys.argv)):
      if(sys.argv[i] == '-iL'):
         fileSites = sys.argv[i+1]
      elif(sys.argv[i] == '-iC'):
         fileCommand = sys.argv[i+1]
      elif(sys.argv[i] == '-o'):
         fileOut = sys.argv[i+1]
      elif(sys.argv[i] == '-pat'):
         pattern = sys.argv[i+1]
      elif(sys.argv[i] == '-th'):
         inPool = int(sys.argv[i+1])
      elif(sys.argv[i] == '-T'):
         timeout = int(sys.argv[i+1])
      elif(sys.argv[i] == '-full'):
         filter = False
      elif(sys.argv[i] == '-ao'):
         alertOnly = True
      elif(sys.argv[i] == '-sp'):
         spiderLevel = int(sys.argv[i+1])
      elif(sys.argv[i] == '-h'):
         print("Commandos: ")
         print("   -iL    :   Nombre de la lista (default: sites.txt)")
         print("   -iC    :   Nombre del archivo con el comando a ejecutar (default: command.txt)")
         print("   -o     :   Nombre del archivo de salida (default: results.txt)")
         print("   -pat   :   Patron contra el cual validar (pendiente)")
         print("   -th    :   Numero de threads para paralelizar (default: 20)")
         print("   -T     :   Segundos de timeout para el comando (default: Sin timeout)(pendiente)")
         print("   -full  :   Entregar todo el output sin filtrar (default: false)")
         print("   -ao    :   Mostrar solo sitios como resultado")
         print("   -sp    :   Activa spider hasta el nivel ingresado a continuacion(default: 0)")
         print("   -h     :   Mostrar esta ayuda")

         sys.exit()
   print("Running with sites: " + fileSites + " command in: " + fileCommand + " Pool: " + str(inPool) + " filter: " + str(filter) )
   manager = multiprocessing.Manager()
   f = open(fileCommand,"r")
   command = f.readline().strip()
   f.close()
   f = open(fileSites,"r")
   initsitelist= set()
   sitelist = {}
   unifiedList = set()
   results = {}
   dictResult = {}
   line = f.readline()
   #Procesar archivo
   while(line):
      pos=line.find(" ")
      if(pos > -1 ):
         line = line[:pos]
      line=line.strip()
      line = forceHTTP(line)
      if(len(line)>4):
         initsitelist.add(line)
      line = f.readline()
   #Spidering
   totalSitiosInicial = len(initsitelist)
   if(spiderLevel>0):
      print("Comenzando spidering con " + str(totalSitiosInicial) + " sitios")
      sp = multiprocessing.Pool(inPool)
      item = 1
      for site in initsitelist:
         sitelist[site]=(sp.apply_async(spider,(site,0,item)))
         item = item +1
      sp.close()
      sp.join()
   #Aplanar la lista
      for k,v in sitelist.items():
         #print(k + " : " + str(v.get()))
         unifiedList.add(k)
         destack(v.get(),unifiedList)
   else:
      unifiedList = initsitelist
   saveSpiderResults(unifiedList)
   item = 1;
   totalSitiosSpidering = len(unifiedList)
   print ("Listado total de sitios a revisar: " + str(totalSitiosSpidering))
   #ejecucion de comomando
   po = multiprocessing.Pool(inPool)
   for line in unifiedList:
      results[line] = (po.apply_async(execmd, (command, line, item)))               
      item = item +1
   f.close()
   #f = open(fileOut,"w")
   today = date.today()
   f = open(fileOut + " " + str(today),"w")
   po.close()
   po.join()
   for k,v in results.items():
      buffer = v.get()
      if(buffer):
         dictResult[k]=v.get()
   #Guardar datos en archivo
   
   for k,v in dictResult.items():
      #print(k + ":" + str(v))
#      sp = v.split("\n")
      f.write("{" + k + " : " + str(v) + "}\n")
   f.close()



def saveSpiderResults(unifiedList):
   f = open("spiderResults","w")
   for r in unifiedList:
      f.write(str(r) + "\n")
   f.close()

def forceHTTP(site):
   if("https" in site):
      site=site.replace("https","http")
   elif("http" in site):
      return site
   else:
      return "http://" + site
   
def spider(site,currentLevel,glitem):
   global spiderLevel
   global totalSitiosInicial
   spiderlist = {}
   items = 0
   try:
      r = requests.get(site, allow_redirects=True, timeout=4)
   except requests.exceptions.Timeout:
      print("Timeout con sitio: " + site + " item " + str(glitem))
      log("Timeout con sitio: " + site + " item " + str(glitem))
      return
   except requests.exceptions.TooManyRedirects:
      print("Too many redirects " + site + " item " + str(glitem))
      log("Too many redirects, retornando: " + site + " item " + str(glitem))
      return
   except requests.exceptions.ConnectionError:
      print("Error de conexion con sitio " + site + " item " + str(glitem))
      log("Error de conexion con sitio: " + site + " item " + str(glitem))
      return
   except requests.exceptions.InvalidURL:
      print("URL invalida " + site + " item " + str(glitem))
      log("URL invalida: " + site + " item " + str(glitem))
      return
   except requests.exceptions.MissingSchema:
      print("Missing Schema " + site + " item " + str(glitem))
      log("Missing Schema: " + site + " item " + str(glitem))
      return
   if(r.status_code == 200):
      soup = BeautifulSoup(r.content, "html.parser")
      for a in soup.findAll("a"):
         href = a.get("href")
         if (href != "" and href is not None):
            #Si es un path comprobar si tiene / y agregar site
            if(href[0]=='/' and len(href) > 1):
               href = site + href
               items = items+1
               if( (currentLevel+1 ) <= spiderLevel):
                  spiderlist[href]= spider(href,currentLevel+1,glitem)
               else:
                  spiderlist[href]=""
            #si no, tiene que ser un subdominio
            else:
               href2 = parseURL(href)
               site2 = parseDomain(site)
               if(site2 in href  and len(href) > (len(site)+1) ):
                  items = items+1
                  href = forceHTTP(href)
                  if( (currentLevel+1 ) <= spiderLevel):
                     spiderlist[href]=spider(href,currentLevel+1,glitem)
                  else:
                     spiderlist[href]=""
   #print("Encontrados " + str(items) + " adicionales en el sitio " + site + " globalItem: " + str(glitem) + "/" + str(totalSitiosInicial))
   return spiderlist

def parseURL(site):
   site = site.strip()
   site = site.replace("https://","")
   site = site.replace("http://","")
   site = site.replace("www.","")
   return site

def parseDomain(site):
   site = site.strip()
   site = site.replace("https://","")
   site = site.replace("http://","")
   site = site.replace("www.","")
   pos = site.find('/')
   if(pos > -1):
      site = site[:pos]
   return site

def destack(item,fset):
   #print(item)
   if(item is not None and type(item)!=str):
      for l in item:
         destack(l,fset)
   elif (item != "" and item is not None):
      fset.add(str(item))
      return fset

def log(string):
   f=open("log","a")
   f.write(string + "\n")
   f.close()

def execmd(command, site, item):
   global alertOnly
   global filter
   global totalSitiosSpidering
   cmd = command + " " + site + "  2>/dev/null "
   cmd = cmd.strip()
   if(item%1000==0):
      print("Item: " + str(item) + "/" + str(totalSitiosSpidering))
   #print(cmd + " item: " + str(item) + "/" + str(totalSitiosSpidering))   
   stream = subprocess.Popen([cmd], stdout=subprocess.PIPE, shell=True)
   output = stream.stdout.readlines()
   #output = stream.read().encode('UTF-8')
   #output = stream.read()
   #print(output)
   if(filter):
      flag200 = False
      flagPass= False
      for o in output:
         if(not flag200 and b"200 OK" in o):
            flag200 = True
         elif(not flagPass and (b"type=\"password\"" in o) or  (b"type=\'password\'" in o)):
            flagPass=True
         elif(flag200 and flagPass):
            if(alertOnly):
               return "Vulnerable"
            else:
               return output
      return ""
   else:
      return output

if __name__ == "__main__":
#   asyncio.run(main())
   today = date.today()
  # print(os.getcwd())
  # logging.basicConfig(filename='/home/kali/Documents/bl.log',filemode='w',encoding='utf-8', level=logging.DEBUG)
   s = time.perf_counter()
   main()
   elapsed = time.perf_counter() - s
   print(f"{__file__} executed in {elapsed:0.2f} seconds.")
